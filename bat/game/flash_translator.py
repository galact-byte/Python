import sys
import re
import json
import os
import struct
import zlib
import subprocess
import configparser
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QTabWidget,
    QFrame, QProgressBar, QLineEdit, QMessageBox,
    QGroupBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor

CONFIG_FILE = Path.home() / ".flash_translator_config.ini"

# ── 样式表 ──────────────────────────────────────────────────────────────
STYLE = """
QMainWindow, QWidget {
    background-color: #0f0f14;
    color: #e0deff;
    font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
}
QTabWidget::pane {
    border: 1px solid #2a2a3d;
    border-radius: 8px;
    background: #15151f;
}
QTabBar::tab {
    background: #1a1a28;
    color: #7878aa;
    padding: 10px 24px;
    border: none;
    font-size: 13px;
    letter-spacing: 1px;
}
QTabBar::tab:selected {
    background: #15151f;
    color: #c8b4ff;
    border-top: 2px solid #7c5cbf;
}
QTabBar::tab:hover:!selected { color: #a090cc; }

QPushButton {
    background: #1e1e30;
    color: #c8b4ff;
    border: 1px solid #3a3a58;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
}
QPushButton:hover {
    background: #2a2a45;
    border-color: #7c5cbf;
    color: #e0d0ff;
}
QPushButton:pressed { background: #7c5cbf; color: #fff; }
QPushButton#action_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #5c3d9e, stop:1 #7c5cbf);
    color: #fff;
    border: none;
    font-size: 14px;
    font-weight: bold;
    padding: 12px 30px;
    border-radius: 8px;
    letter-spacing: 1px;
}
QPushButton#action_btn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #6e4db8, stop:1 #9070d8);
}
QPushButton#action_btn:disabled { background: #2a2a40; color: #555570; }

QTextEdit, QLineEdit {
    background: #0d0d18;
    color: #a0a0cc;
    border: 1px solid #2a2a3d;
    border-radius: 6px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 6px 8px;
}
QLineEdit {
    font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
}

QListWidget {
    background: #0d0d18;
    color: #a0a0cc;
    border: 1px solid #2a2a3d;
    border-radius: 6px;
    font-size: 12px;
    padding: 4px;
}
QListWidget::item { padding: 5px 8px; border-radius: 4px; }
QListWidget::item:selected { background: #2a1a4a; color: #c8b4ff; }
QListWidget::item:hover { background: #1a1a30; }

QProgressBar {
    background: #1a1a28;
    border: 1px solid #2a2a3d;
    border-radius: 4px;
    height: 6px;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #5c3d9e, stop:1 #9070d8);
    border-radius: 4px;
}

QGroupBox {
    border: 1px solid #2a2a3d;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    font-size: 12px;
    color: #7070aa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

QLabel#title { font-size: 22px; font-weight: bold; color: #c8b4ff; letter-spacing: 2px; }
QLabel#subtitle { font-size: 11px; color: #555580; letter-spacing: 3px; }
QLabel#path_label {
    background: #0d0d18; color: #7070aa;
    border: 1px solid #2a2a3d; border-radius: 6px;
    padding: 6px 10px; font-size: 12px;
}
QLabel#status { color: #7878aa; font-size: 12px; }
QFrame#separator { background: #2a2a3d; max-height: 1px; }
QFrame#drop_zone {
    background: #0d0d18;
    border: 2px dashed #3a3a58;
    border-radius: 10px;
}
"""

# ── 配置存取 ─────────────────────────────────────────────────────────────
def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding='utf-8')
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        cfg.write(f)

def get_ffdec_path():
    return load_config().get('paths', 'ffdec', fallback='')

def set_ffdec_path(path):
    cfg = load_config()
    if 'paths' not in cfg:
        cfg['paths'] = {}
    cfg['paths']['ffdec'] = path
    save_config(cfg)

# ── SWF 字体检测 ─────────────────────────────────────────────────────────
CN_KEYWORDS = ['cjk','chinese','cn','sc','tc','gb','雅黑','宋体','黑体',
               'noto','sourchan','pingfang','simsun','simhei','microsoftyahei']

def is_likely_cn(name):
    low = name.lower().replace(' ','').replace('-','')
    return any(k in low for k in CN_KEYWORDS)

def read_swf_fonts(swf_path):
    fonts = []
    try:
        with open(swf_path, 'rb') as f:
            header = f.read(8)
        sig = header[:3]
        with open(swf_path, 'rb') as f:
            f.seek(8)
            raw = f.read()
        if sig == b'CWS':
            data = zlib.decompress(raw)
        elif sig == b'FWS':
            data = raw
        else:
            return [], "不是有效的 SWF 文件"

        i = 0
        while i < len(data) - 2:
            tl = struct.unpack_from('<H', data, i)[0]
            tag_type = (tl >> 6) & 0x3FF
            length = tl & 0x3F
            i += 2
            if length == 0x3F:
                length = struct.unpack_from('<I', data, i)[0]
                i += 4

            chunk = data[i:i+length]

            # DefineFontName tag=88
            if tag_type == 88 and length > 2:
                try:
                    end = chunk.find(b'\x00', 2)
                    if end > 2:
                        name = chunk[2:end].decode('utf-8', errors='ignore')
                        if name and name not in fonts:
                            fonts.append(name)
                except Exception:
                    pass

            # DefineFont2=48 / DefineFont3=75
            if tag_type in (48, 75) and length > 6:
                try:
                    name_len = chunk[5]
                    if name_len > 0:
                        name = chunk[6:6+name_len].decode('utf-8', errors='ignore').rstrip('\x00')
                        if name and name not in fonts:
                            fonts.append(name)
                except Exception:
                    pass

            i += length
    except Exception as e:
        return [], str(e)
    return fonts, None

# ── 拖拽区域 ─────────────────────────────────────────────────────────────
class DropZone(QFrame):
    from PyQt6.QtCore import pyqtSignal
    file_dropped = pyqtSignal(str)

    def __init__(self, label_text, extensions, parent=None):
        super().__init__(parent)
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self.extensions = [e.lower() for e in extensions]
        self.setMinimumHeight(80)

        from PyQt6.QtWidgets import QVBoxLayout
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon = QLabel("📂")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setStyleSheet("font-size:22px; border:none; background:transparent;")
        self.text = QLabel(label_text)
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setStyleSheet("color:#555580; font-size:12px; border:none; background:transparent;")
        lay.addWidget(self.icon)
        lay.addWidget(self.text)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            url = e.mimeData().urls()[0].toLocalFile().lower()
            if any(url.endswith(x) for x in self.extensions):
                e.acceptProposedAction()
                self.setStyleSheet(
                    "QFrame#drop_zone{background:#1a1230;border:2px dashed #7c5cbf;border-radius:10px;}")

    def dragLeaveEvent(self, e):
        self.setStyleSheet("")

    def dropEvent(self, e: QDropEvent):
        self.setStyleSheet("")
        path = e.mimeData().urls()[0].toLocalFile()
        self.file_dropped.emit(path)
        self.text.setText(Path(path).name)
        self.text.setStyleSheet(
            "color:#c8b4ff; font-size:12px; border:none; background:transparent;")

# ── FFDec 路径组件（共享） ────────────────────────────────────────────────
class FFDecWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("FFDec 路径设置", parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 10)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(
            "FFDec 安装目录，例如：D:\\BaiduNetdiskDownload\\GameTools\\ffdec_25.1.3")
        saved = get_ffdec_path()
        if saved:
            self.edit.setText(saved)
        self.edit.textChanged.connect(self._changed)

        btn = QPushButton("浏览")
        btn.setFixedWidth(70)
        btn.clicked.connect(self._browse)

        self.tag = QLabel()
        self.tag.setFixedWidth(56)
        self._validate(saved)

        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)
        lay.addWidget(self.tag)

    def _browse(self):
        p = QFileDialog.getExistingDirectory(self, "选择 FFDec 目录")
        if p:
            self.edit.setText(p)

    def _changed(self, text):
        set_ffdec_path(text)
        self._validate(text)

    def _validate(self, path):
        if not path:
            self.tag.setText("")
            return
        p = Path(path)
        ok = (p / "ffdec.jar").exists() or (p / "ffdec.bat").exists()
        if ok:
            self.tag.setText("✓ 有效")
            self.tag.setStyleSheet("color:#70d4a0; font-size:11px; font-weight:bold;")
        else:
            self.tag.setText("✗ 无效")
            self.tag.setStyleSheet("color:#d47070; font-size:11px; font-weight:bold;")

    def get_ffdec(self):
        """返回 (路径, 类型) 或 (None, None)"""
        p = Path(self.edit.text().strip())
        for name, t in [("ffdec.jar", "jar"), ("ffdec.bat", "bat")]:
            f = p / name
            if f.exists():
                return str(f), t
        return None, None

# ── 提取页 ───────────────────────────────────────────────────────────────
class ExtractTab(QWidget):
    def __init__(self):
        super().__init__()
        self.as_path = ""
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 16, 20, 16)

        lay.addWidget(QLabel("从 ActionScript (.as) 文件中提取日文字符串，生成 Mtool 格式 JSON",
                             styleSheet="color:#606088; font-size:12px;"))
        sep = QFrame(); sep.setObjectName("separator"); lay.addWidget(sep)

        self.drop = DropZone("拖入 .as 文件，或点击下方按钮选择", [".as"])
        self.drop.file_dropped.connect(self._set)
        lay.addWidget(self.drop)

        row = QHBoxLayout()
        btn = QPushButton("选择 .as 文件"); btn.clicked.connect(self._pick)
        self.plbl = QLabel("未选择"); self.plbl.setObjectName("path_label")
        self.plbl.setWordWrap(True)
        row.addWidget(btn); row.addWidget(self.plbl, 1)
        lay.addLayout(row)

        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setPlaceholderText("操作日志...")
        lay.addWidget(self.log)

        self.prog = QProgressBar(); self.prog.setVisible(False)
        lay.addWidget(self.prog)

        self.btn_run = QPushButton("提取日文 → 生成 JSON")
        self.btn_run.setObjectName("action_btn")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run)
        lay.addWidget(self.btn_run)

    def _set(self, p):
        self.as_path = p; self.plbl.setText(p); self.btn_run.setEnabled(True)

    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 AS 文件", "", "ActionScript (*.as)")
        if p: self._set(p)

    def _run(self):
        sp, _ = QFileDialog.getSaveFileName(self, "保存 JSON", "mtool_export.json", "JSON (*.json)")
        if not sp: return
        self.btn_run.setEnabled(False); self.prog.setVisible(True); self.prog.setRange(0,0)
        self.log.clear()
        try:
            content = open(self.as_path, encoding='utf-8').read()
            matches = re.findall(r'"([^"]*[ぁ-んァ-ン一-龥][^"]*)"', content)
            seen, unique = set(), []
            for m in matches:
                if m not in seen: seen.add(m); unique.append(m)
            result = {m: "" for m in unique}
            json.dump(result, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            self.log.append(f"✅ 完成！提取 {len(unique)} 条（原始匹配 {len(matches)} 条）")
            self.log.append(f"📄 已保存：{sp}\n\n前5条预览：")
            for k in list(result)[:5]: self.log.append(f"  · {k}")
        except Exception as e:
            self.log.append(f"❌ 错误：{e}")
        self.prog.setVisible(False); self.prog.setRange(0,100); self.btn_run.setEnabled(True)

# ── 回填页 ───────────────────────────────────────────────────────────────
class InjectTab(QWidget):
    def __init__(self):
        super().__init__()
        self.as_path = self.json_path = ""
        lay = QVBoxLayout(self)
        lay.setSpacing(12); lay.setContentsMargins(20,16,20,16)

        lay.addWidget(QLabel("将翻译完成的 JSON 回填进原始 .as 文件，生成汉化版",
                             styleSheet="color:#606088; font-size:12px;"))
        sep = QFrame(); sep.setObjectName("separator"); lay.addWidget(sep)

        dr = QHBoxLayout(); dr.setSpacing(10)
        self.d_as = DropZone("拖入原始 .as 文件", [".as"])
        self.d_as.file_dropped.connect(self._set_as)
        self.d_json = DropZone("拖入翻译完成的 .json", [".json"])
        self.d_json.file_dropped.connect(self._set_json)
        dr.addWidget(self.d_as); dr.addWidget(self.d_json)
        lay.addLayout(dr)

        for attr, txt, fn in [('las','选择 .as 文件',self._pick_as),
                               ('ljson','选择 .json 文件',self._pick_json)]:
            row = QHBoxLayout()
            btn = QPushButton(txt); btn.clicked.connect(fn)
            lbl = QLabel("未选择"); lbl.setObjectName("path_label")
            setattr(self, attr, lbl)
            row.addWidget(btn); row.addWidget(lbl, 1)
            lay.addLayout(row)

        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setPlaceholderText("操作日志...")
        lay.addWidget(self.log)

        self.prog = QProgressBar(); self.prog.setVisible(False)
        lay.addWidget(self.prog)

        self.btn_run = QPushButton("回填中文 → 生成汉化 .as")
        self.btn_run.setObjectName("action_btn"); self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run)
        lay.addWidget(self.btn_run)

    def _ready(self): self.btn_run.setEnabled(bool(self.as_path and self.json_path))
    def _set_as(self, p): self.as_path=p; self.las.setText(p); self._ready()
    def _set_json(self, p): self.json_path=p; self.ljson.setText(p); self._ready()
    def _pick_as(self):
        p,_ = QFileDialog.getOpenFileName(self,"选择 AS 文件","","ActionScript (*.as)")
        if p: self._set_as(p)
    def _pick_json(self):
        p,_ = QFileDialog.getOpenFileName(self,"选择 JSON","","JSON (*.json)")
        if p: self._set_json(p)

    def _run(self):
        sp,_ = QFileDialog.getSaveFileName(self,"保存汉化 AS","MainTimeline_CN.as","ActionScript (*.as)")
        if not sp: return
        self.btn_run.setEnabled(False); self.prog.setVisible(True); self.prog.setRange(0,0)
        self.log.clear()
        try:
            content = open(self.as_path, encoding='utf-8').read()
            trans = json.load(open(self.json_path, encoding='utf-8'))
            replaced = skipped = 0
            for jp, cn in trans.items():
                if not cn or not cn.strip(): skipped+=1; continue
                new = re.sub(f'"{re.escape(jp)}"', f'"{cn}"', content)
                if new != content: replaced+=1; content=new
            open(sp,'w',encoding='utf-8').write(content)
            self.log.append(f"✅ 完成！回填 {replaced} 条")
            if skipped: self.log.append(f"⚠️  跳过 {skipped} 条空翻译")
            self.log.append(f"📄 已保存：{sp}")
            self.log.append("\n完成后请用 FFDec → Edit ActionScript 导入此文件。")
        except Exception as e:
            self.log.append(f"❌ 错误：{e}")
        self.prog.setVisible(False); self.prog.setRange(0,100); self.btn_run.setEnabled(True)

# ── 字体页 ───────────────────────────────────────────────────────────────
class FontTab(QWidget):
    def __init__(self, ffdec: FFDecWidget):
        super().__init__()
        self.ffdec = ffdec
        self.swf_path = self.ttf_path = ""
        self.fonts = []
        lay = QVBoxLayout(self)
        lay.setSpacing(12); lay.setContentsMargins(20,16,20,16)

        lay.addWidget(QLabel("检测 SWF 内嵌字体，并替换为支持中文的字体（需要 FFDec + Java）",
                             styleSheet="color:#606088; font-size:12px;"))
        sep = QFrame(); sep.setObjectName("separator"); lay.addWidget(sep)

        # SWF 选择行
        r1 = QHBoxLayout(); r1.setSpacing(10)
        self.d_swf = DropZone("拖入 SWF 文件", [".swf"])
        self.d_swf.setMinimumHeight(72); self.d_swf.setMaximumHeight(72)
        self.d_swf.file_dropped.connect(self._set_swf)
        r1.addWidget(self.d_swf, 2)
        col = QVBoxLayout()
        b_swf = QPushButton("选择 SWF"); b_swf.clicked.connect(self._pick_swf)
        self.l_swf = QLabel("未选择"); self.l_swf.setObjectName("path_label")
        col.addWidget(b_swf); col.addWidget(self.l_swf)
        r1.addLayout(col, 3)
        lay.addLayout(r1)

        self.btn_detect = QPushButton("🔍  检测 SWF 内嵌字体")
        self.btn_detect.setEnabled(False)
        self.btn_detect.clicked.connect(self._detect)
        lay.addWidget(self.btn_detect)

        grp = QGroupBox("检测到的字体（橙色 = 需替换，绿色 = 已支持中文）")
        gl = QVBoxLayout(grp)
        self.font_list = QListWidget(); self.font_list.setMaximumHeight(110)
        gl.addWidget(self.font_list)
        lay.addWidget(grp)

        sep2 = QFrame(); sep2.setObjectName("separator"); lay.addWidget(sep2)

        lay.addWidget(QLabel("选择替换用的中文字体（.ttf / .otf）",
                             styleSheet="color:#9090bb; font-size:12px;"))

        r2 = QHBoxLayout(); r2.setSpacing(10)
        self.d_ttf = DropZone("拖入字体文件", [".ttf",".otf"])
        self.d_ttf.setMinimumHeight(62); self.d_ttf.setMaximumHeight(62)
        self.d_ttf.file_dropped.connect(self._set_ttf)
        r2.addWidget(self.d_ttf, 2)
        col2 = QVBoxLayout()
        b_ttf = QPushButton("选择字体文件"); b_ttf.clicked.connect(self._pick_ttf)
        self.l_ttf = QLabel("未选择"); self.l_ttf.setObjectName("path_label")
        col2.addWidget(b_ttf); col2.addWidget(self.l_ttf)
        r2.addLayout(col2, 3)
        lay.addLayout(r2)

        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setPlaceholderText("操作日志..."); self.log.setMaximumHeight(100)
        lay.addWidget(self.log)

        self.prog = QProgressBar(); self.prog.setVisible(False)
        lay.addWidget(self.prog)

        self.btn_rep = QPushButton("替换字体 → 生成新 SWF")
        self.btn_rep.setObjectName("action_btn"); self.btn_rep.setEnabled(False)
        self.btn_rep.clicked.connect(self._replace)
        lay.addWidget(self.btn_rep)

        lay.addWidget(QLabel("💡 字体替换后，再用 FFDec 导入汉化 .as 脚本，最终导出 SWF",
                             styleSheet="color:#505070; font-size:11px;"))

    def _set_swf(self, p):
        self.swf_path=p; self.l_swf.setText(Path(p).name)
        self.btn_detect.setEnabled(True); self.font_list.clear(); self._chk()
    def _pick_swf(self):
        p,_ = QFileDialog.getOpenFileName(self,"选择 SWF","","SWF (*.swf)")
        if p: self._set_swf(p)
    def _set_ttf(self, p):
        self.ttf_path=p; self.l_ttf.setText(Path(p).name); self._chk()
    def _pick_ttf(self):
        p,_ = QFileDialog.getOpenFileName(self,"选择字体","","字体 (*.ttf *.otf)")
        if p: self._set_ttf(p)
    def _chk(self):
        self.btn_rep.setEnabled(bool(self.swf_path and self.ttf_path and self.fonts))

    def _detect(self):
        self.font_list.clear(); self.fonts=[]; self.log.clear()
        fonts, err = read_swf_fonts(self.swf_path)
        if err:
            self.log.append(f"❌ 解析失败：{err}"); return
        if not fonts:
            self.log.append("⚠️  未检测到内嵌字体（可能使用设备字体）"); return
        self.fonts = fonts
        self.log.append(f"✅ 检测到 {len(fonts)} 个内嵌字体：")
        for name in fonts:
            item = QListWidgetItem()
            cn = is_likely_cn(name)
            item.setText(f"  {'✓' if cn else '✗'}  {name}  —  {'已支持中文' if cn else '建议替换'}")
            item.setForeground(QColor('#70d4a0' if cn else '#d4a070'))
            self.font_list.addItem(item)
        self._chk()

    def _replace(self):
        fpath, ftype = self.ffdec.get_ffdec()
        if not fpath:
            QMessageBox.warning(self, "FFDec 未配置",
                "请先在【设置】标签页配置正确的 FFDec 目录。"); return

        sp,_ = QFileDialog.getSaveFileName(self,"保存替换后的 SWF","output_cn.swf","SWF (*.swf)")
        if not sp: return

        self.btn_rep.setEnabled(False); self.prog.setVisible(True); self.prog.setRange(0,0)
        self.log.append("\n🔄 开始替换字体，请稍候...")

        try:
            import tempfile, shutil
            cmd_base = ['java','-jar',fpath] if ftype=='jar' else [fpath]
            tmp = tempfile.mkdtemp()
            cur = os.path.join(tmp,"step.swf")
            shutil.copy(self.swf_path, cur)
            count = 0
            for name in self.fonts:
                if is_likely_cn(name):
                    self.log.append(f"  ⏭ 跳过：{name}"); continue
                out = os.path.join(tmp, f"s{count}.swf")
                cmd = cmd_base + ['-replaceFont', cur, name, self.ttf_path, out]
                self.log.append(f"  🔧 替换：{name}")
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if r.returncode == 0 and os.path.exists(out):
                    cur = out; count += 1
                else:
                    self.log.append(f"  ⚠️  {name} 替换失败：{r.stderr[:150]}")
            shutil.copy(cur, sp)
            shutil.rmtree(tmp, ignore_errors=True)
            self.log.append(f"\n✅ 完成！替换了 {count} 个字体\n📄 已保存：{sp}")
        except FileNotFoundError:
            self.log.append("❌ 找不到 java，请确认 Java 已安装并添加到 PATH")
        except subprocess.TimeoutExpired:
            self.log.append("❌ FFDec 执行超时")
        except Exception as e:
            self.log.append(f"❌ 错误：{e}")

        self.prog.setVisible(False); self.prog.setRange(0,100); self._chk()

# ── 设置页 ───────────────────────────────────────────────────────────────
class SettingsTab(QWidget):
    def __init__(self, ffdec: FFDecWidget):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setSpacing(16); lay.setContentsMargins(20,20,20,20)
        lay.addWidget(ffdec)

        jg = QGroupBox("Java 环境检测")
        jl = QVBoxLayout(jg)
        self.jtag = QLabel("点击检测按钮")
        self.jtag.setStyleSheet("color:#7878aa; font-size:12px;")
        bj = QPushButton("检测 Java"); bj.clicked.connect(self._chk_java)
        jl.addWidget(self.jtag); jl.addWidget(bj)
        lay.addWidget(jg)

        hg = QGroupBox("完整汉化流程")
        hl = QVBoxLayout(hg)
        steps = QLabel(
            "① 提取日文   →   把 .as 拖入【提取日文】，生成 JSON\n"
            "② AI 翻译    →   把 JSON 丢给 Ainiee（选 Mtool 格式）\n"
            "③ 回填中文   →   翻译后的 JSON + 原 .as → 汉化 .as\n"
            "④ 字体替换   →   检测 SWF 字体，替换为中文字体\n"
            "⑤ 导入脚本   →   FFDec → Edit ActionScript → 导入汉化 .as\n"
            "⑥ 导出 SWF  →   FFDec 保存即可游玩"
        )
        steps.setStyleSheet("color:#707090; font-size:12px;")
        steps.setWordWrap(True)
        hl.addWidget(steps)
        lay.addWidget(hg)
        lay.addStretch()

    def _chk_java(self):
        try:
            r = subprocess.run(['java','-version'], capture_output=True, text=True, timeout=5)
            out = (r.stderr or r.stdout).strip().split('\n')[0]
            self.jtag.setText(f"✅ {out}")
            self.jtag.setStyleSheet("color:#70d4a0; font-size:12px;")
        except FileNotFoundError:
            self.jtag.setText("❌ 未找到 Java，字体替换功能需要 Java 运行环境")
            self.jtag.setStyleSheet("color:#d47070; font-size:12px;")
        except Exception as e:
            self.jtag.setText(f"⚠️  {e}")
            self.jtag.setStyleSheet("color:#d4a070; font-size:12px;")

# ── 主窗口 ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flash 游戏汉化工具")
        self.setMinimumSize(720, 640)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(14); root.setContentsMargins(24,18,24,18)

        t = QLabel("FLASH 汉化工具"); t.setObjectName("title")
        s = QLabel("EXTRACT  ·  INJECT  ·  FONT REPLACE"); s.setObjectName("subtitle")
        root.addWidget(t); root.addWidget(s)

        sep = QFrame(); sep.setObjectName("separator"); root.addWidget(sep)

        # FFDec组件由设置页和字体页共享
        self.ffdec = FFDecWidget()

        tabs = QTabWidget()
        tabs.addTab(ExtractTab(),              "提取日文")
        tabs.addTab(InjectTab(),               "回填中文")
        tabs.addTab(FontTab(self.ffdec),       "字体替换")
        tabs.addTab(SettingsTab(self.ffdec),   "设置")
        root.addWidget(tabs)

        tip = QLabel("提取 → Ainiee 翻译 → 回填 → 字体替换 → FFDec 导入 → 导出 SWF")
        tip.setObjectName("status")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tip)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    MainWindow().show()
    sys.exit(app.exec())
