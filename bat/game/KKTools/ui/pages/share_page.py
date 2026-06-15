"""分享整理导入页：生成分享包 / 导入恢复 / 整理 / 离线对账 四个标签页。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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


def _dir_row(parent_layout, label: str, default: str = "") -> QLineEdit:
    row = QHBoxLayout()
    edit = QLineEdit(default)
    b = QPushButton("…"); b.setFixedWidth(34)

    def pick():
        d = QFileDialog.getExistingDirectory(None, label, edit.text() or "")
        if d:
            edit.setText(d)

    b.clicked.connect(pick)
    row.addWidget(QLabel(label)); row.addWidget(edit, 1); row.addWidget(b)
    parent_layout.addLayout(row)
    return edit


class SharePage(PageBase):
    def __init__(self):
        super().__init__("分享整理导入", "生成分享包、导入恢复、整理文件、离线对账")
        self._worker: Worker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_generate_tab(), "生成分享包")
        tabs.addTab(self._build_restore_tab(), "导入 / 恢复")
        tabs.addTab(self._build_organize_tab(), "整理")
        tabs.addTab(self._build_reconcile_tab(), "离线对账")
        self.body_layout.addWidget(tabs, 1)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

    # ---------- 生成分享包 ----------

    def _build_generate_tab(self) -> QWidget:
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
        self.out_edit = _dir_row(v, "输出目录", settings.get("output_dir", "") or "")
        self.chk_group = QCheckBox("按角色分组（每张卡一个子目录）"); self.chk_group.setChecked(True)
        v.addWidget(self.chk_group)
        b_go = QPushButton("生成分享包"); b_go.setProperty("accent", "primary")
        b_go.clicked.connect(self._build)
        v.addWidget(b_go)
        self.result = QPlainTextEdit(); self.result.setReadOnly(True); self.result.setMaximumHeight(140)
        v.addWidget(self.result)
        return card

    def _add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择角色卡", "", "角色卡 PNG (*.png)")
        for f in files:
            self.queue.addItem(f)

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

        self._run(job, self._on_built)

    def _on_built(self, report: dict) -> None:
        self.progress.setVisible(False)
        lines = [f"完成：{len(report['cards'])} 张卡",
                 f"复制 mod 种类: {len(report['copied_mods'])}",
                 f"总缺失 mod: {len(report['total_missing'])}", ""]
        for c in report["cards"]:
            lines.append(f"[{c['name']}] 依赖{c['required']} 含{c['copied']} 缺{len(c['missing'])}")
        self.result.setPlainText("\n".join(lines))
        log("分享包生成完成")
        QMessageBox.information(self, "完成", "分享包已生成，详见输出目录的 README.txt。")

    # ---------- 导入 / 恢复 ----------

    def _build_restore_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("导入 / 恢复分享包"))
        v.addWidget(hint("从分享包(或任意含卡片/zipmod 的目录)把卡片复制回游戏角色目录、mod 复制回游戏 mods 目录。已存在同名则跳过。"))
        self.rs_pkg = _dir_row(v, "分享包目录")
        self.rs_card = _dir_row(v, "卡片目标目录")
        self.rs_mod = _dir_row(v, "Mod 目标目录(可空)")
        b = QPushButton("开始导入 / 恢复"); b.setProperty("accent", "primary")
        b.clicked.connect(self._do_restore)
        v.addWidget(b)
        self.rs_result = QPlainTextEdit(); self.rs_result.setReadOnly(True); self.rs_result.setMaximumHeight(120)
        v.addWidget(self.rs_result)
        v.addStretch(1)
        return card

    def _do_restore(self) -> None:
        pkg = self.rs_pkg.text().strip()
        card_t = self.rs_card.text().strip()
        mod_t = self.rs_mod.text().strip() or None
        if not (pkg and Path(pkg).is_dir()):
            QMessageBox.warning(self, "无效", "请选择有效的分享包目录。"); return
        if not card_t:
            QMessageBox.warning(self, "无效", "请选择卡片目标目录。"); return

        def job(progress=None):
            return share.restore_package(pkg, card_t, mod_t, progress=progress)

        def done(r):
            self.progress.setVisible(False)
            self.rs_result.setPlainText(
                f"恢复完成：\n卡片 复制 {r['cards']} / 跳过 {r['cards_skipped']}\n"
                f"Mod 复制 {r['mods']} / 跳过 {r['mods_skipped']}")
            log(f"导入恢复完成: {r}")
            QMessageBox.information(self, "完成", "导入 / 恢复完成。")

        self._run(job, done)

    # ---------- 整理 ----------

    def _build_organize_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("整理卡片"))
        v.addWidget(hint("扫描卡片目录，按类型或角色名归类到输出目录。默认复制(不动原目录)。"))
        self.or_src = _dir_row(v, "卡片源目录")
        self.or_out = _dir_row(v, "整理输出目录")
        opt = QHBoxLayout()
        self.or_by = QComboBox(); self.or_by.addItem("按类型", "type"); self.or_by.addItem("按角色名", "character")
        self.or_move = QCheckBox("移动(而非复制)")
        opt.addWidget(QLabel("方式")); opt.addWidget(self.or_by); opt.addWidget(self.or_move); opt.addStretch(1)
        v.addLayout(opt)
        b = QPushButton("开始整理"); b.setProperty("accent", "primary")
        b.clicked.connect(self._do_organize)
        v.addWidget(b)
        self.or_result = QPlainTextEdit(); self.or_result.setReadOnly(True); self.or_result.setMaximumHeight(100)
        v.addWidget(self.or_result)
        v.addStretch(1)
        return card

    def _do_organize(self) -> None:
        src = self.or_src.text().strip()
        out = self.or_out.text().strip()
        if not (src and Path(src).is_dir()):
            QMessageBox.warning(self, "无效", "请选择有效的卡片源目录。"); return
        if not out:
            QMessageBox.warning(self, "无效", "请选择整理输出目录。"); return
        by = self.or_by.currentData()
        move = self.or_move.isChecked()

        def job(progress=None):
            return share.organize_cards(src, out, by=by, move=move, progress=progress)

        def done(r):
            self.progress.setVisible(False)
            self.or_result.setPlainText(
                f"整理完成（{'移动' if r['move'] else '复制'}/{r['by']}）：处理 {r['processed']}，归类 {r['organized']}。")
            log(f"整理完成: {r}")
            QMessageBox.information(self, "完成", "整理完成。")

        self._run(job, done)

    # ---------- 离线对账 ----------

    def _build_reconcile_tab(self) -> QWidget:
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("离线对账"))
        v.addWidget(hint("比对两个目录的文件(按文件名)，列出只在A/只在B/共有，便于核对 mod 或卡片差异。"))
        self.rc_a = _dir_row(v, "目录 A")
        self.rc_b = _dir_row(v, "目录 B")
        b = QPushButton("开始对账"); b.setProperty("accent", "primary")
        b.clicked.connect(self._do_reconcile)
        v.addWidget(b)
        self.rc_result = QPlainTextEdit(); self.rc_result.setReadOnly(True)
        v.addWidget(self.rc_result, 1)
        return card

    def _do_reconcile(self) -> None:
        a = self.rc_a.text().strip(); b = self.rc_b.text().strip()
        if not (a and Path(a).is_dir() and b and Path(b).is_dir()):
            QMessageBox.warning(self, "无效", "请选择两个有效目录。"); return
        rec = share.reconcile_dirs(a, b)
        lines = [
            f"目录A: {rec['count_a']} 个文件   目录B: {rec['count_b']} 个文件   共有: {rec['both']}",
            "",
            f"[只在 A，共 {len(rec['only_a'])}]",
        ]
        lines += [f"  {n}" for n in rec["only_a"][:300]]
        lines += ["", f"[只在 B，共 {len(rec['only_b'])}]"]
        lines += [f"  {n}" for n in rec["only_b"][:300]]
        self.rc_result.setPlainText("\n".join(lines))
        log(f"离线对账: A{rec['count_a']} B{rec['count_b']} 只在A{len(rec['only_a'])} 只在B{len(rec['only_b'])}")

    # ---------- 公共后台执行 ----------

    def _run(self, job, on_done) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "已有任务进行中。"); return
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self._worker = Worker(job)
        self._worker.progress.connect(
            lambda c, t, d: (self.progress.setRange(0, t), self.progress.setValue(c)) if t else None)
        self._worker.finished_ok.connect(on_done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        QMessageBox.critical(self, "失败", msg.splitlines()[0])
