"""目录卡片扫描：遍历目录下的 PNG，识别类型并提取缩略图与基本信息。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from core.kk_card import KNOWN_MARKERS, KoikatuCard, classify

TYPE_LABELS = {
    "character": "角色卡",
    "coordinate": "服装卡",
    "scene": "场景卡",
    "other": "其它",
}


@dataclass
class CardItem:
    path: str
    type: str            # character / coordinate / scene / other
    game: str            # KK / KKS / ?
    name: str            # 角色名（仅角色卡）
    thumbnail: bytes     # 缩略图字节（PNG）


def _read_head(path: Path, head_bytes: int = 0) -> bytes:
    return path.read_bytes()


def scan_item(path: Path) -> CardItem | None:
    """识别单个 PNG 文件，返回 CardItem；非卡片 PNG 也会返回 type=other。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    ctype, game, _marker = classify(data)
    name = ""
    thumb = b""
    if ctype == "character":
        try:
            card = KoikatuCard.from_bytes(data)
            thumb = card.thumbnail
            p = card.parameter or {}
            name = f"{p.get('lastname','')}{p.get('firstname','')}".strip() or p.get("nickname", "")
        except Exception:  # noqa: BLE001
            thumb = _first_png(data)
    else:
        thumb = _first_png(data)
    return CardItem(path=str(path), type=ctype, game=game, name=name, thumbnail=thumb)


def _first_png(data: bytes) -> bytes:
    from core.kk_card import KKCardError, png_data_length

    try:
        n = png_data_length(data, 0)
        return data[:n]
    except KKCardError:
        return b""


def scan_dir(
    directory: str | Path,
    *,
    recursive: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[CardItem]:
    """扫描目录下的 PNG（默认不递归）。"""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    if recursive:
        files = [p for p in directory.rglob("*.png") if p.is_file()]
    else:
        files = [p for p in directory.glob("*.png") if p.is_file()]
    total = len(files)
    items: list[CardItem] = []
    for i, p in enumerate(files, 1):
        item = scan_item(p)
        if item is not None:
            items.append(item)
        if progress and (i % 10 == 0 or i == total):
            progress(i, total, p.name)
    return items
