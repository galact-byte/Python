from __future__ import annotations

import json
from pathlib import Path

from .models import ProjectConfig


class ConfigStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load_all(self) -> list[ProjectConfig]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [ProjectConfig.from_dict(item) for item in data.get("projects", [])]

    def save_all(self, projects: list[ProjectConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"projects": [project.to_dict() for project in projects]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
