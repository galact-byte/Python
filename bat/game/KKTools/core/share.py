"""分享包生成：把角色卡与其依赖的 mod 一起整理输出，方便分享给别人。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from core.kk_card import KoikatuCard, extract_mod_ids
from core.mod_index import ModIndex


def _card_name(path: Path) -> str:
    try:
        card = KoikatuCard.load(path)
        p = card.parameter or {}
        name = f"{p.get('lastname','')}{p.get('firstname','')}".strip() or p.get("nickname", "")
        return name or path.stem
    except Exception:  # noqa: BLE001
        return path.stem


def build_share_package(
    card_paths: list[str],
    index: ModIndex,
    out_dir: str | Path,
    *,
    group_by_char: bool = True,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """为若干角色卡生成分享包。

    每张卡：复制卡片本身 + 从索引中复制其依赖且本地存在的 zipmod；记录缺失的 mod。
    group_by_char=True 时每张卡一个子目录，否则集中放到 cards/ 与 mods/。
    返回汇总报告 dict。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {"cards": [], "total_missing": set(), "copied_mods": set()}
    total = len(card_paths)
    for i, cp in enumerate(card_paths, 1):
        cp = Path(cp)
        name = _card_name(cp)
        safe = "".join(c for c in name if c not in r'\/:*?"<>|').strip() or cp.stem

        if group_by_char:
            base = out_dir / safe
            card_dst_dir = base
            mods_dst_dir = base / "mods"
        else:
            card_dst_dir = out_dir / "cards"
            mods_dst_dir = out_dir / "mods"
        card_dst_dir.mkdir(parents=True, exist_ok=True)
        mods_dst_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(cp, card_dst_dir / cp.name)

        try:
            card = KoikatuCard.load(cp)
            required = extract_mod_ids(card)
        except Exception:  # noqa: BLE001
            required = {}

        present, missing = [], []
        for guid in required:
            entry = index.get(guid)
            if entry and entry.path and Path(entry.path).exists():
                dst = mods_dst_dir / Path(entry.path).name
                if not dst.exists():
                    shutil.copy2(entry.path, dst)
                present.append(guid)
                report["copied_mods"].add(guid)
            else:
                missing.append(guid)
        report["total_missing"].update(missing)
        report["cards"].append({
            "card": cp.name, "name": name,
            "required": len(required), "copied": len(present), "missing": missing,
        })
        if progress:
            progress(i, total, name)

    # 写一份说明
    readme = out_dir / "README.txt"
    lines = ["KKTools 分享包", f"共 {len(card_paths)} 张角色卡", ""]
    for c in report["cards"]:
        lines.append(f"[{c['name']}] {c['card']}  依赖 {c['required']} | 已含 {c['copied']} | 缺失 {len(c['missing'])}")
        for m in c["missing"]:
            lines.append(f"    缺失: {m}")
    readme.write_text("\n".join(lines), encoding="utf-8")

    report["total_missing"] = sorted(report["total_missing"])
    report["copied_mods"] = sorted(report["copied_mods"])
    return report
