"""轻量配置存储：游戏目录、Mod 路径、输出目录等。

配置写在应用目录下的 config.json（已被 .gitignore 忽略），结构简单，按需读写。
"""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULTS: dict = {
    "kk_game_dir": "",          # 恋活游戏根目录
    "kks_game_dir": "",         # 恋活日光浴游戏根目录
    "mod_dirs": [],             # 额外的 Mod 仓库目录（zipmod 所在）
    "output_dir": "",           # 通用输出目录
    "last_browse_dir": "",      # 浏览器上次打开目录
    "carrier_dir": "",          # 伪装载体（视频/图片）目录
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: data.get(k, v) for k, v in DEFAULTS.items()})
        except (json.JSONDecodeError, OSError):
            pass  # 配置损坏不应阻塞应用，回退默认
    return cfg


def save(cfg: dict) -> None:
    merged = dict(DEFAULTS)
    merged.update({k: cfg.get(k, v) for k, v in DEFAULTS.items()})
    _CONFIG_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)


def guess_mod_dirs() -> list[str]:
    """从已配置的游戏目录推断默认 mod 目录（<game>/mods）。"""
    dirs: list[str] = []
    cfg = load()
    for key in ("kk_game_dir", "kks_game_dir"):
        base = cfg.get(key)
        if base:
            mods = Path(base) / "mods"
            if mods.is_dir():
                dirs.append(str(mods))
    dirs.extend(d for d in cfg.get("mod_dirs", []) if d)
    return dirs
