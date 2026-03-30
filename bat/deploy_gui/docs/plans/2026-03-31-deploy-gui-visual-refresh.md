# Deploy GUI Visual Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 deploy_gui 改造成现代卡片式桌面应用，默认浅色，日志区深色，同时保持现有部署功能和数据流不变。

**Architecture:** 主要修改 `deploy_gui/main_window.py`，把 UI 结构拆成更清晰的区块，并引入统一样式表和复用构建函数。补充一个最小测试，验证样式初始化与主窗口创建仍然可执行。逻辑层、SSH 层、计划生成与运行器不做行为改动。

**Tech Stack:** Python 3, PyQt6, pytest

---

### Task 1: 为主窗口增加可复用样式层

**Files:**
- Modify: `E:\Python\Programs\test\bat\deploy_gui\deploy_gui\main_window.py`
- Test: `E:\Python\Programs\test\bat\deploy_gui\tests\test_main_window.py`

**Step 1: Write the failing test**

创建 `test_main_window.py`，验证窗口能被实例化，且样式初始化后窗口标题与关键区域对象存在。

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: FAIL because test file or target structure does not exist yet.

**Step 3: Write minimal implementation**

在 `main_window.py` 中抽出样式常量与初始化方法，保证主窗口初始化后可加载样式而不破坏现有行为。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: PASS

### Task 2: 重构三栏布局为卡片式工作台

**Files:**
- Modify: `E:\Python\Programs\test\bat\deploy_gui\deploy_gui\main_window.py`
- Test: `E:\Python\Programs\test\bat\deploy_gui\tests\test_main_window.py`

**Step 1: Write the failing test**

补充断言，检查项目列表、配置区、计划区和日志区对应控件都能创建。

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: FAIL because object names or structure not added yet.

**Step 3: Write minimal implementation**

调整 `_build_project_panel`、`_build_form_panel`、`_build_preview_panel`，增加卡片容器、标题区、辅助说明、按钮分层和深色日志面板。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: PASS

### Task 3: 补文档与验证

**Files:**
- Modify: `E:\Python\Programs\test\bat\deploy_gui\README.md`
- Modify: `E:\Python\Programs\test\bat\deploy_gui\CHANGES.md`

**Step 1: Update docs**

补充界面改版说明，记录当前视觉方向和验证结果。

**Step 2: Run full verification**

Run: `python -m pytest tests -q`
Expected: PASS

Run: `python -c "from deploy_gui.main_window import MainWindow; print('import-ok')"`
Expected: `import-ok`
