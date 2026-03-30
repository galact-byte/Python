# 🛠️ 工作效率脚本集合（bat）

> 在工作中编写的自动化脚本，用于减少重复劳动、提高工作效率。

## 📁 目录结构

```
bat/
├── convert_ips_urls/     # IP/URL 格式转换工具
<<<<<<< HEAD
├── deploy_gui/          # 通用部署器（PyQt6 + Paramiko）
=======
├── dengbao-scraper/      # 等保测评数据爬虫
├── dengbao_tool/         # 等保完结单处理工具
>>>>>>> c53aae5a778713b586c8491a6a2c5285376364e2
├── game/                 # 游戏本地化与图层管理工具
├── generate_docs/        # 文档自动生成工具
├── guidang/              # 项目归档工具
├── rename/               # 批量重命名工具
├── tiqu/                 # 文件名提取工具
├── video/                # 视频质量检测与 AI 修复工具
└── *.py                  # 其他独立脚本
```

---

## 🔧 工具详情

### 🕷️ 等保数据爬虫类 (`dengbao-scraper/`)

| 脚本 | 功能 |
|------|------|
| `dengbao-scraper/scraper.py` | 项目进度数据爬虫 CLI，自动登录（OCR 验证码）、全量分页爬取、导出格式化 Excel，支持 7 种项目类型 |
| `dengbao-scraper/gui.py` | Web GUI 界面，浏览器可视化操作爬虫，实时日志、文件下载管理 |

详细说明请参阅 [dengbao-scraper/README.md](./dengbao-scraper/README.md)

### 📌 安全测试类

| 脚本 | 功能 |
|------|------|
| `ruoyi_scanner.py` | 若依(RuoYi)框架漏洞扫描器 v3.0，支持非标准路径部署，检测 Druid、Swagger、Actuator、Shiro 等漏洞 |
| `sqlmap_cred_finder.py` | 自动化 SQLMap 凭证查找，并行扫描数据库表，识别潜在的用户名/密码字段 |
| `generate_small_dictionaries.py` | 生成常见弱口令字典及其 MD5 哈希值，用于安全测试 |

### 🚀 部署运维类

| 工具 | 功能 |
|------|------|
| `deploy_gui/` | 通用图形化部署器，支持多项目配置、ZIP 上传部署、Git 拉取部署、自定义命令部署、执行计划预览和 SSH 实时日志 |

### 🎮 游戏本地化类 (`game/`)

| 脚本 | 功能 |
|------|------|
| `gameTranslate_tool.py` | 游戏汉化辅助工具 GUI，支持日文文本提取与翻译替换 |
| `layerManager.py` | 图层管理器 GUI，用于管理游戏立绘差分图层，支持拖拽排序和互斥设置 |
| `gamehanhuatihuan.py` | 游戏汉化文本替换脚本 |
| `rename_tool.py` | 文件批量重命名工具 |
| `fanbox_scraper.py` | Fanbox 内容抓取工具 |

### 📄 文档处理类

| 脚本 | 功能 |
|------|------|
| `generate_docs/generate_docs1.4.1.9.py` | 等保完结单处理脚本，自动提取项目信息并生成测评过程文档清单 |
| `guidang/tiqu1.2.py` | 项目归档批处理，从 Word 文档提取项目信息并打包 |

### 🔄 格式转换类

| 脚本 | 功能 |
|------|------|
| `convert_ips_urls/ips_urls.py` | IP/URL 地址格式转换，将顿号/逗号分隔的地址转换为每行一个 |

### 📝 批量重命名类

| 脚本 | 功能 |
|------|------|
| `rename/rename_invoices2.py` | 发票 PDF 批量重命名，自动提取发票号码作为文件名 |

### 📋 文件名提取类

| 脚本 | 功能 |
|------|------|
| `tiqu/tiqu1.py` | 批量提取目录下所有文件名，支持导出为 TXT 或 XLSX 格式 |

### 🎬 视频质量检测类 (`video/`)

| 脚本 | 功能 |
|------|------|
| `video/video_inspector.py` | 视频质量检测 GUI，扫描视频分辨率/帧率/码率，支持假分辨率检测和 Video2X AI 超分修复 |

---

## 🚀 使用方法

大多数脚本支持交互式运行：

```bash
python <脚本名>.py
```

部分脚本支持命令行参数，运行时会有提示。

## ⚙️ 环境要求

- Python 3.8+
- 部分脚本需要额外依赖：
  - `PyQt5` / `PyQt6` - GUI 工具
  - `paramiko` - SSH / SFTP 连接
  - `python-docx` - Word 文档处理
  - `pdfplumber` - PDF 解析
  - `pandas` - 数据导出
  - `requests` - 网络请求
  - `pywin32` - Windows COM 接口
  - `cryptography` - PFX 证书处理（dengbao-scraper）
  - `openpyxl` - Excel 导出（dengbao-scraper）
  - `ddddocr` - OCR 验证码识别（dengbao-scraper）
