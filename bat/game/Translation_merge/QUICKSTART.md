# 🚀 快速开始指南

## 1️⃣ 安装依赖

### Windows
双击运行 `run.bat`，会自动检查并安装依赖，然后启动程序。

### Linux/Mac
```bash
chmod +x run.sh
./run.sh
```

或者手动安装：
```bash
pip install -r requirements.txt
python translation_gui.py
```

## 2️⃣ 第一次使用

### 测试工作流程（使用示例文件）

1. **启动程序**
   ```bash
   python translation_gui.py
   ```

2. **第一步：合并文件**
   - 新文件：选择 `example_new_original.json`
   - 旧文件：选择 `example_old_translation.json`
   - 输出文件：保持默认 `merged_translation.json`
   - 点击"开始合并"

3. **第二步：API翻译**
   - 配置API（以OpenAI为例）：
     ```
     API提供商: OpenAI
     API Key: sk-你的密钥
     模型: gpt-3.5-turbo
     ```
   - 点击"保存API配置"
   - 输入文件会自动填充为 `merged_translation_new_entries.json`
   - 点击"开始翻译"

4. **第三步：回写结果**
   - 文件会自动填充
   - 点击"合并回写"
   - 完成！得到 `final_translation.json`

## 3️⃣ 实际使用

替换示例文件为你的实际文件：
- `example_new_original.json` → 游戏新版本的原文JSON
- `example_old_translation.json` → 游戏旧版本的已翻译JSON

## 📌 支持的API服务商

### OpenAI / ChatGPT
```
提供商: OpenAI
API Key: sk-xxxxxxxx
模型: gpt-3.5-turbo (便宜) 或 gpt-4o (质量高)
```

### Claude (推荐翻译质量)
```
提供商: Anthropic (Claude)  
API Key: sk-ant-xxxxxxxx
模型: claude-sonnet-4-5-20250929
```

### DeepSeek (国内推荐)
```
提供商: DeepSeek
API Key: sk-xxxxxxxx
模型: deepseek-chat
```

### Sakura 本地模型 (成人游戏推荐)⭐ 新增
```
提供商: Sakura (本地模型)
API Key: (留空)
模型: sakura
Base URL: http://localhost:11434 (Ollama) 或 http://localhost:1234/v1 (LM Studio)
```

**Sakura优势：**
- ✅ 完全免费（一次性配置后）
- ✅ 专为日译中游戏优化
- ✅ 完全无内容审核
- ✅ 特别适合成人向游戏

**详细配置教程：** 查看 `Sakura使用教程.md`

### 自定义API（适合国内中转）
```
提供商: 自定义OpenAI格式
API Key: 中转服务提供的Key
模型: gpt-3.5-turbo
Base URL: https://your-proxy.com/v1
```

## ⚡ 常用操作

### 只想合并，不翻译
完成第一步后，直接使用 `merged_translation.json` 即可。

### 已经有部分翻译
把已翻译的内容放在旧文件中，程序会自动复用。

### 重新翻译某些条目
1. 编辑 `merged_translation_new_entries.json`，只保留需要翻译的
2. 执行第二步
3. 执行第三步

### 批量翻译多个文件
每个文件重复三步流程即可。建议保存API配置，下次自动加载。

## 💰 费用估算

以1000条日文文本为例：

| API | 模型 | 约估费用 |
|-----|------|---------|
| OpenAI | gpt-3.5-turbo | ~$0.5-1 |
| OpenAI | gpt-4 | ~$5-10 |
| Claude | claude-3-5-sonnet | ~$3-5 |
| DeepSeek | deepseek-chat | ~$0.1-0.3 |

💡 提示：
- 首次使用建议先测试少量文本
- 程序会自动跳过不需要翻译的内容，节省费用
- 避免重复翻译已有内容

## 🔧 故障排查

### 程序无法启动
```bash
# 检查Python版本（需要3.8+）
python --version

# 重新安装依赖
pip install -r requirements.txt
```

### API翻译失败
1. 检查API Key是否正确
2. 检查网络连接
3. 查看日志中的具体错误信息
4. 确认API服务商的配额未用尽

### 编码错误
确保所有JSON文件都是UTF-8编码。

## 📞 获取帮助

1. 查看完整 `README.md`
2. 检查日志中的错误信息
3. 确认文件格式是否正确（JSON格式，UTF-8编码）

---

**祝使用愉快！** 🎮
