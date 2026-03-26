import os
import re
import configparser
import sqlite3
import tomllib
import warnings
from datetime import date, datetime, time

import pandas as pd
import pyreadstat
import toons
import tomli_w
import vobject
import yaml, json
from pandas.api.types import is_object_dtype, is_scalar
from typing import Optional
from .converter_interface import ConverterInterface


def _structured_data_to_dataframe(data):
    if isinstance(data, list):
        return pd.DataFrame(data)

    if isinstance(data, dict):
        if len(data) == 1:
            only_key, only_value = next(iter(data.items()))
            if isinstance(only_value, list):
                if only_value and all(isinstance(item, dict) for item in only_value):
                    return pd.DataFrame(only_value).add_prefix(f'{only_key}.')

                return pd.DataFrame({only_key: only_value})

        return pd.json_normalize(data)

    return pd.DataFrame([data])


def _to_toml_document(data):
    if isinstance(data, dict):
        return data

    return {'data': data}


def _to_string_keyed_data(value):
    if isinstance(value, dict):
        return {str(key): _to_string_keyed_data(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_to_string_keyed_data(item) for item in value]

    if isinstance(value, tuple):
        return [_to_string_keyed_data(item) for item in value]

    return value


def _to_toml_compatible(value):
    if value is None:
        return ''

    if isinstance(value, dict):
        return {str(key): _to_toml_compatible(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_toml_compatible(item) for item in value]

    if hasattr(value, 'tolist') and not is_scalar(value):
        return _to_toml_compatible(value.tolist())

    if hasattr(value, 'item') and not isinstance(value, (str, bytes, bytearray, datetime, date, time)):
        try:
            value = value.item()
        except (AttributeError, ValueError, TypeError):
            pass

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, pd.Timedelta):
        return str(value)

    if isinstance(value, float) and pd.isna(value):
        return ''

    if value is pd.NA or value is pd.NaT:
        return ''

    return value


def _serialize_nested_value(value):
    if value is None:
        return None

    if is_scalar(value):
        return value

    if isinstance(value, set):
        value = list(value)
    elif hasattr(value, 'tolist'):
        value = value.tolist()

    return json.dumps(value, ensure_ascii=False)


def _stringify_value(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, float) and pd.isna(value):
        return None

    if hasattr(value, 'item') and not isinstance(value, (str, bytes, bytearray, datetime, date, time)):
        try:
            value = value.item()
        except (AttributeError, ValueError, TypeError):
            pass

    if not is_scalar(value):
        return _serialize_nested_value(value)

    return str(value)


def _sanitize_xml_tag_name(name):
    sanitized = re.sub(r'[^0-9A-Za-z_.-]+', '_', str(name)).strip('_')
    if not sanitized:
        sanitized = 'field'
    if re.match(r'^[0-9.-]', sanitized) or sanitized.lower().startswith('xml'):
        sanitized = f'field_{sanitized}'
    return sanitized


def _prepare_dataframe_for_arrow(df):
    prepared = df.copy()
    prepared.columns = [str(column) for column in prepared.columns]
    for column in prepared.columns:
        series = prepared[column]

        if isinstance(series.dtype, pd.CategoricalDtype):
            prepared[column] = series.astype('string')
            continue

        if not is_object_dtype(series.dtype):
            continue

        non_null = [value for value in series if value is not None and value is not pd.NA and not (isinstance(value, float) and pd.isna(value))]
        if not non_null:
            continue

        normalized_types = set()
        has_nested = False
        for value in non_null:
            candidate = value
            if hasattr(candidate, 'item') and not isinstance(candidate, (str, bytes, bytearray, datetime, date, time)):
                try:
                    candidate = candidate.item()
                except (AttributeError, ValueError, TypeError):
                    pass
            if not is_scalar(candidate):
                has_nested = True
                break
            normalized_types.add(type(candidate))

        if has_nested or len(normalized_types) > 1:
            prepared[column] = series.map(_stringify_value).astype('string')

    return prepared


def _prepare_dataframe_for_output(df, output_type):
    if output_type in {'parquet', 'feather', 'orc'}:
        return _prepare_dataframe_for_arrow(df)

    if output_type == 'sqlite':
        return df.apply(lambda column: column.map(_serialize_nested_value))

    if output_type == 'xml':
        prepared = df.apply(lambda column: column.map(_serialize_nested_value))
        prepared = prepared.rename(columns=lambda column: _sanitize_xml_tag_name(column))
        return prepared

    return df

class PandasConverter(ConverterInterface):
    supported_input_formats: set = {
        'csv',
        'xlsx',
        'json',
        'jsonl',
        'parquet',
        'yaml',
        'feather',
        'orc',
        'tsv',
        'xml',
        'html',
        'ods',
        'sqlite',
        'xls',     # read-only
        'dta',     # read-only
        'sav',     # read-only (SPSS)
        'xpt',     # read-only (SAS transport)
        'fwf',     # read-only (fixed-width)
        'toon',
        'toml',
        'ini',
        'env',
        'vcf',     # read-only (vCard contacts)
    }
    supported_output_formats: set = {
        'csv',
        'xlsx',
        'json',
        'jsonl',
        'parquet',
        'yaml',
        'feather',
        'orc',
        'tsv',
        'xml',
        'html',
        'ods',
        'sqlite',
        'toon',
        'toml',
        'ini',
        'env',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize Pandas converter.
        
        Args:
            input_file: Path to the input file
            output_dir: Directory where the output file will be saved
            input_type: Format of the input file (e.g., "csv", "xlsx")
            output_type: Format of the output file (e.g., "csv", "xlsx")
        """
        super().__init__(input_file, output_dir, input_type, output_type)
    
    def can_convert(self) -> bool:
        """
        Check if conversion between the specified formats is possible.
        
        Returns:
            True if conversion is possible, False otherwise
        """
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()
        
        # Check if formats are supported
        if input_fmt not in self.supported_input_formats or output_fmt not in self.supported_output_formats:
            return False
        
        return True

    def _read_xlsx(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                'ignore',
                message='Unknown extension is not supported and will be removed',
                category=UserWarning,
                module='openpyxl\\.worksheet\\._reader',
            )
            return pd.read_excel(self.input_file)

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the input file to the output format using Pandas.
        
        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Not applicable for data formats, ignored
        
        Returns:
            List of paths to the converted output files.
        """
        if not self.can_convert():
            raise ValueError(f"Conversion from {self.input_type} to {self.output_type} is not supported.")
        
        # Prepare output file path
        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        output_file = os.path.join(self.output_dir, f"{base_name}.{self.output_type}")
        
        # Check for overwrite
        if os.path.exists(output_file) and not overwrite:
            raise FileExistsError(f"Output file {output_file} already exists and overwrite is set to False.")
        
        # Handle structured document conversions directly to preserve nested structure.
        if self.input_type in ['yaml', 'json', 'toml', 'toon'] and self.output_type in ['yaml', 'json', 'toml', 'toon']:
            if self.input_type == 'yaml':
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            elif self.input_type == 'toml':
                with open(self.input_file, 'rb') as f:
                    data = tomllib.load(f)
            elif self.input_type == 'toon':
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    data = toons.load(f)
            else:  # json
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            if self.output_type == 'yaml':
                with open(output_file, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            elif self.output_type == 'toml':
                with open(output_file, 'wb') as f:
                    tomli_w.dump(_to_toml_compatible(_to_toml_document(data)), f)
            elif self.output_type == 'toon':
                with open(output_file, 'w', encoding='utf-8') as f:
                    toons.dump(_to_string_keyed_data(data), f)
            else:  # json
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            
            return [output_file]
        
        # For tabular conversions, use pandas
        df = None
        if self.input_type == 'csv':
            df = pd.read_csv(self.input_file)
        elif self.input_type == 'xlsx':
            df = self._read_xlsx()
        elif self.input_type == 'json':
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = _structured_data_to_dataframe(data)
        elif self.input_type == 'parquet':
            df = pd.read_parquet(self.input_file)
        elif self.input_type == 'feather':
            df = pd.read_feather(self.input_file)
        elif self.input_type == 'orc':
            df = pd.read_orc(self.input_file)
        elif self.input_type == 'tsv':
            df = pd.read_csv(self.input_file, sep='\t')
        elif self.input_type == 'xml':
            df = pd.read_xml(self.input_file)
        elif self.input_type == 'html':
            tables = pd.read_html(self.input_file)
            df = tables[0]
        elif self.input_type == 'ods':
            df = pd.read_excel(self.input_file, engine='odf')
        elif self.input_type == 'xls':
            df = pd.read_excel(self.input_file, engine='xlrd')
        elif self.input_type == 'jsonl':
            df = pd.read_json(self.input_file, lines=True)
        elif self.input_type == 'toon':
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = toons.load(f)
            df = _structured_data_to_dataframe(data)
        elif self.input_type == 'sqlite':
            conn = sqlite3.connect(self.input_file)
            tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
            table_name = tables['name'].iloc[0]
            # The table name comes from the file's own metadata so it's not 
            # exactly untrusted input, but we should still sanitize it properly.
            safe_name = table_name.replace('"', '""')
            # nosec B608 - table name is sanitized and comes from the database itself, not user input
            df = pd.read_sql(f'SELECT * FROM "{safe_name}"', conn)  # nosec B608
            conn.close()
        elif self.input_type == 'dta':
            df = pd.read_stata(self.input_file)
        elif self.input_type == 'sav':
            df, _ = pyreadstat.read_sav(self.input_file)
        elif self.input_type == 'xpt':
            df, _ = pyreadstat.read_xport(self.input_file)
        elif self.input_type == 'fwf':
            df = pd.read_fwf(self.input_file)
        elif self.input_type == 'toml':
            with open(self.input_file, 'rb') as f:
                data = tomllib.load(f)
            df = _structured_data_to_dataframe(data)
        elif self.input_type == 'ini':
            config = configparser.ConfigParser()
            config.read(self.input_file)
            rows = []
            for section in config.sections():
                for key, value in config.items(section):
                    rows.append({'section': section, 'key': key, 'value': value})
            df = pd.DataFrame(rows, columns=['section', 'key', 'value'])
        elif self.input_type == 'env':
            rows = []
            with open(self.input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    key, _, value = line.partition('=')
                    rows.append({'key': key.strip(), 'value': value.strip()})
            df = pd.DataFrame(rows, columns=['key', 'value'])
        elif self.input_type == 'yaml':
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            df = _structured_data_to_dataframe(data)
        elif self.input_type == 'vcf':
            with open(self.input_file, 'r', encoding='utf-8') as f:
                vcards = list(vobject.readComponents(f.read()))
            rows = []
            for vc in vcards:
                row = {}
                for field_name, field_items in vc.contents.items():
                    if field_name == 'version':
                        continue
                    for item in field_items:
                        val = item.value
                        if field_name == 'n':
                            row['last_name'] = val.family or ''
                            row['first_name'] = val.given or ''
                        elif field_name == 'categories':
                            row['categories'] = ', '.join(val) if isinstance(val, list) else str(val)
                        else:
                            row[field_name] = str(val)
                rows.append(row)
            df = pd.DataFrame(rows)

        df = _prepare_dataframe_for_output(df, self.output_type)
        
        # Write DataFrame to output format
        if self.output_type == 'csv':
            df.to_csv(output_file, index=False)
        elif self.output_type == 'xlsx':
            df.to_excel(output_file, index=False)
        elif self.output_type == 'json':
            df.to_json(output_file, orient='records', indent=2, date_format='iso')
        elif self.output_type == 'parquet':
            df.to_parquet(output_file, index=False)
        elif self.output_type == 'feather':
            df.to_feather(output_file)
        elif self.output_type == 'orc':
            df.to_orc(output_file, index=False)
        elif self.output_type == 'jsonl':
            df.to_json(output_file, orient='records', lines=True, date_format='iso')
        elif self.output_type == 'toon':
            with open(output_file, 'w', encoding='utf-8') as f:
                toons.dump(_to_string_keyed_data(df.to_dict(orient='records')), f)
        elif self.output_type == 'sqlite':
            conn = sqlite3.connect(output_file)
            df.to_sql('data', conn, index=False, if_exists='replace')
            conn.close()
        elif self.output_type == 'tsv':
            df.to_csv(output_file, sep='\t', index=False)
        elif self.output_type == 'xml':
            df.to_xml(output_file, index=False)
        elif self.output_type == 'html':
            from lxml import etree
            html_str = df.to_html(index=False)
            root = etree.fromstring(html_str.encode(), etree.HTMLParser())
            with open(output_file, 'wb') as f:
                f.write(etree.tostring(root, pretty_print=True, method='html'))
        elif self.output_type == 'ods':
            df.to_excel(output_file, engine='odf', index=False)
        elif self.output_type == 'yaml':
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(df.to_dict(orient='records'), f, default_flow_style=False)
        elif self.output_type == 'toml':
            with open(output_file, 'wb') as f:
                tomli_w.dump(_to_toml_compatible({'data': df.to_dict(orient='records')}), f)
        elif self.output_type == 'ini':
            config = configparser.ConfigParser(interpolation=None)
            if 'section' in df.columns and 'key' in df.columns and 'value' in df.columns:
                for _, row in df.iterrows():
                    section = str(row['section'])
                    if not config.has_section(section):
                        config.add_section(section)
                    config.set(section, str(row['key']), str(row['value']))
            else:
                config.add_section('data')
                for col in df.columns:
                    for i, val in enumerate(df[col]):
                        config.set('data', f'{col}_{i}', str(val))
            with open(output_file, 'w', encoding='utf-8') as f:
                config.write(f)
        elif self.output_type == 'env':
            with open(output_file, 'w', encoding='utf-8') as f:
                if 'key' in df.columns and 'value' in df.columns:
                    for _, row in df.iterrows():
                        f.write(f"{row['key']}={row['value']}\n")
                else:
                    for col in df.columns:
                        for i, val in enumerate(df[col]):
                            f.write(f"{col}_{i}={val}\n")

        return [output_file]