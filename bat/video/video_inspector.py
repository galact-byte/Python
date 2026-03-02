"""
视频质量检测工具 - Video Quality Inspector
扫描本地视频文件，检测真实分辨率、帧率、码率等信息。
支持 Video2X AI 超分辨率(RealESRGAN/RealCUGAN) + 帧插值(RIFE) 修复。
"""

import sys
import os
import json
import re
import subprocess
from pathlib import Path

import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QFileDialog,
    QLabel, QProgressBar, QHeaderView, QCheckBox, QMenu, QDialog,
    QComboBox, QFormLayout, QDialogButtonBox, QGroupBox, QMessageBox,
    QTextEdit, QSlider, QColorDialog, QToolBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QSize
from PyQt6.QtGui import (
    QColor, QFont, QAction, QPainter, QPixmap, QBrush, QPen,
    QLinearGradient, QPalette, QIcon,
)

VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
    '.webm', '.m4v', '.ts', '.mpg', '.mpeg', '.rmvb', '.rm',
}

SETTINGS_FILE = Path(__file__).parent / "inspector_settings.json"

# ── 分辨率 / 帧率分级 ──────────────────────────────────────────────

RESOLUTION_TIERS = [
    (3840, 2160, "4K",    "#E03131"),
    (2560, 1440, "2K",    "#E8590C"),
    (1920, 1080, "1080p", "#2F9E44"),
    (1280, 720,  "720p",  "#1971C2"),
    (854,  480,  "480p",  "#7048E8"),
]

FPS_TIERS = [
    (55, "60fps", "#E03131"),
    (45, "50fps", "#E8590C"),
    (25, "30fps", "#2F9E44"),
    (20, "24fps", "#1971C2"),
]

RESOLUTION_PRESETS = {
    "4K (3840×2160)": (3840, 2160),
    "2K (2560×1440)": (2560, 1440),
    "1080p (1920×1080)": (1920, 1080),
}

# ── Video2X 配置 ───────────────────────────────────────────────────

VIDEO2X_DEFAULT_PATH = r"D:\Software\Video2X Qt6\video2x.exe"

UPSCALE_MODELS = {
    "RealESRGAN (真人/实拍)": ("realesrgan", "realesrgan-plus"),
    "RealESRGAN (动漫视频)": ("realesrgan", "realesr-animevideov3"),
    "RealCUGAN (动漫，更锐利)": ("realcugan", "models-se"),
}

INTERP_MODELS = {
    "RIFE v4.26 (最新，最佳质量)": "rife-v4.26",
    "RIFE v4.6 (经典稳定)": "rife-v4.6",
    "RIFE v4.25 (轻量快速)": "rife-v4.25-lite",
    "不插帧": "",
}

ENCODER_PRESETS = {
    "H.264 (兼容性好)": ("libx264", "crf=18"),
    "H.265/HEVC (体积小)": ("libx265", "crf=20"),
}

# ── 主题预设 ────────────────────────────────────────────────────────

THEMES = {
    "深色毛玻璃": {
        "bg": "rgba(30, 30, 46, 200)",
        "card": "rgba(40, 40, 60, 180)",
        "text": "#cdd6f4",
        "accent": "#89b4fa",
        "border": "rgba(100, 100, 140, 80)",
        "header_bg": "rgba(50, 50, 70, 200)",
        "table_alt": "rgba(50, 50, 75, 100)",
        "hover": "rgba(80, 80, 120, 150)",
    },
    "浅色毛玻璃": {
        "bg": "rgba(255, 255, 255, 200)",
        "card": "rgba(245, 245, 250, 180)",
        "text": "#1e1e2e",
        "accent": "#1971C2",
        "border": "rgba(200, 200, 210, 120)",
        "header_bg": "rgba(235, 235, 245, 220)",
        "table_alt": "rgba(240, 240, 248, 100)",
        "hover": "rgba(200, 210, 240, 150)",
    },
    "暗夜紫": {
        "bg": "rgba(25, 20, 40, 210)",
        "card": "rgba(35, 28, 55, 180)",
        "text": "#e0d0ff",
        "accent": "#b197fc",
        "border": "rgba(90, 70, 130, 80)",
        "header_bg": "rgba(45, 35, 65, 200)",
        "table_alt": "rgba(45, 35, 70, 100)",
        "hover": "rgba(70, 55, 110, 150)",
    },
    "翡翠绿": {
        "bg": "rgba(20, 35, 30, 210)",
        "card": "rgba(25, 45, 38, 180)",
        "text": "#d0f0e0",
        "accent": "#51cf66",
        "border": "rgba(60, 110, 80, 80)",
        "header_bg": "rgba(30, 55, 45, 200)",
        "table_alt": "rgba(30, 55, 45, 100)",
        "hover": "rgba(50, 90, 70, 150)",
    },
}


def classify_resolution(w, h):
    for min_w, min_h, label, color in RESOLUTION_TIERS:
        if w >= min_w or h >= min_h:
            return label, color
    return "低清", "#868E96"


def classify_fps(fps):
    for threshold, label, color in FPS_TIERS:
        if fps >= threshold:
            return label, color
    return f"{fps:.0f}fps", "#868E96"


# 疑似假分辨率检测 —— 码率(kbps)低于阈值则标记
# 阈值参考: 真4K60fps通常 30Mbps+, 真4K30fps通常 15Mbps+
FAKE_RES_THRESHOLDS = {
    "4K":    15_000,   # 低于 15 Mbps 疑似假4K
    "2K":     8_000,   # 低于 8 Mbps 疑似假2K
    "1080p":  3_000,   # 低于 3 Mbps 疑似假1080p
}
FAKE_COLOR = "#FFD43B"  # 黄色警告


def check_fake_resolution(res_label, bitrate_kbps):
    """码率过低时返回警告文字和颜色，否则返回 None。"""
    threshold = FAKE_RES_THRESHOLDS.get(res_label)
    if threshold and bitrate_kbps > 0 and bitrate_kbps < threshold:
        return f"{res_label} ⚠疑似假", FAKE_COLOR
    return None


def format_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def format_duration(sec):
    h, sec = divmod(int(sec), 3600)
    m, s = divmod(sec, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_bitrate(kbps):
    if kbps >= 1000:
        return f"{kbps / 1000:.1f} Mbps"
    return f"{kbps:.0f} kbps"


def find_video2x(settings):
    """查找 video2x.exe，优先用设置里的路径。"""
    custom = settings.get("video2x_path", "")
    if custom and Path(custom).is_file():
        return custom
    if Path(VIDEO2X_DEFAULT_PATH).is_file():
        return VIDEO2X_DEFAULT_PATH
    return ""


# ── 设置管理 ────────────────────────────────────────────────────────

def load_settings():
    defaults = {
        "theme": "深色毛玻璃",
        "bg_image": "",
        "bg_opacity": 0.35,
        "last_folder": "",
        "video2x_path": VIDEO2X_DEFAULT_PATH,
        "gpu_device": 1,
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# ── 自定义排序 Item ─────────────────────────────────────────────────

class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)


# ── 带背景的中央控件 ───────────────────────────────────────────────

class BackgroundWidget(QWidget):
    """支持背景图 + 半透明遮罩的中央控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_pixmap = None
        self._bg_opacity = 0.35
        self._overlay_color = QColor(30, 30, 46, 200)

    def set_background(self, image_path, opacity=0.35):
        if image_path and Path(image_path).is_file():
            self._bg_pixmap = QPixmap(image_path)
        else:
            self._bg_pixmap = None
        self._bg_opacity = opacity
        self.update()

    def set_overlay(self, color: QColor):
        self._overlay_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()

        if self._bg_pixmap and not self._bg_pixmap.isNull():
            # 绘制背景图（填满窗口，裁切居中）
            scaled = self._bg_pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - rect.width()) // 2
            y = (scaled.height() - rect.height()) // 2
            painter.drawPixmap(0, 0, scaled, x, y, rect.width(), rect.height())

            # 半透明遮罩（让文字可读）
            overlay = QColor(self._overlay_color)
            overlay.setAlpha(int(255 * (1 - self._bg_opacity)))
            painter.fillRect(rect, overlay)
        else:
            painter.fillRect(rect, self._overlay_color)

        painter.end()


# ── 扫描线程 ────────────────────────────────────────────────────────

class ScanThread(QThread):
    progress = pyqtSignal(int, int)
    result = pyqtSignal(dict)
    finished_scan = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, folder, recursive=True):
        super().__init__()
        self.folder = folder
        self.recursive = recursive
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        root = Path(self.folder)
        files = []
        iterator = root.rglob("*") if self.recursive else root.iterdir()
        for f in iterator:
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                files.append(f)

        total = len(files)
        for i, fp in enumerate(files):
            if self._stop:
                break
            self.progress.emit(i + 1, total)
            try:
                cap = cv2.VideoCapture(str(fp))
                if not cap.isOpened():
                    self.error.emit(f"无法打开: {fp.name}")
                    continue
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                codec = "".join(
                    chr((fourcc >> 8 * i) & 0xFF) for i in range(4)
                ).strip('\x00')
                cap.release()

                size = fp.stat().st_size
                dur = frames / fps if fps > 0 else 0
                bitrate = (size * 8 / dur / 1000) if dur > 0 else 0

                self.result.emit({
                    "path": str(fp), "name": fp.name,
                    "width": w, "height": h,
                    "fps": round(fps, 2), "codec": codec,
                    "duration": dur, "bitrate": bitrate,
                    "file_size": size,
                })
            except Exception as e:
                self.error.emit(f"{fp.name}: {e}")

        self.finished_scan.emit()


# ── Video2X AI 修复线程 ────────────────────────────────────────────

class ConvertThread(QThread):
    """调用 Video2X CLI 逐个处理视频。
    需要超分+插帧时分两遍执行: 第一遍超分，第二遍插帧。"""
    file_started = pyqtSignal(int, str)       # index, filename
    file_progress = pyqtSignal(int, float)    # index, 0.0~1.0
    file_log = pyqtSignal(int, str)           # index, log line
    file_finished = pyqtSignal(int, bool, str)
    all_done = pyqtSignal()

    def __init__(self, tasks, v2x_exe, gpu_device,
                 upscale_proc, upscale_model, scale_factor,
                 interp_model, fps_mul,
                 codec, extra_enc, output_dir):
        super().__init__()
        self.tasks = tasks  # [(path, dur, w, h, fps), ...]
        self.v2x = v2x_exe
        self.gpu = gpu_device
        self.upscale_proc = upscale_proc      # "realesrgan" / "realcugan" / ""
        self.upscale_model = upscale_model     # model name
        self.scale_factor = scale_factor       # 2 or 4
        self.interp_model = interp_model       # "rife-v4.6" / ""
        self.fps_mul = fps_mul                 # 2 or 4
        self.codec = codec
        self.extra_enc = extra_enc             # e.g. "crf=18"
        self.output_dir = Path(output_dir)
        self._stop = False
        self._proc = None

    def stop(self):
        self._stop = True
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass

    def _run_v2x(self, args, idx, total_frames, phase_label):
        """执行一次 video2x 命令，解析 stderr 进度。"""
        cmd = [self.v2x] + args
        self.file_log.emit(idx, f"  [{phase_label}] {' '.join(cmd)}")

        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        pct_re = re.compile(r'(\d+(?:\.\d+)?)%')
        frame_re = re.compile(r'frame\s+(\d+)')

        for line in self._proc.stdout:
            if self._stop:
                self._proc.kill()
                return False
            line = line.strip()
            if not line:
                continue
            # 尝试解析百分比
            m = pct_re.search(line)
            if m:
                pct = float(m.group(1)) / 100.0
                self.file_progress.emit(idx, min(pct, 1.0))
            else:
                # 尝试解析帧号
                m2 = frame_re.search(line)
                if m2 and total_frames > 0:
                    pct = int(m2.group(1)) / total_frames
                    self.file_progress.emit(idx, min(pct, 1.0))
            # 只记录有意义的行
            if any(k in line.lower() for k in ('error', 'fail', 'warn', 'process', 'frame', '%')):
                self.file_log.emit(idx, f"  {line}")

        self._proc.wait()
        ok = self._proc.returncode == 0
        self._proc = None
        return ok

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        need_upscale = bool(self.upscale_proc)
        need_interp = bool(self.interp_model)

        for idx, (path, duration, sw, sh, sfps) in enumerate(self.tasks):
            if self._stop:
                break
            src = Path(path)
            self.file_started.emit(idx, src.name)
            total_frames = int(duration * sfps) if duration > 0 and sfps > 0 else 0

            # 判断是否需要处理
            is_4k = sw >= 3840 or sh >= 2160
            is_60 = sfps >= 55
            skip_up = is_4k or not need_upscale
            skip_interp = is_60 or not need_interp

            if skip_up and skip_interp:
                reasons = []
                if is_4k:
                    reasons.append(f"已是4K ({sw}×{sh})")
                if is_60:
                    reasons.append(f"已是{sfps:.0f}fps")
                self.file_finished.emit(idx, True,
                                        "已达标，跳过: " + ", ".join(reasons))
                continue

            final_out = self.output_dir / f"{src.stem}_ai{src.suffix}"
            temp_file = self.output_dir / f"{src.stem}_tmp_upscale{src.suffix}"

            # === 第一遍: 超分辨率 ===
            if not skip_up:
                up_out = temp_file if not skip_interp else final_out
                args = [
                    "-i", str(src),
                    "-o", str(up_out),
                    "-p", self.upscale_proc,
                    "-s", str(self.scale_factor),
                    "-d", str(self.gpu),
                    "-c", self.codec,
                ]
                if self.extra_enc:
                    for kv in self.extra_enc.split(","):
                        args += ["-e", kv.strip()]
                if self.upscale_proc == "realesrgan":
                    args += ["--realesrgan-model", self.upscale_model]
                elif self.upscale_proc == "realcugan":
                    args += ["--realcugan-model", self.upscale_model]

                self.file_log.emit(idx, "超分辨率处理中...")
                ok = self._run_v2x(args, idx, total_frames, "超分")
                if not ok:
                    # 检查输出文件是否实际存在（Video2X 有时返回码非零但实际成功）
                    if up_out.exists() and up_out.stat().st_size > 1024:
                        self.file_log.emit(idx, "  返回码异常但输出文件存在，视为成功")
                    else:
                        self.file_finished.emit(idx, False, "超分辨率失败")
                        temp_file.unlink(missing_ok=True)
                        continue
                src_for_interp = up_out
            else:
                src_for_interp = src
                if is_4k:
                    self.file_log.emit(idx, f"  分辨率已达标 ({sw}×{sh})，跳过超分")

            # === 第二遍: 帧插值 ===
            if not skip_interp:
                args = [
                    "-i", str(src_for_interp),
                    "-o", str(final_out),
                    "-p", "rife",
                    "--rife-model", self.interp_model,
                    "-m", str(self.fps_mul),
                    "-d", str(self.gpu),
                    "-c", self.codec,
                ]
                if self.extra_enc:
                    for kv in self.extra_enc.split(","):
                        args += ["-e", kv.strip()]

                self.file_log.emit(idx, "帧插值处理中...")
                ok = self._run_v2x(args, idx, total_frames, "插帧")
                if not ok:
                    # 同样检查输出文件
                    if final_out.exists() and final_out.stat().st_size > 1024:
                        self.file_log.emit(idx, "  返回码异常但输出文件存在，视为成功")
                    else:
                        self.file_finished.emit(idx, False, "帧插值失败")
                        temp_file.unlink(missing_ok=True)
                        continue
                # 清理临时文件
                if temp_file.exists() and temp_file != final_out:
                    temp_file.unlink(missing_ok=True)
            else:
                if is_60:
                    self.file_log.emit(idx, f"  帧率已达标 ({sfps:.0f}fps)，跳过插帧")

            self.file_progress.emit(idx, 1.0)
            self.file_finished.emit(idx, True, str(final_out))

        self.all_done.emit()


# ── 修复设置对话框 ──────────────────────────────────────────────────

class ConvertDialog(QDialog):
    def __init__(self, parent, count, settings):
        super().__init__(parent)
        self.setWindowTitle("AI 视频修复设置")
        self.setMinimumWidth(500)
        self._settings = settings
        layout = QVBoxLayout(self)

        info = QLabel(f"已选择 <b>{count}</b> 个视频进行 AI 修复 (Video2X)")
        layout.addWidget(info)

        # ── 超分辨率 ──
        g1 = QGroupBox("超分辨率 (画质提升)")
        f1 = QFormLayout(g1)

        self.upscale_cb = QCheckBox("启用 AI 超分")
        self.upscale_cb.setChecked(True)
        f1.addRow(self.upscale_cb)

        self.model_combo = QComboBox()
        self.model_combo.addItems(UPSCALE_MODELS.keys())
        f1.addRow("超分模型:", self.model_combo)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["2x (推荐，1080p→4K)", "4x (720p→4K，较慢)"])
        f1.addRow("放大倍数:", self.scale_combo)
        layout.addWidget(g1)

        # ── 帧插值 ──
        g2 = QGroupBox("帧插值 (流畅度提升)")
        f2 = QFormLayout(g2)

        self.interp_combo = QComboBox()
        self.interp_combo.addItems(INTERP_MODELS.keys())
        f2.addRow("插帧模型:", self.interp_combo)

        self.fps_mul_combo = QComboBox()
        self.fps_mul_combo.addItems(["2x (30→60fps)", "4x (15→60fps)"])
        f2.addRow("帧率倍数:", self.fps_mul_combo)
        layout.addWidget(g2)

        # ── 编码 + GPU ──
        g3 = QGroupBox("输出设置")
        f3 = QFormLayout(g3)

        self.enc_combo = QComboBox()
        self.enc_combo.addItems(ENCODER_PRESETS.keys())
        f3.addRow("编码器:", self.enc_combo)

        self.gpu_combo = QComboBox()
        self.gpu_combo.addItems([
            "0 - AMD Radeon 780M (集显)",
            "1 - NVIDIA RTX 4060 (独显，推荐)",
        ])
        self.gpu_combo.setCurrentIndex(settings.get("gpu_device", 1))
        f3.addRow("GPU:", self.gpu_combo)

        # Video2X 路径
        v2x_row = QHBoxLayout()
        self.v2x_edit = QLineEdit(settings.get("video2x_path", VIDEO2X_DEFAULT_PATH))
        self.v2x_edit.setPlaceholderText("video2x.exe 路径")
        v2x_row.addWidget(self.v2x_edit, 1)
        v2x_browse = QPushButton("浏览")
        v2x_browse.clicked.connect(self._browse_v2x)
        v2x_row.addWidget(v2x_browse)
        f3.addRow("Video2X:", v2x_row)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("默认: 源文件夹/ai_upscaled")
        out_row.addWidget(self.out_edit, 1)
        browse = QPushButton("浏览")
        browse.clicked.connect(self._browse_out)
        out_row.addWidget(browse)
        f3.addRow("输出目录:", out_row)
        layout.addWidget(g3)

        # 提示
        tip = QLabel(
            "<small>"
            "超分+插帧会分两遍处理。已达标(4K/60fps)的视频自动跳过。<br>"
            "RTX 4060 处理速度约 2~5 fps，一个 10 分钟视频大约需要 30~60 分钟。"
            "</small>"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.out_edit.setText(d)

    def _browse_v2x(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 video2x.exe", "",
            "可执行文件 (*.exe);;所有文件 (*)"
        )
        if path:
            self.v2x_edit.setText(path)

    def get_settings(self):
        # 超分
        do_upscale = self.upscale_cb.isChecked()
        up_key = self.model_combo.currentText()
        up_proc, up_model = UPSCALE_MODELS[up_key] if do_upscale else ("", "")
        scale = 4 if "4x" in self.scale_combo.currentText() else 2

        # 插帧
        interp_key = self.interp_combo.currentText()
        interp_model = INTERP_MODELS[interp_key]
        fps_mul = 4 if "4x" in self.fps_mul_combo.currentText() else 2

        # 编码
        codec, extra = ENCODER_PRESETS[self.enc_combo.currentText()]
        gpu = self.gpu_combo.currentIndex()
        out_dir = self.out_edit.text().strip()

        return {
            "upscale_proc": up_proc,
            "upscale_model": up_model,
            "scale_factor": scale,
            "interp_model": interp_model,
            "fps_mul": fps_mul,
            "codec": codec,
            "extra_enc": extra,
            "gpu_device": gpu,
            "output_dir": out_dir,
            "video2x_path": self.v2x_edit.text().strip(),
        }


# ── 外观设置对话框 ──────────────────────────────────────────────────

class AppearanceDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("外观设置")
        self.setMinimumWidth(460)
        self._settings = dict(settings)
        layout = QVBoxLayout(self)

        # 主题
        g1 = QGroupBox("主题")
        g1_layout = QFormLayout(g1)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        if settings.get("theme") in THEMES:
            self.theme_combo.setCurrentText(settings["theme"])
        g1_layout.addRow("预设主题:", self.theme_combo)
        layout.addWidget(g1)

        # 背景图
        g2 = QGroupBox("背景图片")
        g2_layout = QVBoxLayout(g2)

        img_row = QHBoxLayout()
        self.img_edit = QLineEdit(settings.get("bg_image", ""))
        self.img_edit.setPlaceholderText("选择一张图片作为背景（留空则纯色）")
        img_row.addWidget(self.img_edit, 1)
        img_btn = QPushButton("选择图片")
        img_btn.clicked.connect(self._pick_image)
        img_row.addWidget(img_btn)
        clear_btn = QPushButton("清除")
        clear_btn.clicked.connect(lambda: self.img_edit.clear())
        img_row.addWidget(clear_btn)
        g2_layout.addLayout(img_row)

        # 背景图透明度
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("图片可见度:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(5, 90)
        self.opacity_slider.setValue(int(settings.get("bg_opacity", 0.35) * 100))
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        opacity_row.addWidget(self.opacity_slider, 1)
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_label.setFixedWidth(40)
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(self.opacity_label)
        g2_layout.addLayout(opacity_row)

        # 预览
        self.preview = QLabel()
        self.preview.setFixedHeight(100)
        self.preview.setStyleSheet(
            "border: 1px solid #555; border-radius: 6px; background: #222;"
        )
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setText("背景预览")
        g2_layout.addWidget(self.preview)
        self.img_edit.textChanged.connect(self._update_preview)
        self._update_preview()

        layout.addWidget(g2)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*)"
        )
        if path:
            self.img_edit.setText(path)

    def _update_preview(self):
        path = self.img_edit.text().strip()
        if path and Path(path).is_file():
            pm = QPixmap(path).scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(pm)
        else:
            self.preview.clear()
            self.preview.setText("无背景图片（纯主题色）")

    def get_settings(self):
        return {
            "theme": self.theme_combo.currentText(),
            "bg_image": self.img_edit.text().strip(),
            "bg_opacity": self.opacity_slider.value() / 100,
        }


# ── 主窗口 ──────────────────────────────────────────────────────────

COL_CHECK = 0
COL_NAME = 1
COL_RES = 2
COL_RES_LABEL = 3
COL_FPS = 4
COL_FPS_LABEL = 5
COL_CODEC = 6
COL_BITRATE = 7
COL_DURATION = 8
COL_SIZE = 9
COL_PATH = 10

COLUMNS = [
    "", "文件名", "分辨率", "等级", "帧率", "帧率等级",
    "编码", "码率", "时长", "文件大小", "路径",
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频质量检测工具")
        self.resize(1300, 780)
        self.settings = load_settings()
        self.scan_thread = None
        self.convert_thread = None
        self.video_count = {"4K": 0, "2K": 0, "1080p": 0, "720p": 0, "其他": 0}
        self._v2x_exe = find_video2x(self.settings)
        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        # 背景容器
        self.bg_widget = BackgroundWidget(self)
        self.setCentralWidget(self.bg_widget)
        layout = QVBoxLayout(self.bg_widget)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(10)

        # ── 标题栏 ──
        title_row = QHBoxLayout()
        title = QLabel("视频质量检测工具")
        title.setObjectName("titleLabel")
        title_row.addWidget(title)
        title_row.addStretch()

        self.theme_btn = QPushButton("外观设置")
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self._open_appearance)
        title_row.addWidget(self.theme_btn)
        layout.addLayout(title_row)

        # ── 文件夹选择（卡片样式）──
        folder_card = QWidget()
        folder_card.setObjectName("card")
        fc_layout = QHBoxLayout(folder_card)
        fc_layout.setContentsMargins(12, 10, 12, 10)

        fc_layout.addWidget(QLabel("文件夹"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择要扫描的文件夹...")
        if self.settings.get("last_folder"):
            self.path_edit.setText(self.settings["last_folder"])
        fc_layout.addWidget(self.path_edit, 1)

        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self._browse)
        fc_layout.addWidget(self.browse_btn)

        self.recursive_cb = QCheckBox("包含子文件夹")
        self.recursive_cb.setChecked(True)
        fc_layout.addWidget(self.recursive_cb)

        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setObjectName("primaryBtn")
        self.scan_btn.setFixedWidth(110)
        self.scan_btn.clicked.connect(self._toggle_scan)
        fc_layout.addWidget(self.scan_btn)
        layout.addWidget(folder_card)

        # ── 进度条 ──
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        # ── 统计 + 操作栏 ──
        action_row = QHBoxLayout()
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("statsLabel")
        action_row.addWidget(self.stats_label, 1)

        self.select_btn = QPushButton("全选不达标")
        self.select_btn.setToolTip("选中所有非 4K 60fps 的视频")
        self.select_btn.clicked.connect(self._select_substandard)
        action_row.addWidget(self.select_btn)

        self.deselect_btn = QPushButton("取消全选")
        self.deselect_btn.clicked.connect(self._deselect_all)
        action_row.addWidget(self.deselect_btn)

        self.convert_btn = QPushButton("AI 修复选中视频")
        self.convert_btn.setObjectName("convertBtn")
        self.convert_btn.clicked.connect(self._start_convert)
        action_row.addWidget(self.convert_btn)
        layout.addLayout(action_row)

        # ── 表格 ──
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_CHECK, 36)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for i in range(COL_RES, COL_SIZE + 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(COL_PATH, True)
        layout.addWidget(self.table, 1)

        # ── 修复进度区 ──
        self.convert_group = QGroupBox("修复进度")
        self.convert_group.setObjectName("convertGroup")
        self.convert_group.setVisible(False)
        cg = QVBoxLayout(self.convert_group)
        self.convert_label = QLabel("")
        cg.addWidget(self.convert_label)
        self.convert_progress = QProgressBar()
        cg.addWidget(self.convert_progress)
        self.convert_log = QTextEdit()
        self.convert_log.setReadOnly(True)
        self.convert_log.setMaximumHeight(110)
        cg.addWidget(self.convert_log)
        self.convert_stop_btn = QPushButton("停止修复")
        self.convert_stop_btn.clicked.connect(self._stop_convert)
        cg.addWidget(self.convert_stop_btn)
        layout.addWidget(self.convert_group)

        # ── 状态栏 ──
        msg = "就绪"
        if not self._v2x_exe:
            msg += "  |  未检测到 Video2X，AI 修复功能不可用"
        else:
            msg += "  |  Video2X 已就绪"
        self.statusBar().showMessage(msg)

    # ── 主题应用 ──

    def _apply_theme(self):
        theme_name = self.settings.get("theme", "深色毛玻璃")
        t = THEMES.get(theme_name, THEMES["深色毛玻璃"])

        # 背景图
        bg_img = self.settings.get("bg_image", "")
        bg_opacity = self.settings.get("bg_opacity", 0.35)
        self.bg_widget.set_background(bg_img, bg_opacity)

        # 解析 overlay 颜色
        overlay = QColor(t["bg"])
        self.bg_widget.set_overlay(overlay)

        # QSS
        self.setStyleSheet(f"""
            QMainWindow {{
                background: transparent;
            }}
            QDialog {{
                background: {t['bg'].replace(', 200)', ', 240)').replace(', 210)', ', 240)')};
            }}
            QLabel {{
                color: {t['text']};
                background: transparent;
            }}
            #titleLabel {{
                font-size: 20px;
                font-weight: bold;
                color: {t['accent']};
                padding: 4px 0;
            }}
            #statsLabel {{
                font-size: 13px;
                color: {t['text']};
                opacity: 0.8;
            }}
            #card {{
                background: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 8px;
            }}
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {t['border']};
                border-radius: 6px;
                background: rgba(0,0,0,40);
                color: {t['text']};
                selection-background-color: {t['accent']};
            }}
            QLineEdit:focus {{
                border-color: {t['accent']};
            }}
            QPushButton {{
                padding: 7px 18px;
                border: 1px solid {t['border']};
                border-radius: 6px;
                background: {t['card']};
                color: {t['text']};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {t['hover']};
                border-color: {t['accent']};
            }}
            #primaryBtn {{
                background: {t['accent']};
                color: #fff;
                font-weight: bold;
                border: none;
            }}
            #primaryBtn:hover {{
                opacity: 0.85;
            }}
            #convertBtn {{
                background: {t['accent']};
                color: #fff;
                font-weight: bold;
                border: none;
            }}
            #convertBtn:hover {{
                opacity: 0.85;
            }}
            #convertBtn:disabled {{
                background: rgba(128,128,128,120);
            }}
            #themeBtn {{
                font-size: 12px;
                padding: 5px 12px;
            }}
            QTableWidget {{
                background: {t['card']};
                alternate-background-color: {t['table_alt']};
                color: {t['text']};
                gridline-color: {t['border']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                font-size: 13px;
                selection-background-color: {t['hover']};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QHeaderView::section {{
                background: {t['header_bg']};
                color: {t['text']};
                padding: 7px 6px;
                border: none;
                border-bottom: 2px solid {t['accent']};
                font-weight: bold;
                font-size: 12px;
            }}
            QCheckBox {{
                spacing: 6px;
                color: {t['text']};
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {t['border']};
                border-radius: 3px;
                background: rgba(0,0,0,30);
            }}
            QCheckBox::indicator:checked {{
                background: {t['accent']};
                border-color: {t['accent']};
            }}
            QProgressBar {{
                border: 1px solid {t['border']};
                border-radius: 6px;
                text-align: center;
                height: 22px;
                background: rgba(0,0,0,40);
                color: {t['text']};
            }}
            QProgressBar::chunk {{
                background: {t['accent']};
                border-radius: 5px;
            }}
            QGroupBox {{
                font-weight: bold;
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 18px;
                background: {t['card']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                color: {t['text']};
            }}
            QTextEdit {{
                background: rgba(0,0,0,50);
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }}
            QComboBox {{
                padding: 5px 10px;
                border: 1px solid {t['border']};
                border-radius: 6px;
                background: {t['card']};
                color: {t['text']};
            }}
            QComboBox QAbstractItemView {{
                background: {t['card']};
                color: {t['text']};
                selection-background-color: {t['hover']};
            }}
            QStatusBar {{
                background: transparent;
                color: {t['text']};
                font-size: 12px;
            }}
            QMenu {{
                background: {t['card']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item:selected {{
                background: {t['hover']};
                border-radius: 4px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

    # ── 外观对话框 ──

    def _open_appearance(self):
        dlg = AppearanceDialog(self, self.settings)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new = dlg.get_settings()
            self.settings.update(new)
            save_settings(self.settings)
            self._apply_theme()

    # ── 扫描 ──

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        if folder:
            self.path_edit.setText(folder)
            self.settings["last_folder"] = folder
            save_settings(self.settings)

    def _toggle_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_btn.setText("开始扫描")
            self.statusBar().showMessage("已停止")
            return

        folder = self.path_edit.text().strip()
        if not folder or not Path(folder).is_dir():
            self.statusBar().showMessage("请选择有效的文件夹")
            return

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.video_count = {"4K": 0, "2K": 0, "1080p": 0, "720p": 0, "其他": 0}
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.scan_btn.setText("停止")
        self.statusBar().showMessage("扫描中...")

        self.scan_thread = ScanThread(folder, self.recursive_cb.isChecked())
        self.scan_thread.progress.connect(self._on_progress)
        self.scan_thread.result.connect(self._on_result)
        self.scan_thread.finished_scan.connect(self._on_finished)
        self.scan_thread.error.connect(self._on_error)
        self.scan_thread.start()

    def _on_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.progress.setFormat(f"{current}/{total}")

    def _on_result(self, info):
        row = self.table.rowCount()
        self.table.insertRow(row)

        w, h = info["width"], info["height"]
        fps = info["fps"]
        res_label, res_color = classify_resolution(w, h)
        fps_label, fps_color = classify_fps(fps)

        # 先用原始等级统计计数
        if res_label in self.video_count:
            self.video_count[res_label] += 1
        else:
            self.video_count["其他"] += 1
        self._update_stats()

        # 再做假分辨率检测（会改变显示文字）
        fake = check_fake_resolution(res_label, info["bitrate"])
        if fake:
            res_label, res_color = fake

        # 勾选框
        cb = QCheckBox()
        cb_w = QWidget()
        cb_l = QHBoxLayout(cb_w)
        cb_l.addWidget(cb)
        cb_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb_l.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, COL_CHECK, cb_w)
        self.table.setItem(row, COL_CHECK, QTableWidgetItem(""))

        cells = [
            (COL_NAME,      info["name"],                    None, None),
            (COL_RES,       f"{w} × {h}",                   None, w * h),
            (COL_RES_LABEL, res_label,                       res_color, w * h),
            (COL_FPS,       f"{fps:.2f}",                    None, fps),
            (COL_FPS_LABEL, fps_label,                       fps_color, fps),
            (COL_CODEC,     info["codec"],                   None, None),
            (COL_BITRATE,   format_bitrate(info["bitrate"]), None, info["bitrate"]),
            (COL_DURATION,  format_duration(info["duration"]), None, info["duration"]),
            (COL_SIZE,      format_size(info["file_size"]),  None, info["file_size"]),
            (COL_PATH,      info["path"],                    None, None),
        ]

        for col, text, color, sort_val in cells:
            item = NumericItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if sort_val is not None:
                item.setData(Qt.ItemDataRole.UserRole, sort_val)
            if color:
                item.setForeground(QColor(color))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            if col == COL_NAME:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            self.table.setItem(row, col, item)

    def _on_finished(self):
        self.table.setSortingEnabled(True)
        self.progress.setVisible(False)
        self.scan_btn.setText("开始扫描")
        total = self.table.rowCount()
        self.statusBar().showMessage(f"扫描完成 — 共 {total} 个视频文件")

    def _on_error(self, msg):
        self.statusBar().showMessage(f"错误: {msg}")

    def _update_stats(self):
        parts = []
        for label in ("4K", "2K", "1080p", "720p", "其他"):
            cnt = self.video_count[label]
            if cnt:
                parts.append(f"{label}: {cnt}")
        total = sum(self.video_count.values())
        self.stats_label.setText(f"共 {total} 个视频  |  " + "  |  ".join(parts))

    # ── 勾选 ──

    def _get_checkbox(self, row):
        w = self.table.cellWidget(row, COL_CHECK)
        if w:
            return w.findChild(QCheckBox)
        return None

    def _select_substandard(self):
        for row in range(self.table.rowCount()):
            cb = self._get_checkbox(row)
            if not cb:
                continue
            res_item = self.table.item(row, COL_RES_LABEL)
            fps_item = self.table.item(row, COL_FPS)
            if not res_item or not fps_item:
                continue
            is_4k = res_item.text() == "4K"
            fps_val = fps_item.data(Qt.ItemDataRole.UserRole)
            is_60 = fps_val is not None and fps_val >= 55
            cb.setChecked(not (is_4k and is_60))

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            cb = self._get_checkbox(row)
            if cb:
                cb.setChecked(False)

    def _get_checked_videos(self):
        result = []
        for row in range(self.table.rowCount()):
            cb = self._get_checkbox(row)
            if not cb or not cb.isChecked():
                continue
            path = self.table.item(row, COL_PATH).text()
            dur = self.table.item(row, COL_DURATION).data(Qt.ItemDataRole.UserRole) or 0
            fps_val = self.table.item(row, COL_FPS).data(Qt.ItemDataRole.UserRole) or 0
            res_text = self.table.item(row, COL_RES).text()
            try:
                parts = res_text.split("×")
                w, h = int(parts[0].strip()), int(parts[1].strip())
            except (ValueError, IndexError):
                w, h = 0, 0
            result.append((path, dur, w, h, fps_val))
        return result

    # ── 修复 ──

    def _start_convert(self):
        videos = self._get_checked_videos()
        if not videos:
            self.statusBar().showMessage("请先勾选要修复的视频")
            return

        dlg = ConvertDialog(self, len(videos), self.settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        opts = dlg.get_settings()

        # 更新 Video2X 路径
        v2x_path = opts.get("video2x_path", "")
        if v2x_path and Path(v2x_path).is_file():
            self._v2x_exe = v2x_path
            self.settings["video2x_path"] = v2x_path
        else:
            # 尝试默认路径
            self._v2x_exe = find_video2x(self.settings)

        if not self._v2x_exe:
            QMessageBox.warning(
                self, "缺少 Video2X",
                "AI 修复功能需要 Video2X。\n\n"
                "请在修复设置对话框中配置正确的 video2x.exe 路径。",
            )
            return

        out_dir = opts["output_dir"]
        if not out_dir:
            first_dir = str(Path(videos[0][0]).parent)
            out_dir = os.path.join(first_dir, "ai_upscaled")

        # 保存 GPU 偏好和 Video2X 路径
        self.settings["gpu_device"] = opts["gpu_device"]
        save_settings(self.settings)

        self.convert_group.setVisible(True)
        self.convert_log.clear()
        self.convert_progress.setValue(0)
        self.convert_progress.setMaximum(len(videos) * 100)
        self.convert_btn.setEnabled(False)
        self.convert_label.setText(f"准备 AI 修复 {len(videos)} 个视频...")

        self.convert_thread = ConvertThread(
            tasks=videos,
            v2x_exe=self._v2x_exe,
            gpu_device=opts["gpu_device"],
            upscale_proc=opts["upscale_proc"],
            upscale_model=opts["upscale_model"],
            scale_factor=opts["scale_factor"],
            interp_model=opts["interp_model"],
            fps_mul=opts["fps_mul"],
            codec=opts["codec"],
            extra_enc=opts["extra_enc"],
            output_dir=out_dir,
        )
        self.convert_thread.file_started.connect(self._conv_started)
        self.convert_thread.file_progress.connect(self._conv_progress)
        self.convert_thread.file_log.connect(self._conv_log)
        self.convert_thread.file_finished.connect(self._conv_file_done)
        self.convert_thread.all_done.connect(self._conv_all_done)
        self.convert_thread.start()

    def _conv_started(self, idx, name):
        total = len(self.convert_thread.tasks)
        self.convert_label.setText(f"[{idx+1}/{total}] AI 处理中: {name}")
        self.convert_progress.setValue(idx * 100)

    def _conv_progress(self, idx, pct):
        total = len(self.convert_thread.tasks)
        name = Path(self.convert_thread.tasks[idx][0]).name
        overall = idx * 100 + int(pct * 100)
        self.convert_progress.setValue(overall)
        self.convert_label.setText(
            f"[{idx+1}/{total}] AI 处理中: {name}  ({pct*100:.0f}%)"
        )

    def _conv_log(self, idx, text):
        self.convert_log.append(text)

    def _conv_file_done(self, idx, ok, msg):
        name = Path(self.convert_thread.tasks[idx][0]).name
        if "已达标" in msg:
            tag = "SKIP"
        elif ok:
            tag = "OK"
        else:
            tag = "FAIL"
        self.convert_log.append(f"[{tag}] {name}: {msg}")

    def _conv_all_done(self):
        total = len(self.convert_thread.tasks)
        self.convert_progress.setValue(total * 100)
        self.convert_label.setText("AI 修复完成!")
        self.convert_btn.setEnabled(True)
        self.statusBar().showMessage("AI 修复完成")

    def _stop_convert(self):
        if self.convert_thread and self.convert_thread.isRunning():
            self.convert_thread.stop()
            self.convert_label.setText("已停止")
            self.convert_btn.setEnabled(True)

    # ── 右键菜单 ──

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        path_item = self.table.item(row, COL_PATH)
        if not path_item:
            return
        filepath = path_item.text()

        menu = QMenu(self)
        a1 = QAction("打开所在文件夹", self)
        a1.triggered.connect(lambda: os.startfile(str(Path(filepath).parent)))
        menu.addAction(a1)
        a2 = QAction("复制文件路径", self)
        a2.triggered.connect(lambda: QApplication.clipboard().setText(filepath))
        menu.addAction(a2)
        a3 = QAction("AI 修复此视频", self)
        a3.triggered.connect(lambda: self._convert_single(row))
        menu.addAction(a3)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _convert_single(self, row):
        cb = self._get_checkbox(row)
        if cb:
            self._deselect_all()
            cb.setChecked(True)
            self._start_convert()

    def closeEvent(self, event):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait(2000)
        if self.convert_thread and self.convert_thread.isRunning():
            self.convert_thread.stop()
            self.convert_thread.wait(3000)
        event.accept()


# ── 入口 ────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
