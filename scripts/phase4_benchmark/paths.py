"""Resolve repository root and canonical benchmark output paths."""

from __future__ import annotations

from pathlib import Path

_MARKERS = ("api-service", "scripts", "docker")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk parents until repo markers (api-service + scripts + docker) are present."""
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if all((candidate / name).exists() for name in _MARKERS):
            return candidate
    msg = f"Could not find repository root from {start}"
    raise FileNotFoundError(msg)


def results_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or find_repo_root()) / "benchmarks" / "results"


def manifest_path(repo_root: Path | None = None) -> Path:
    return results_dir(repo_root) / "last_seed_manifest.json"


def resolve_output_path(path: Path | None, repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    if path is None:
        return results_dir(root)
    return path if path.is_absolute() else root / path
