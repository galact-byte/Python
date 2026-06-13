"""分享整理导入页：把角色卡与其依赖 mod 一起打包成分享包。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core import mod_index, settings, share
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


class SharePage(PageBase):
    def __init__(self):
        super().__init__("分享整理导入", "把角色卡与其依赖的 mod 一起打包成分享包")
        self._worker: Worker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("生成分享包"))
        v.addWidget(hint("依赖的 mod 取自 Mod 仓库索引；缺失的会记录在分享包的 README。请先在「Mod 仓库」建好索引。"))

        self.queue = _CardDropList()
        v.addWidget(self.queue, 1)
        row = QHBoxLayout()
        b_add = QPushButton("加入角色卡"); b_add.clicked.connect(self._add)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.queue.clear)
        row.addWidget(b_add); row.addWidget(b_clr); row.addStretch(1)
        v.addLayout(row)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit(settings.get("output_dir", "") or "")
        self.out_edit.setPlaceholderText("分享包输出目录")
        b_out = QPushButton("…"); b_out.setFixedWidth(34)
        b_out.clicked.connect(self._pick_out)
        out_row.addWidget(QLabel("输出")); out_row.addWidget(self.out_edit, 1); out_row.addWidget(b_out)
        v.addLayout(out_row)

        self.chk_group = QCheckBox("按角色分组（每张卡一个子目录）"); self.chk_group.setChecked(True)
        v.addWidget(self.chk_group)

        b_go = QPushButton("生成分享包"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._build)
        v.addWidget(b_go)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        v.addWidget(self.progress)
        self.result = QPlainTextEdit(); self.result.setReadOnly(True); self.result.setMaximumHeight(160)
        v.addWidget(self.result)
        self.body_layout.addWidget(card, 1)

    def _add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择角色卡", "", "角色卡 PNG (*.png)")
        for f in files:
            self.queue.addItem(f)

    def _pick_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self.out_edit.text() or "")
        if d:
            self.out_edit.setText(d)

    def _build(self) -> None:
        files = [self.queue.item(i).text() for i in range(self.queue.count())]
        out = self.out_edit.text().strip()
        if not files:
            QMessageBox.warning(self, "队列为空", "请先加入角色卡。"); return
        if not out:
            QMessageBox.warning(self, "无输出目录", "请选择输出目录。"); return
        index = mod_index.ModIndex.load(_INDEX_CACHE)
        if index.count == 0:
            ret = QMessageBox.question(
                self, "索引为空",
                "尚未建立 Mod 索引，分享包将只含卡片、不含 mod。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        settings.set_value("output_dir", out)
        group = self.chk_group.isChecked()

        def job(progress=None):
            return share.build_share_package(files, index, out, group_by_char=group, progress=progress)

        if self._worker and self._worker.isRunning():
            return
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        log(f"生成分享包: {len(files)} 张卡 -> {out}")
        self._worker = Worker(job)
        self._worker.progress.connect(lambda c, t, d: (self.progress.setRange(0, t), self.progress.setValue(c)) if t else None)
        self._worker.finished_ok.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _done(self, report: dict) -> None:
        self.progress.setVisible(False)
        lines = [f"完成：{len(report['cards'])} 张卡",
                 f"复制 mod 种类: {len(report['copied_mods'])}",
                 f"总缺失 mod: {len(report['total_missing'])}", ""]
        for c in report["cards"]:
            lines.append(f"[{c['name']}] 依赖{c['required']} 含{c['copied']} 缺{len(c['missing'])}")
        self.result.setPlainText("\n".join(lines))
        log("分享包生成完成")
        QMessageBox.information(self, "完成", "分享包已生成，详见输出目录的 README.txt。")

    def _failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        QMessageBox.critical(self, "失败", msg.splitlines()[0])
