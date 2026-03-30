# CHANGES

## 2026-03-31

### 新增

- 新建 `deploy_gui` 通用部署器项目
- 基于 `PyQt6 + Paramiko` 提供图形化部署界面
- 支持多项目配置保存与切换
- 支持三种部署模式：ZIP 上传、Git 拉取、自定义命令
- 支持执行计划预览、SSH 测试连接、实时日志输出

### 实现

- 新增配置模型与 JSON 配置存储
- 新增执行计划生成器
- 新增 ZIP 打包模块
- 新增 SSH / SFTP 服务层
- 新增串行部署运行器
- 新增 PyQt6 主窗口
- 将 GUI 重构为默认浅色的卡片式工作台布局
- 日志区改为独立深色终端面板，和配置区视觉分层
- 将左侧新增/复制/删除操作前置为独立操作卡片，提升可见性
- 修复模式切换会被已保存项目强制写回的问题，恢复 ZIP/Git/自定义三种模式正常切换
- 将左侧项目列表改成信息卡片，直接显示项目名、模式标签和目标主机
- 增加 `Program` 预设，可直接填入当前项目常用的 ZIP 部署路径和选项
- 无配置时默认载入 `Program` 预设，减少首次填写成本
- 将左侧重构为紧凑工具头加项目导航区，移除冗余的当前项目摘要卡片
- 为主窗口补充最小结构测试，验证关键面板可实例化

### 验证

- `python -m pytest tests/test_main_window.py -q` 通过（1 passed）
- `python -m pytest tests -q` 通过（10 passed）
- `python -c "import os; os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen'); from deploy_gui.main_window import MainWindow; from PyQt6.QtWidgets import QApplication; app = QApplication.instance() or QApplication([]); w = MainWindow(); print(w.windowTitle())"` 输出 `通用部署器`
