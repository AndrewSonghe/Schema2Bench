from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DomainSpec:
    domain_id: str
    manifest_path: Path
    db_path: Path
    sample_path: Path | None = None


def load_manifest_domain(manifest_path: str | Path) -> DomainSpec:
    path = Path(manifest_path).resolve()
    data = json.loads(path.read_text())
    manifest_dir = path.parent
    db_cfg: dict[str, Any] = data["database"]
    if "path" not in db_cfg:
        raise ValueError(f"Schema2Bench currently expects single-db manifest database.path: {path}")
    db_path = _resolve_existing_path(manifest_dir, db_cfg["path"])
    sample_path = None
    if "samples" in data and "path" in data["samples"]:
        sample_path = _resolve_existing_path(manifest_dir, data["samples"]["path"], required=False)
    return DomainSpec(
        domain_id=data.get("dataset_id", path.stem),
        manifest_path=path,
        db_path=db_path,
        sample_path=sample_path,
    )


def _resolve_existing_path(manifest_dir: Path, raw_path: str, required: bool = True) -> Path:
    path = (manifest_dir / raw_path).resolve()
    if path.exists():
        return path
    text = str(path)
    fallback = Path(text.replace("text2sql_benchmark_datasets", "datasets"))
    if fallback.exists():
        return fallback
    if required:
        raise FileNotFoundError(f"Manifest path does not exist: {path}")
    return path


def resolve_domain(value: str | Path) -> DomainSpec:
    path = Path(value)
    if path.exists() and path.suffix == ".json":
        return load_manifest_domain(path)
    candidate = Path("ArcSQLBench") / "manifests" / f"{value}.json"
    if candidate.exists():
        return load_manifest_domain(candidate)
    raise FileNotFoundError(f"Cannot resolve domain '{value}' as manifest path or ArcSQLBench manifest id")


def write_json(path: str | Path, obj: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
