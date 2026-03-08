import os
import pandas as pd
import yaml, json
from typing import Optional
from .converter_interface import ConverterInterface

class PandasConverter(ConverterInterface):
    supported_input_formats: set = {
        'csv',
        'xlsx',
        'json',
        'parquet',
        'yaml',
        'feather',
        'orc',
        'tsv',
        'xml',
        'html',
        'ods',
        'xls',   # read-only
        'dta',   # read-only
    }
    supported_output_formats: set = {
        'csv',
        'xlsx',
        'json',
        'parquet',
        'yaml',
        'feather',
        'orc',
        'tsv',
        'xml',
        'html',
        'ods',
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
        
        # Handle YAML <-> JSON conversions directly (preserve nested structure)
        if self.input_type in ['yaml', 'json'] and self.output_type in ['yaml', 'json']:
            if self.input_type == 'yaml':
                with open(self.input_file, 'r') as f:
                    data = yaml.safe_load(f)
            else:  # json
                with open(self.input_file, 'r') as f:
                    data = json.load(f)
            
            if self.output_type == 'yaml':
                with open(output_file, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            else:  # json
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=2)
            
            return [output_file]
        
        # For tabular conversions, use pandas
        df = None
        if self.input_type == 'csv':
            df = pd.read_csv(self.input_file)
        elif self.input_type == 'xlsx':
            df = pd.read_excel(self.input_file)
        elif self.input_type == 'json':
            with open(self.input_file, 'r') as f:
                data = json.load(f)
            # Try to convert to DataFrame - if it's a list of dicts, it works directly
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                # For nested structures, flatten them
                df = pd.json_normalize(data)
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
        elif self.input_type == 'dta':
            df = pd.read_stata(self.input_file)
        elif self.input_type == 'yaml':
            with open(self.input_file, 'r') as f:
                data = yaml.safe_load(f)
            # Try to convert to DataFrame - if it's a list of dicts, it works directly
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                # For nested structures, flatten them
                df = pd.json_normalize(data)
        
        # Write DataFrame to output format
        if self.output_type == 'csv':
            df.to_csv(output_file, index=False)
        elif self.output_type == 'xlsx':
            df.to_excel(output_file, index=False)
        elif self.output_type == 'json':
            df.to_json(output_file, orient='records', indent=2)
        elif self.output_type == 'parquet':
            df.to_parquet(output_file, index=False)
        elif self.output_type == 'feather':
            df.to_feather(output_file)
        elif self.output_type == 'orc':
            df.to_orc(output_file, index=False)
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
            with open(output_file, 'w') as f:
                yaml.dump(df.to_dict(orient='records'), f, default_flow_style=False)

        return [output_file]