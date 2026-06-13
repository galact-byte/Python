"""Mod 仓库索引与缺失检测。

- 扫描目录下的 .zipmod / .zip，读取内部 manifest.xml，建立 {guid: 信息} 索引。
- 从角色卡提取依赖 ModID（见 kk_card.extract_mod_ids）。
- 比对卡片依赖与本地索引，给出缺失清单。

索引可缓存为 JSON，避免每次重扫海量 mod 目录。
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from core.kk_card import KoikatuCard, extract_mod_ids

MOD_SUFFIXES = (".zipmod", ".zip")


@dataclass
class ModEntry:
    guid: str
    name: str = ""
    version: str = ""
    author: str = ""
    path: str = ""


def read_manifest(zip_path: Path) -> ModEntry | None:
    """读取单个 zipmod 的 manifest.xml，返回 ModEntry；无 manifest 或无 guid 则 None。"""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if "manifest.xml" not in zf.namelist():
                return None
            raw = zf.read("manifest.xml")
    except (zipfile.BadZipFile, OSError):
        return None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None

    def text(tag: str) -> str:
        el = root.find(tag)
        return (el.text or "").strip() if el is not None else ""

    guid = text("guid")
    if not guid:
        return None
    return ModEntry(
        guid=guid,
        name=text("name"),
        version=text("version"),
        author=text("author"),
        path=str(zip_path),
    )


def iter_mod_files(dirs: Iterable[str]) -> Iterable[Path]:
    for d in dirs:
        base = Path(d)
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix.lower() in MOD_SUFFIXES and p.is_file():
                yield p


@dataclass
class ModIndex:
    """guid -> ModEntry 的全局索引。"""

    entries: dict[str, ModEntry] = field(default_factory=dict)

    def __contains__(self, guid: str) -> bool:
        return guid in self.entries

    def get(self, guid: str) -> ModEntry | None:
        return self.entries.get(guid)

    @property
    def count(self) -> int:
        return len(self.entries)

    def build(
        self,
        dirs: Iterable[str],
        progress: Callable[[int, str], None] | None = None,
    ) -> "ModIndex":
        """扫描目录建立索引。progress(已处理数, 当前文件) 可选回调。"""
        self.entries.clear()
        files = list(iter_mod_files(dirs))
        total = len(files)
        for i, p in enumerate(files, 1):
            entry = read_manifest(p)
            if entry:
                # 同 guid 多版本时保留后扫到的（一般是更全的整合包）
                self.entries[entry.guid] = entry
            if progress and (i % 50 == 0 or i == total):
                progress(i, str(p))
        return self

    def save(self, path: str | Path) -> None:
        data = {
            "entries": {
                g: {"name": e.name, "version": e.version, "author": e.author, "path": e.path}
                for g, e in self.entries.items()
            }
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ModIndex":
        idx = cls()
        p = Path(path)
        if not p.exists():
            return idx
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return idx
        for guid, info in data.get("entries", {}).items():
            idx.entries[guid] = ModEntry(
                guid=guid,
                name=info.get("name", ""),
                version=info.get("version", ""),
                author=info.get("author", ""),
                path=info.get("path", ""),
            )
        return idx


@dataclass
class MissingReport:
    card_path: str
    required: dict[str, int]            # ModID -> 次数
    present: list[str]                  # 仓库里有的
    missing: list[str]                  # 仓库里没有的

    @property
    def required_count(self) -> int:
        return len(self.required)

    @property
    def missing_count(self) -> int:
        return len(self.missing)


def check_card(card_path: str | Path, index: ModIndex) -> MissingReport:
    """检查一张角色卡的 mod 依赖在索引中的缺失情况。"""
    card = KoikatuCard.load(card_path)
    required = extract_mod_ids(card)
    present = [g for g in required if g in index]
    missing = [g for g in required if g not in index]
    return MissingReport(
        card_path=str(card_path),
        required=required,
        present=sorted(present),
        missing=sorted(missing),
    )
