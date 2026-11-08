"""Smoke tests for the initial project structure."""

from importlib import import_module


def test_application_package_is_importable() -> None:
    """The application package must expose its initial version."""
    app = import_module("app")

    assert app.__version__ == "0.1.0"
