import os
from pathlib import Path
import subprocess
import sys

import pytest

from core import pdf_layout


def test_layout_sessions_use_explicit_threads_and_extract_markdown():
    # A fresh process is needed: the layout models are initialized only once.
    script = """
import onnxruntime
from core.pdf_layout import load_pymupdf4llm

original = onnxruntime.InferenceSession
sessions = []
def record_session(*args, **kwargs):
    session = original(*args, **kwargs)
    sessions.append(session)
    return session

onnxruntime.InferenceSession = record_session
extractor = load_pymupdf4llm()
assert onnxruntime.InferenceSession is record_session
assert len(sessions) == 2
assert all(s.get_session_options().intra_op_num_threads == 1 for s in sessions)

import pymupdf
with pymupdf.open() as document:
    page = document.new_page()
    page.insert_text((72, 72), 'Container PDF extraction works.')
    result = extractor.to_markdown(document, show_progress=False)
    assert 'Container PDF extraction works.' in result, result
"""
    backend = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend,
        env={**os.environ, "ORT_DISABLE_TELEMETRY": "1"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pthread_setaffinity_np failed" not in result.stderr


def test_failed_import_restores_onnx_constructor(monkeypatch):
    original = pdf_layout.onnxruntime.InferenceSession

    def fail_import(name):
        raise ImportError("layout unavailable")

    monkeypatch.setattr(pdf_layout.importlib, "import_module", fail_import)
    with pytest.raises(ImportError, match="layout unavailable"):
        pdf_layout.load_pymupdf4llm()
    assert pdf_layout.onnxruntime.InferenceSession is original
