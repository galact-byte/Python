# 🛠️ 个人工具集

> 工作与玩游戏时编写的自动化脚本，减少重复劳动，提升效率。

---

## 📁 项目结构

```
.
├── AI/                     # AI 相关工具（打标、音频、对话等）
├── Excel/                  # Excel 处理工具
├── Image_classification/   # 图像分类（PyTorch / CIFAR-10）
├── Unity/                  # Unity AssetBundle 分析工具
├── ai-assistant/           # RAG 知识库 AI 助手
├── bat/                    # 批处理脚本集合
├── competation/            # CTF 竞赛工具（Crypto / Reverse）
├── files/                  # Pixiv 图片下载与处理工具
├── AI.py                   # OpenAI API 快速调用示例
├── Rename.py               # 图片批量顺序重命名
├── merge_manga.py          # 漫画 ZIP 合并 & 统一编号
├── merge_manga1.py         # 漫画合并（变体版本）
├── resize.py               # 图片批量缩放裁剪
├── test.py                 # 威胁日志分析 & IP 提取
└── ziduan.py               # JSON 字段提取工具
```

---

## 🤖 AI 工具模块 (AI/)

### AItag.py - AI 图片标签生成器

基于 AI 的智能图片打标工具，支持：

- 🏷️ 自动识别图片内容并生成标签
- 🔍 标签匹配与验证（精确匹配/模糊匹配）
- 📊 批量处理多图片
- 💾 项目保存与加载
- ⚙️ 自定义 API 配置（兼容 OpenAI 接口）

### image_processing_app.py - 辣椒炒肉图片打标器

功能完善的图片打标 GUI 应用：

- 🖼️ 批量图片打标处理
- 🔑 多 API Key 管理与自动轮换
- 📁 自定义输出目录
- 🎨 美观的 customtkinter 界面

### chat_with_api.py - API 对话工具

轻量级 AI 对话脚本，通过 OpenAI 兼容接口进行交互式问答。

### geminiAudio.py - Gemini 音频处理

基于 Google Gemini API 的音频处理工具。

### congpaixu.py - 排序工具

文件/数据排序相关功能。

详细说明请参阅 [AI/README.md](./AI/README.md)

---

## 🧠 AI 助手 (ai-assistant/)

基于 RAG（检索增强生成）架构的知识库 AI 助手：

- 📚 本地知识库管理，支持向量化检索
- 🔎 自动将用户问题与知识库匹配，输出更精准的回答
- 💬 多轮对话支持，上下文记忆
- 💾 对话历史保存/加载
- 🧮 基于 `text-embedding-3-small` 的语义向量检索

---

## 📊 Excel 工具模块 (Excel/)

### Script.py - 完结单批量导出

将 Word 格式的项目完结单批量导出到 Excel 表格。

**功能特点：**
- 📄 自动扫描并解析 `.docx` 完结单文件
- 📈 支持一个项目多个系统
- 🏷️ 智能识别项目类型（等保/密评/风评等）
- 📉 自动提取人员贡献率信息

详细说明请参阅 [Excel/README1.md](./Excel/README1.md)

---

## 🖼️ 图像分类 (Image_classification/)

基于 PyTorch 的 CIFAR-10 图像分类项目：

- 🧠 自定义 CNN 卷积神经网络
- 📈 训练过程可视化（损失曲线）
- 🖥️ 自动检测 GPU 并加速训练
- 📊 分类别准确率评估

---

## 🎮 Unity 工具 (Unity/)

Unity AssetBundle 文件分析工具集：

- 🔍 `analyze_unity.py` - 分析 Unity 文件结构、格式、压缩方式
- 🔧 `fix_unity.py` - Unity 文件修复工具
- 📊 支持 UnityFS / UnityRaw / UnityArchive 格式识别
- 🔐 文件加密检测（熵值分析）

---

## 🏴 CTF 竞赛工具 (competation/)

| 分类 | 工具 | 说明 |
|------|------|------|
| **Crypto** | `EzHNP.py` | 密码学挑战解题脚本 |
| **Crypto** | `RSA.iso.py` | RSA 相关密码分析 |
| **REVERSE** | `Dragon.py` | 逆向工程分析 |
| **REVERSE** | `Lesscommon.py` | 逆向工程分析 |

另含 `chelian`、`lattice-based-cryptanalysis`、`liangzi` 等专题目录。

---

## 🎨 Pixiv 工具 (files/)

Pixiv 图片批量下载与处理：

- 📥 从特殊格式文本提取 Pixiv 作品 ID
- 🔗 生成作品页面 URL 列表
- 🌐 HTML 版批量打开工具
- 🧹 自动去重

详细说明请参阅 [files/README.md](./files/README.md)

---

## 📜 批处理脚本 (bat/)

包含多种实用自动化脚本，按功能分类：

| 类别 | 说明 |
|------|------|
| **🔐 安全测试** | 若依框架扫描器、SQLMap 凭证查找、弱口令字典生成 |
| **🎮 游戏本地化** | 汉化工具 GUI、图层管理器、Fanbox 抓取、翻译合并 |
| **📄 文档处理** | 等保完结单处理、项目归档打包、文档自动生成 |
| **🔄 格式转换** | IP/URL 地址格式转换 |
| **📝 批量重命名** | 发票 PDF 重命名、文件名提取 |
| **🎬 视频质量检测** | 视频分辨率/帧率/码率检测、假分辨率警告、Video2X AI 超分修复 |

详细说明请参阅 [bat/README.md](./bat/README.md)

---

## 🧩 根目录独立脚本

| 脚本 | 功能 |
|------|------|
| `AI.py` | OpenAI API 快速调用示例 |
| `Rename.py` | 图片按顺序批量重命名 |
| `merge_manga.py` | 多个漫画 ZIP 解包后统一编号合并 |
| `merge_manga1.py` | 漫画合并（变体版本） |
| `resize.py` | 图片批量等比缩放 & 居中裁剪 |
| `test.py` | 威胁日志 CSV 清洗、IP 去重与导出 |
| `ziduan.py` | 从 JSON 文件提取指定字段到 TXT |

---

## 🚀 快速开始

### 环境要求

- Python 3.6+
- 根据使用的工具安装对应依赖

### 安装依赖

```bash
# AI 工具依赖
pip install PyQt6 aiohttp pandas fuzzywuzzy pillow customtkinter

# Excel 工具依赖
pip install python-docx pandas openpyxl colorama

# 图像分类依赖
pip install torch torchvision matplotlib numpy

# AI 助手依赖
pip install openai python-dotenv

# Pixiv 工具依赖
pip install requests
```

---

## 📝 使用说明

每个模块都有其特定用途，请根据需要运行对应脚本：

```bash
# 运行 AI 图片打标器
python AI/AItag.py

# 运行完结单导出工具
python Excel/Script.py

# 运行 AI 助手
python ai-assistant/main.py

# 运行图像分类训练
python Image_classification/图像分类.py
```

---

## 📄 许可证

本项目仅供个人学习和内部使用。
