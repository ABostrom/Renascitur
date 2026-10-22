import importlib
import os

import pytest


def test_engine_package_imports():
    import renasci

    assert renasci.__version__ == "0.1.0"


def test_engine_pins_blas_to_one_thread():
    import renasci  # noqa: F401

    assert os.environ["OPENBLAS_NUM_THREADS"] == "1"
    assert os.environ["MKL_NUM_THREADS"] == "1"


def test_legacy_prototype_only_under_renasci_legacy():
    legacy = importlib.import_module("renasci_legacy.world")
    assert hasattr(legacy, "World")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("renasci.world")
