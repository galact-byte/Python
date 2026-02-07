# 🎮 游戏翻译工作流工具

一站式游戏翻译工具，支持多种AI API（Sakura、DeepSeek、OpenAI、Claude、Gemini），包含翻译、质量检查和自动修复功能。

## ✨ 功能特点

- 🔄 **智能合并** - 比对新旧版本，只翻译新增内容
- 🤖 **多API支持** - Sakura、DeepSeek、OpenAI、Claude、Gemini
- 🔍 **质量检查** - 检测漏翻、语序错误
- 🪄 **AI修复** - 自动修复检测到的问题
- 💾 **配置保存** - API Key自动保存，支持.env文件
- 🎯 **智能跳过** - 自动跳过代码、数字等无需翻译内容

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install PyQt6 requests
```

### 2. 配置API Key（可选）

复制 `.env.example` 为 `.env` 并填入你的API密钥：

```bash
cp .env.example .env
```

编辑 `.env`：
```
DEEPSEEK_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### 3. 启动程序

```bash
python translation_gui.py
```

或使用启动脚本：
```bash
# Windows
run.bat

# Linux/Mac
./run.sh
```

## 📋 使用流程

### 第一步：合并文件
1. 选择新版本原文文件和旧版本翻译文件
2. 点击"开始合并"
3. 生成待翻译条目

### 第二步：API翻译
1. 选择API提供商，填写API Key
2. 点击"开始翻译"
3. 等待翻译完成

### 第三步：回写结果
1. 选择合并文件和翻译文件
2. 点击"合并回写"
3. 获得最终翻译文件

### 第四步：质量检查（可选）
1. 选择原文和译文文件
2. 勾选检查选项
3. 点击"开始检查"
4. 可使用"AI自动修复"

## 🔧 支持的API

| 提供商 | 用途 | 备注 |
|--------|------|------|
| **Sakura** | ✅翻译 | 本地模型，免费 |
| **DeepSeek** | ✅翻译 ✅检查 ✅修复 | 便宜好用 |
| **OpenAI** | ✅翻译 ✅检查 ✅修复 | GPT-4o-mini |
| **Claude** | ✅翻译 ✅检查 ✅修复 | Claude-3 |
| **Gemini** | ✅翻译 ✅检查 ✅修复 | Google AI |

> ⚠️ **Sakura是翻译专用模型**，不擅长质量检查和修复任务。

## 📁 文件说明

```
├── translation_gui.py      # 主程序（图形界面）
├── api_translator.py       # API翻译模块
├── merge_translations.py   # 合并逻辑
├── quality_checker.py      # 质量检查模块
├── .env.example           # API Key模板
├── requirements.txt       # 依赖列表
└── run.bat / run.sh       # 启动脚本
```

## ⚙️ 配置文件

程序会自动生成以下配置文件（已被.gitignore忽略）：

- `translation_config.json` - API配置
- `quality_config.json` - 质量检查设置
- `api_presets.json` - API预设

## 🔒 安全说明

- `.env` 文件包含敏感的API Key，**不会被上传到Git**
- 如要分享项目，请确保删除个人配置文件
- 建议使用 `.env` 而非直接在界面输入Key

## 📝 常见问题

**Q: Sakura连接失败？**  
A: 确保Sakura已启动，默认地址 `http://127.0.0.1:8080`

**Q: AI检查结果不准确？**  
A: Sakura是翻译专用模型，检查功能建议用DeepSeek/GPT

**Q: 如何保存API Key？**  
A: 在翻译标签页点击"保存API配置"，或创建`.env`文件

## 📄 许可证

MIT License

---

**祝翻译愉快！** 🎮✨
