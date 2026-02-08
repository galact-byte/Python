# 🛠️ 工作效率工具集

> 日常工作中积累的自动化脚本，减少重复劳动，提升工作效率。

---

## 📁 项目结构

```
.
├── AI/                 # AI 相关工具
├── Excel/              # Excel 处理工具
├── bat/                # 批处理脚本集合
└── generate_small_dictionaries.py
```

---

## 🤖 AI 工具模块

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

### geminiAudio.py - Gemini 音频处理

基于 Google Gemini API 的音频处理工具。

### congpaixu.py - 排序工具

文件/数据排序相关功能。

---

## 📊 Excel 工具模块

### Script.py - 完结单批量导出

将 Word 格式的项目完结单批量导出到 Excel 表格。

**功能特点：**
- 📄 自动扫描并解析 `.docx` 完结单文件
- 📈 支持一个项目多个系统
- 🏷️ 智能识别项目类型（等保/密评/风评等）
- 📉 自动提取人员贡献率信息

详细说明请参阅 [Excel/README1.md](./Excel/README1.md)

---

## 📜 批处理脚本 (bat/)

包含多种实用批处理脚本：

| 类别 | 说明 |
|------|------|
| **game/** | 游戏相关工具脚本 |
| **convert_ips_urls/** | IP 与 URL 转换工具 |
| **generate_docs/** | 文档生成工具 |
| **rename/** | 文件重命名工具 |
| **ruoyi_scanner.py** | 若依框架扫描器 |
| **sqlmap_cred_finder.py** | SQLMap 凭证查找工具 |

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
```

---

## 📝 使用说明

每个模块都有其特定用途，请根据需要运行对应脚本：

```bash
# 运行 AI 图片打标器
python AI/AItag.py

# 运行完结单导出工具
python Excel/Script.py
```

---

## 📄 许可证

本项目仅供个人学习和内部使用。
