import base64
from defusedxml import ElementTree as DefusedET
from pathlib import Path

from converters.pypandoc_convert import PyPandocConverter


def test_prepare_fb2_input_sanitizes_binary_ids(safe_path_test_settings, monkeypatch):
    monkeypatch.setattr(
        'converters.pypandoc_convert.get_settings',
        lambda: safe_path_test_settings,
    )

    input_file = safe_path_test_settings.upload_dir / 'abcdef123.fb2'
    input_file.write_text(
        f'''<?xml version="1.0" encoding="UTF-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:xlink="http://www.w3.org/1999/xlink">
  <description>
    <title-info>
      <coverpage><image xlink:href="#../../evil.jpg" /></coverpage>
    </title-info>
  </description>
  <body><section><p>hello</p></section></body>
  <binary id="../../evil.jpg" content-type="image/jpeg">{base64.b64encode(b'test-image').decode('ascii')}</binary>
</FictionBook>
''',
        encoding='utf-8',
    )

    converter = PyPandocConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type='fb2',
        output_type='epub',
    )

    prepared_input, cleanup_paths = converter._prepare_fb2_input(input_file)
    prepared_path = Path(prepared_input)

    try:
        assert prepared_path.parent.parent == safe_path_test_settings.tmp_dir.resolve()
        extracted_files = {path.name for path in prepared_path.parent.iterdir() if path.is_file()}
        assert 'evil.jpg' in extracted_files
        assert '../../evil.jpg' not in extracted_files

        tree = DefusedET.parse(prepared_path)
        namespace = {
            'fb2': 'http://www.gribuser.ru/xml/fictionbook/2.0',
            'xlink': 'http://www.w3.org/1999/xlink',
        }
        image = tree.find('.//fb2:image', namespace)
        binary = tree.find('fb2:binary', namespace)

        assert image is not None
        assert binary is not None
        assert image.attrib['{http://www.w3.org/1999/xlink}href'] == '#evil.jpg'
        assert binary.attrib['id'] == 'evil.jpg'
    finally:
        for cleanup_path in cleanup_paths:
            cleanup_target = Path(cleanup_path)
            if cleanup_target.is_dir():
                for child in cleanup_target.iterdir():
                    child.unlink()
                cleanup_target.rmdir()
            elif cleanup_target.exists():
                cleanup_target.unlink()