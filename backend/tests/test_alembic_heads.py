from __future__ import annotations

import ast
from pathlib import Path


def _parse_down_revision(raw: str) -> tuple[str, ...]:
    if raw == "None":
        return ()

    value = ast.literal_eval(raw)
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return (str(value),)


def _load_revision_map() -> tuple[set[str], set[str]]:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revisions: set[str] = set()
    parents: set[str] = set()

    for path in versions_dir.glob("*.py"):
        revision: str | None = None
        down_revisions: tuple[str, ...] = ()

        for line in path.read_text().splitlines():
            if line.startswith("revision = "):
                revision = line.split("=", 1)[1].strip().strip('"\'')
            if line.startswith("down_revision = "):
                raw = line.split("=", 1)[1].strip()
                down_revisions = _parse_down_revision(raw)

        assert revision is not None, f"Missing revision in {path.name}"
        revisions.add(revision)
        parents.update(down_revisions)

    return revisions, parents


def test_alembic_has_single_head() -> None:
    revisions, parents = _load_revision_map()
    heads = sorted(revision for revision in revisions if revision not in parents)

    assert heads == ["20260426_0015"]
