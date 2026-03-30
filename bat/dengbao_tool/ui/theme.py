"""Charcoal 暗色主题 — 功能型 UI"""

# 色板
BG = "#1c1c1e"
SURFACE = "#2c2c2e"
SURFACE_HOVER = "#363638"
PRIMARY = "#0a84ff"
PRIMARY_HOVER = "#3399ff"
ACCENT = "#ff375f"
TEXT = "#f2f2f7"
TEXT_SEC = "#8e8e93"
BORDER = "#3a3a3c"
SUCCESS = "#30d158"
FIELD_AUTO = "#1a3a5c"
FIELD_MODIFIED = "#3a2a1a"

STYLESHEET = f"""
/* ── 全局 ── */
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* ── 分组框 ── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 16px 12px 10px 12px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {PRIMARY};
    font-size: 13px;
}}

/* ── Tab ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SEC};
    padding: 8px 18px;
    margin-right: 2px;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {PRIMARY};
    border-bottom: 2px solid {PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    border-bottom: 2px solid {BORDER};
}}

/* ── 输入框 ── */
QLineEdit, QTextEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: {PRIMARY};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {BG};
    color: {TEXT_SEC};
}}
/* 自动填充字段 */
QLineEdit[fieldState="auto"], QTextEdit[fieldState="auto"] {{
    background-color: {FIELD_AUTO};
    border-color: #2a5a8c;
}}
/* 手动修改字段 */
QLineEdit[fieldState="modified"], QTextEdit[fieldState="modified"] {{
    background-color: {FIELD_MODIFIED};
    border-color: #6a4a2a;
}}

/* ── 下拉框 ── */
QComboBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 20px;
}}
QComboBox:focus {{
    border-color: {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SEC};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY};
    outline: none;
}}

/* ── 按钮 ── */
QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
    border-color: {TEXT_SEC};
}}
QPushButton:pressed {{
    background-color: {BORDER};
}}
QPushButton:disabled {{
    color: {TEXT_SEC};
    background-color: {BG};
    border-color: {BG};
}}
/* 主按钮 */
QPushButton[class="primary"] {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton[class="primary"]:hover {{
    background-color: {PRIMARY_HOVER};
}}
QPushButton[class="primary"]:disabled {{
    background-color: {BORDER};
    color: {TEXT_SEC};
}}

/* ── 复选框 ── */
QCheckBox {{
    spacing: 6px;
    color: {TEXT};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}
QCheckBox::indicator:hover {{
    border-color: {PRIMARY};
}}

/* ── 标签 ── */
QLabel {{
    color: {TEXT};
}}
QLabel[class="hint"] {{
    color: {TEXT_SEC};
    font-style: italic;
    font-size: 12px;
}}
QLabel[class="stepTitle"] {{
    font-size: 15px;
    font-weight: bold;
    color: {PRIMARY};
}}

/* ── 表格 ── */
QTableWidget {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    gridline-color: {BORDER};
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QTableWidget::item:selected {{
    background-color: {PRIMARY};
    color: white;
}}
QHeaderView::section {{
    background-color: {BG};
    color: {TEXT_SEC};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-size: 12px;
}}

/* ── 进度条 ── */
QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {PRIMARY};
    border-radius: 3px;
}}

/* ── 滚动区域 ── */
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_SEC};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 0;
}}

/* ── 表单标签 ── */
QFormLayout QLabel {{
    color: {TEXT_SEC};
    font-size: 12px;
}}

/* ── 步骤指示器 ── */
QWidget[class="stepBar"] {{
    background-color: {SURFACE};
    border-radius: 4px;
    padding: 4px;
}}

/* ── 分割线 ── */
QFrame[frameShape="4"] {{
    color: {BORDER};
}}

/* ── 变更日志面板 ── */
QTextEdit[class="changeLog"] {{
    background-color: {BG};
    color: {TEXT_SEC};
    border: 1px solid {BORDER};
    border-radius: 4px;
    font-family: "Consolas", "Microsoft YaHei UI", monospace;
    font-size: 12px;
}}
"""
