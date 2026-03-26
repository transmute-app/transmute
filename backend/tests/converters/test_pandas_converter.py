import json
import mimetypes
from pathlib import Path

import toons

from converters.pandas_convert import PandasConverter


def test_json_to_toon_preserves_nested_structure(tmp_path):
    payload = {
        'meta': {'source': 'unit-test', 'version': 3},
        'users': [
            {'id': 1, 'name': 'Ada', 'roles': ['admin', 'editor']},
            {'id': 2, 'name': 'Grace', 'roles': ['viewer']},
        ],
        'active': True,
    }
    input_file = tmp_path / 'input.json'
    input_file.write_text(json.dumps(payload), encoding='utf-8')

    converter = PandasConverter(str(input_file), str(tmp_path), 'json', 'toon')

    [output_file] = converter.convert()

    with open(output_file, 'r', encoding='utf-8') as file_handle:
        result = toons.load(file_handle)

    assert result == payload


def test_toon_to_json_preserves_nested_structure(tmp_path):
    payload = {
        'meta': {'source': 'unit-test', 'version': 3},
        'users': [
            {'id': 1, 'name': 'Ada', 'roles': ['admin', 'editor']},
            {'id': 2, 'name': 'Grace', 'roles': ['viewer']},
        ],
        'active': True,
    }
    input_file = tmp_path / 'input.toon'
    with open(input_file, 'w', encoding='utf-8') as file_handle:
        toons.dump(payload, file_handle)

    converter = PandasConverter(str(input_file), str(tmp_path), 'toon', 'json')

    [output_file] = converter.convert()

    result = json.loads(Path(output_file).read_text(encoding='utf-8'))

    assert result == payload


def test_toon_to_csv_converts_tabular_data(tmp_path):
    payload = [
        {'id': 1, 'name': 'Ada'},
        {'id': 2, 'name': 'Grace'},
    ]
    input_file = tmp_path / 'input.toon'
    with open(input_file, 'w', encoding='utf-8') as file_handle:
        toons.dump(payload, file_handle)

    converter = PandasConverter(str(input_file), str(tmp_path), 'toon', 'csv')

    [output_file] = converter.convert()

    assert Path(output_file).read_text(encoding='utf-8').splitlines() == [
        'id,name',
        '1,Ada',
        '2,Grace',
    ]


def test_named_toon_array_to_csv_flattens_with_prefix(tmp_path):
    input_file = tmp_path / 'employees.toon'
    input_file.write_text(
        '\n'.join([
            'employees[2]{employee_id,name,department,salary,hire_date}:',
            '  101,Alice Johnson,Engineering,95000,2020-03-15',
            '  102,Bob Smith,Marketing,75000,2021-06-01',
        ]),
        encoding='utf-8',
    )

    converter = PandasConverter(str(input_file), str(tmp_path), 'toon', 'csv')

    [output_file] = converter.convert()

    assert Path(output_file).read_text(encoding='utf-8').splitlines() == [
        'employees.employee_id,employees.name,employees.department,employees.salary,employees.hire_date',
        '101,Alice Johnson,Engineering,95000,2020-03-15',
        '102,Bob Smith,Marketing,75000,2021-06-01',
    ]