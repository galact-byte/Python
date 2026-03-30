from __future__ import annotations

from pathlib import Path
import zipfile


def create_zip(source_dir: Path | str, zip_path: Path | str, ignore_names: set[str] | None = None) -> None:
    source = Path(source_dir)
    target = Path(zip_path)
    ignore = ignore_names or {".git", "__pycache__", "node_modules", ".pytest_cache"}
    target.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            rel = path.relative_to(source)
            if any(part in ignore for part in rel.parts):
                continue
            if path.is_file():
                zf.write(path, arcname=str(Path(source.name) / rel))
