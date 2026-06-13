"""解包 / 打包 / 隐写伪装 / 分卷 页。

左：解包（含识别伪装在视频后的压缩包）。右：把文件夹打包并伪装成载体文件，可分卷。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import settings, stego
from ui.applog import log
from ui.widgets import PageBase, hint, make_card, section_title
from ui.worker import Worker


class _DropList(QListWidget):
    """接受拖入文件的列表。"""

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p and Path(p).is_file():
                self.addItem(p)


class PackPage(PageBase):
    def __init__(self):
        super().__init__("解包 / 打包", "压缩、伪装隐写、分卷处理")
        self._worker: Worker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._build_unpack(), 1)
        cols.addWidget(self._build_pack(), 1)
        self.body_layout.addLayout(cols, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

    # ---- 解包 ----

    def _build_unpack(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("解包"))
        v.addWidget(hint("拖入或选择压缩包 / 伪装文件（视频后接 zip 也能识别），解压到输出目录。"))
        self.unpack_list = _DropList()
        v.addWidget(self.unpack_list, 1)
        row = QHBoxLayout()
        b_add = QPushButton("选择文件"); b_add.clicked.connect(self._add_unpack)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.unpack_list.clear)
        row.addWidget(b_add); row.addWidget(b_clr); row.addStretch(1)
        v.addLayout(row)
        out = QHBoxLayout()
        self.unpack_out = QLineEdit(settings.get("output_dir", "") or "")
        self.unpack_out.setPlaceholderText("解包输出目录")
        b_out = QPushButton("…"); b_out.setFixedWidth(34)
        b_out.clicked.connect(lambda: self._pick_dir(self.unpack_out))
        out.addWidget(QLabel("输出")); out.addWidget(self.unpack_out, 1); out.addWidget(b_out)
        v.addLayout(out)
        b_go = QPushButton("开始解包"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._do_unpack)
        v.addWidget(b_go)
        return card

    def _add_unpack(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择压缩包/伪装文件", "", "所有文件 (*.*)")
        for f in files:
            self.unpack_list.addItem(f)

    def _do_unpack(self) -> None:
        files = [self.unpack_list.item(i).text() for i in range(self.unpack_list.count())]
        out = self.unpack_out.text().strip()
        if not files:
            QMessageBox.warning(self, "无文件", "请先添加要解包的文件。")
            return
        if not out:
            QMessageBox.warning(self, "无输出目录", "请选择解包输出目录。")
            return
        settings.set_value("output_dir", out)

        def job(progress=None):
            results = []
            for idx, f in enumerate(files, 1):
                if not stego.looks_like_zip(f):
                    results.append(f"[跳过] 非压缩包: {Path(f).name}")
                    continue
                sub = Path(out) / Path(f).stem
                names = stego.extract_archive(f, sub)
                results.append(f"[OK] {Path(f).name} -> {len(names)} 个文件")
                if progress:
                    progress(idx, len(files), Path(f).name)
            return results

        self._run(job, "解包")

    # ---- 打包伪装 ----

    def _build_pack(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("打包并伪装"))
        v.addWidget(hint("把文件夹压缩后追加到一个真实视频/图片之后，生成既能播放又能解压的伪装文件。"))

        self.pack_folder = self._path_row(v, "待打包文件夹", pick_dir=True)
        self.pack_carrier = self._path_row(v, "载体文件(视频/图片)", pick_dir=False)
        self.pack_out = self._path_row(v, "输出文件", pick_dir=False, save=True)

        split_row = QHBoxLayout()
        split_row.addWidget(QLabel("分卷大小(MB，0=不分卷)"))
        self.split_size = QDoubleSpinBox()
        self.split_size.setRange(0, 100000); self.split_size.setValue(0); self.split_size.setDecimals(0)
        split_row.addWidget(self.split_size); split_row.addStretch(1)
        v.addLayout(split_row)

        b_go = QPushButton("开始打包伪装"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._do_pack)
        v.addWidget(b_go)
        v.addStretch(1)
        return card

    def _path_row(self, parent, label, *, pick_dir, save=False) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        b = QPushButton("…"); b.setFixedWidth(34)

        def pick():
            if pick_dir:
                d = QFileDialog.getExistingDirectory(self, label)
            elif save:
                d, _ = QFileDialog.getSaveFileName(self, label)
            else:
                d, _ = QFileDialog.getOpenFileName(self, label)
            if d:
                edit.setText(d)

        b.clicked.connect(pick)
        row.addWidget(QLabel(label))
        row.addWidget(edit, 1)
        row.addWidget(b)
        parent.addLayout(row)
        return edit

    def _do_pack(self) -> None:
        folder = self.pack_folder.text().strip()
        carrier = self.pack_carrier.text().strip()
        out = self.pack_out.text().strip()
        if not (folder and Path(folder).is_dir()):
            QMessageBox.warning(self, "无效", "请选择有效的待打包文件夹。"); return
        if not (carrier and Path(carrier).is_file()):
            QMessageBox.warning(self, "无效", "请选择有效的载体文件。"); return
        if not out:
            QMessageBox.warning(self, "无效", "请指定输出文件路径。"); return
        split_mb = self.split_size.value()

        def job(progress=None):
            stego.pack_and_disguise(folder, carrier, out, progress=progress)
            msgs = [f"[OK] 已伪装: {Path(out).name}"]
            if split_mb > 0:
                parts = stego.split_file(out, split_mb)
                msgs.append(f"[OK] 已分卷为 {len(parts)} 个分片")
            return msgs

        self._run(job, "打包伪装")

    # ---- 公共执行 ----

    def _pick_dir(self, edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择目录", edit.text() or "")
        if d:
            edit.setText(d)

    def _run(self, job, label: str) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "已有任务进行中。"); return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        log(f"{label} 开始")
        self._worker = Worker(job)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(lambda res: self._on_done(label, res))
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, cur, total, desc) -> None:
        if total:
            self.progress.setRange(0, total); self.progress.setValue(cur)

    def _on_done(self, label, results) -> None:
        self.progress.setVisible(False)
        for r in results:
            log(r)
        QMessageBox.information(self, f"{label}完成", "\n".join(results))

    def _on_failed(self, msg) -> None:
        self.progress.setVisible(False)
        log(f"任务失败: {msg.splitlines()[0]}")
        QMessageBox.critical(self, "失败", msg.splitlines()[0])
