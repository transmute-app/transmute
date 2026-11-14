"""Initialize PyMuPDF's layout models without automatic CPU affinity."""

import importlib

import onnxruntime


def load_pymupdf4llm():
    # pymupdf-layout 1.27.2 eagerly creates two ONNX sessions without exposing
    # session options. Automatic affinity can target CPUs unavailable inside a
    # container. An explicit thread count disables that affinity behavior.
    # Keep this workaround scoped to startup imports, before workers start.
    inference_session = onnxruntime.InferenceSession

    def create_session(path_or_bytes, sess_options=None, *args, **kwargs):
        if sess_options is None:
            sess_options = onnxruntime.SessionOptions()
        if sess_options.intra_op_num_threads == 0:
            sess_options.intra_op_num_threads = 1
        return inference_session(path_or_bytes, sess_options, *args, **kwargs)

    onnxruntime.InferenceSession = create_session
    try:
        return importlib.import_module("pymupdf4llm")
    finally:
        onnxruntime.InferenceSession = inference_session
