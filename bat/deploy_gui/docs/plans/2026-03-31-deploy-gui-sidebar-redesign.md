# Deploy GUI Sidebar Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 deploy_gui 左侧导航栏重做为现代桌面应用风格的一体化侧栏，让项目列表成为主视图并解决操作区与列表互相挤压的问题。

**Architecture:** 主要修改 `deploy_gui/main_window.py` 的左栏布局、样式和分配比例，保留中间与右侧工作区不变。通过测试维持 `Program` 预设、模式切换和项目列表摘要的现有行为，同时补充一条针对左栏布局结构的最小验证。

**Tech Stack:** Python 3, PyQt6, pytest

---

### Task 1: 固定左栏结构与预设行为

**Files:**
- Modify: `E:\Python\Programs\test\bat\deploy_gui\tests\test_main_window.py`
- Modify: `E:\Python\Programs\test\bat\deploy_gui\deploy_gui\main_window.py`

**Step 1: Write the failing test**

补充左栏结构测试，锁住“无摘要卡片、项目列表存在、Program 预设存在”的预期。

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: FAIL if current structure does not satisfy the new compact sidebar design.

**Step 3: Write minimal implementation**

调整左栏结构与样式，去掉冗余分块，保留 Program 预设和项目列表。

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: PASS

### Task 2: 重做左栏为柔和分段式侧栏

**Files:**
- Modify: `E:\Python\Programs\test\bat\deploy_gui\deploy_gui\main_window.py`

**Step 1: Implement compact toolbar header**

将左栏操作区改成紧凑按钮组，减少说明文案和纵向堆叠。

**Step 2: Implement project navigation area**

将项目列表作为主导航区，增加更合理的宽度分配和可视高度。

**Step 3: Verify visually oriented structure via tests**

Run: `python -m pytest tests/test_main_window.py -q`
Expected: PASS

### Task 3: 文档与统一验证

**Files:**
- Modify: `E:\Python\Programs\test\bat\deploy_gui\README.md`
- Modify: `E:\Python\Programs\test\bat\deploy_gui\CHANGES.md`

**Step 1: Update docs**

同步左栏重设计说明和 Program 预设说明。

**Step 2: Run full verification**

Run: `python -m pytest tests -q`
Expected: PASS
