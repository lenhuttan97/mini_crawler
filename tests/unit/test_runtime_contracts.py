"""Static contracts for deployable P00 runtime configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _project_dependencies() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {
        dependency.split(">", 1)[0].split("[", 1)[0]
        for dependency in project["project"]["dependencies"]
    }


def _dev_dependencies() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {
        dependency.split(">", 1)[0].split("[", 1)[0]
        for dependency in project["dependency-groups"]["dev"]
    }


def test_runtime_dependencies_are_production_dependencies() -> None:
    """The API image must install FastAPI and Uvicorn without dev dependencies."""
    dependencies = _project_dependencies()

    assert {"fastapi", "uvicorn"} <= dependencies


def test_async_test_plugin_is_available_in_development() -> None:
    """P00 requires the async pytest plugin for async API/service tests."""
    assert "pytest-asyncio" in _dev_dependencies()


def test_compose_mounts_existing_searxng_config() -> None:
    """Every repository-relative Compose bind mount must exist in the repository."""
    assert (ROOT / "infra" / "searxng" / "settings.yml").is_file()


def test_ci_syncs_test_tooling_explicitly() -> None:
    """CI installs its declared test/lint group before invoking pytest and Ruff."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "uv sync --frozen" in workflow
    assert "uv sync --frozen --no-group dev" not in workflow


def test_api_image_installs_project_after_copying_its_build_inputs() -> None:
    """The image must contain package files at sync time and never sync on startup."""
    dockerfile = (ROOT / "Dockerfile.local").read_text(encoding="utf-8")

    assert dockerfile.index("COPY pyproject.toml uv.lock README.md ./") < dockerfile.index(
        "RUN uv sync --frozen"
    )
    assert dockerfile.index("COPY app ./app") < dockerfile.index("RUN uv sync --frozen")
    assert '"--no-sync", "uvicorn"' in dockerfile
