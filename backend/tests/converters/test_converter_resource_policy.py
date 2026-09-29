"""Regression tests for converter resource-access hardening.

Covers the pandoc include-directive local file read (GHSA-q3fc-r99p-5gj7) and
the WeasyPrint external resource fetch (GHSA-jcqc-6m64-4xv6).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.modules.setdefault('weasyprint', MagicMock())

from converters.pypandoc_convert import PyPandocConverter
from converters.safe_resources import safe_url_fetcher, BlockedResourceError


def _make_converter(tmp_path, input_type='rst', output_type='txt'):
    return PyPandocConverter(
        input_file=str(tmp_path / f'in.{input_type}'),
        output_dir=str(tmp_path),
        input_type=input_type,
        output_type=output_type,
    )


@pytest.mark.parametrize('output_type', ['txt', 'html', 'docx', 'pdf'])
def test_pandoc_always_runs_sandboxed(tmp_path, output_type):
    """--sandbox must be present for every output format."""
    converter = _make_converter(tmp_path, output_type=output_type)
    source = tmp_path / 'in.rst'
    source.write_text('content')

    assert '--sandbox' in converter._build_extra_args(str(source))


@pytest.mark.parametrize('scheme_url', [
    'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
    'https://internal.svc.cluster.local/admin',
    'file:///etc/passwd',
    'file:///proc/self/environ',
    '//evil.example/x.png',
    '/app/.env',
])
def test_renderer_refuses_external_resources(scheme_url):
    with pytest.raises(BlockedResourceError):
        safe_url_fetcher(scheme_url)


def test_renderer_allows_inline_data_uris():
    """Inline email/document media arrives as data: URIs and must still render."""
    fetcher = MagicMock(return_value={'string': b'ok'})
    urls_module = MagicMock(default_url_fetcher=fetcher)

    with patch.dict(sys.modules, {'weasyprint.urls': urls_module}):
        result = safe_url_fetcher('data:text/plain;base64,aGVsbG8=')

    assert result == {'string': b'ok'}
    fetcher.assert_called_once()


def test_pandoc_include_directive_cannot_read_local_file(tmp_path):
    """End-to-end: an include directive must not pull in an unrelated file."""
    pypandoc = pytest.importorskip('pypandoc')

    secret = tmp_path / 'secret.txt'
    secret.write_text('TRANSMUTE_SECRET_MARKER')
    source = tmp_path / 'in.rst'
    source.write_text(f'BEFORE\n\n.. include:: {secret}\n\nAFTER\n')

    converter = _make_converter(tmp_path, output_type='txt')
    output = pypandoc.convert_file(
        str(source),
        'plain',
        format='rst',
        extra_args=converter._build_extra_args(str(source)),
    )

    assert 'TRANSMUTE_SECRET_MARKER' not in output
    assert 'BEFORE' in output
