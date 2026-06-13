"""Mod 仓库 / 缺失检测 页。

扫描 mod 目录建立 GUID 索引（可缓存），把角色卡加入检查队列，比对依赖找出缺失。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import mod_index, settings
from ui.applog import log
from ui.widgets import PageBase, hint, make_card, section_title
from ui.worker import Worker

_INDEX_CACHE = Path(__file__).resolve().parent.parent.parent / "mod_index.json"


class _CardDropList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".png"):
                self.addItem(p)


class ModPage(PageBase):
    def __init__(self):
        super().__init__("Mod 仓库", "扫描本地 zipmod 建立 GUID 索引，检测角色卡缺失的 mod")
        self.index = mod_index.ModIndex.load(_INDEX_CACHE)
        self._worker: Worker | None = None
        self._build_ui()
        self._refresh_index_status()

    def _build_ui(self) -> None:
        # 索引区
        idx_card = make_card()
        iv = QVBoxLayout(idx_card)
        iv.setContentsMargins(14, 14, 14, 14)
        iv.addWidget(section_title("Mod 索引"))
        self.index_status = QLabel()
        self.index_status.setObjectName("HintLabel")
        iv.addWidget(self.index_status)
        row = QHBoxLayout()
        b_build = QPushButton("建立 / 重建索引"); b_build.setProperty("accent", "primary")
        b_build.clicked.connect(self._build_index)
        b_dirs = QPushButton("配置 Mod 目录")
        b_dirs.clicked.connect(self._config_dirs)
        row.addWidget(b_build); row.addWidget(b_dirs); row.addStretch(1)
        iv.addLayout(row)
        iv.addWidget(hint(f"索引缓存: {_INDEX_CACHE.name}（关闭后保留，下次直接加载）"))
        self.body_layout.addWidget(idx_card)

        # 检查区
        chk = make_card()
        cv = QVBoxLayout(chk)
        cv.setContentsMargins(14, 14, 14, 14)
        cv.addWidget(section_title("卡片 Mod 检查队列"))
        cv.addWidget(hint("拖入或选择角色卡 PNG，检查它们依赖的 mod 在本地索引中是否齐全。"))
        body = QHBoxLayout()
        self.queue = _CardDropList()
        body.addWidget(self.queue, 1)
        self.result = QPlainTextEdit(); self.result.setReadOnly(True)
        body.addWidget(self.result, 2)
        cv.addLayout(body, 1)
        row2 = QHBoxLayout()
        b_add = QPushButton("加入角色卡"); b_add.clicked.connect(self._add_cards)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.queue.clear)
        b_chk = QPushButton("检查队列"); b_chk.setProperty("accent", "primary")
        b_chk.clicked.connect(self._check)
        b_exp = QPushButton("导出缺失清单"); b_exp.clicked.connect(self._export_missing)
        row2.addWidget(b_add); row2.addWidget(b_clr); row2.addStretch(1)
        row2.addWidget(b_chk); row2.addWidget(b_exp)
        cv.addLayout(row2)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        cv.addWidget(self.progress)
        self.body_layout.addWidget(chk, 1)

        self._last_missing: dict[str, list[str]] = {}

    # ---- 索引 ----

    def _refresh_index_status(self) -> None:
        self.index_status.setText(f"当前索引：{self.index.count} 个 mod（按 guid 去重）")

    def _config_dirs(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择一个 Mod 目录加入仓库")
        if not d:
            return
        cfg = settings.load()
        dirs = list(cfg.get("mod_dirs", []))
        if d not in dirs:
            dirs.append(d)
            settings.set_value("mod_dirs", dirs)
            QMessageBox.information(self, "已添加", f"已加入 Mod 目录：\n{d}\n请重建索引生效。")

    def _build_index(self) -> None:
        dirs = settings.guess_mod_dirs()
        if not dirs:
            QMessageBox.warning(
                self, "无 Mod 目录",
                "未配置 Mod 目录。请先在「软件设置」填游戏目录，或点「配置 Mod 目录」添加。")
            return
        if self._worker and self._worker.isRunning():
            return
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self.index_status.setText("扫描中…（mod 多时较慢，请耐心等待）")
        log(f"建立 Mod 索引，目录: {dirs}")

        def job(progress=None):
            idx = mod_index.ModIndex().build(dirs, progress=lambda c, f: progress(c, 0, f) if progress else None)
            idx.save(_INDEX_CACHE)
            return idx

        self._worker = Worker(job)
        self._worker.progress.connect(lambda c, t, f: self.index_status.setText(f"扫描中… 已处理 {c}  {Path(f).name}"))
        self._worker.finished_ok.connect(self._on_indexed)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_indexed(self, idx) -> None:
        self.index = idx
        self.progress.setVisible(False)
        self._refresh_index_status()
        log(f"Mod 索引完成：{idx.count} 个")
        QMessageBox.information(self, "完成", f"索引建立完成，共 {idx.count} 个 mod。")

    # ---- 检查 ----

    def _add_cards(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择角色卡", "", "角色卡 PNG (*.png)")
        for f in files:
            self.queue.addItem(f)

    def _check(self) -> None:
        if self.index.count == 0:
            QMessageBox.warning(self, "无索引", "请先建立 Mod 索引。"); return
        files = [self.queue.item(i).text() for i in range(self.queue.count())]
        if not files:
            QMessageBox.warning(self, "队列为空", "请先加入角色卡。"); return

        lines = []
        self._last_missing = {}
        for f in files:
            try:
                rep = mod_index.check_card(f, self.index)
            except Exception as exc:  # noqa: BLE001
                lines.append(f"[X] {Path(f).name}: {exc}")
                continue
            lines.append(
                f"[{'OK' if rep.missing_count == 0 else '缺'}] {Path(f).name}  "
                f"所需 {rep.required_count} | 命中 {len(rep.present)} | 缺失 {rep.missing_count}")
            if rep.missing:
                self._last_missing[f] = rep.missing
                for g in rep.missing:
                    lines.append(f"      - {g}")
        self.result.setPlainText("\n".join(lines))
        log(f"检查 {len(files)} 张卡，缺失记录 {len(self._last_missing)} 张")

    def _export_missing(self) -> None:
        if not self._last_missing:
            QMessageBox.information(self, "无缺失", "没有缺失记录可导出（先检查队列）。"); return
        path, _ = QFileDialog.getSaveFileName(self, "导出缺失清单", "missing_mods.txt", "文本 (*.txt)")
        if not path:
            return
        out = []
        for card, miss in self._last_missing.items():
            out.append(f"# {Path(card).name}")
            out.extend(miss)
            out.append("")
        Path(path).write_text("\n".join(out), encoding="utf-8")
        log(f"导出缺失清单: {path}")
        QMessageBox.information(self, "已导出", f"已导出到:\n{path}")

    def _on_failed(self, msg) -> None:
        self.progress.setVisible(False)
        self.index_status.setText("索引失败")
        QMessageBox.critical(self, "失败", msg.splitlines()[0])
