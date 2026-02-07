# Sakura 本地模型使用教程

## 🌸 Sakura 模型介绍

Sakura-7B-Qwen2.5 是专门为**日译中游戏翻译**优化的本地大语言模型，特别适合：
- ✅ Galgame（美少女游戏）
- ✅ 成人向游戏（完全无审核）
- ✅ 日系RPG
- ✅ 文字冒险游戏

---

## 📥 第一步：下载模型

### 推荐下载：IQ4XS 版本（4.25GB）

**下载地址（选择一个）：**

#### 方案1：HuggingFace 镜像（国内推荐）⭐⭐⭐⭐⭐
```
https://hf-mirror.com/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-7b-qwen2.5-v1.0-iq4xs.gguf
```

#### 方案2：HuggingFace 原站
```
https://huggingface.co/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-7b-qwen2.5-v1.0-iq4xs.gguf
```

#### 方案3：命令行下载
```bash
# Windows
set HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF sakura-7b-qwen2.5-v1.0-iq4xs.gguf --local-dir ./models

# Linux/Mac
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF sakura-7b-qwen2.5-v1.0-iq4xs.gguf --local-dir ./models
```

### 可选：Q6K 版本（更高质量，6.25GB）
如果你的显卡显存充足（10GB+），可以下载Q6K版本：
```
https://hf-mirror.com/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF/resolve/main/sakura-7b-qwen2.5-v1.0-q6k.gguf
```

---

## 🛠️ 第二步：选择运行方式

有三种方式运行Sakura模型，推荐度从高到低：

### 方式1：LM Studio（新手推荐）⭐⭐⭐⭐⭐

**最简单，图形化界面，开箱即用！**

#### 安装步骤：

1. **下载 LM Studio**
   ```
   https://lmstudio.ai/
   ```
   支持 Windows/Mac/Linux

2. **打开 LM Studio**

3. **导入模型**
   - 点击左侧 "🏠 Home"
   - 点击 "Load a local model"
   - 选择你下载的 `sakura-7b-qwen2.5-v1.0-iq4xs.gguf`

4. **加载模型**
   - 模型导入后，点击 "Load Model"
   - 等待加载完成（会显示绿色提示）

5. **启动API服务器**
   - 点击左侧 "↔️ Local Server"
   - 点击 "Start Server"
   - 默认地址：`http://localhost:1234`
   - 保持LM Studio运行！

6. **在翻译工具中配置**
   ```
   API提供商: Sakura (本地模型)
   API Key: (留空)
   模型: sakura (或留空)
   Base URL: http://localhost:1234/v1
   ```

---

### 方式2：Ollama（命令行用户推荐）⭐⭐⭐⭐

**简单，性能好，适合熟悉命令行的用户**

#### 安装步骤：

1. **安装 Ollama**
   
   **Windows:**
   ```
   https://ollama.ai/download
   ```
   或使用 winget：
   ```bash
   winget install Ollama.Ollama
   ```
   
   **Linux:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
   
   **Mac:**
   ```bash
   brew install ollama
   ```

2. **创建 Modelfile**
   
   在模型文件所在目录创建 `Modelfile` 文件：
   ```
   FROM ./sakura-7b-qwen2.5-v1.0-iq4xs.gguf
   
   PARAMETER temperature 0.1
   PARAMETER top_p 0.3
   PARAMETER top_k 40
   PARAMETER repeat_penalty 1.0
   ```

3. **导入模型**
   ```bash
   ollama create sakura -f Modelfile
   ```

4. **启动 Ollama 服务**
   ```bash
   # Ollama通常会自动启动服务
   # 如果没有，手动启动：
   ollama serve
   ```

5. **测试模型**
   ```bash
   ollama run sakura "将下面的日文翻译成中文：今日はいい天気ですね"
   ```

6. **在翻译工具中配置**
   ```
   API提供商: Sakura (本地模型)
   API Key: (留空)
   模型: sakura
   Base URL: http://localhost:11434
   ```

---

### 方式3：llama.cpp（高级用户）⭐⭐⭐

**性能最优，但配置复杂**

#### 安装步骤：

1. **下载 llama.cpp**
   
   **从Release下载（推荐）：**
   ```
   https://github.com/ggerganov/llama.cpp/releases
   ```
   下载适合你系统的预编译版本
   
   **或者自己编译：**
   ```bash
   git clone https://github.com/ggerganov/llama.cpp
   cd llama.cpp
   mkdir build && cd build
   cmake .. -DLLAMA_CUBLAS=ON  # NVIDIA GPU
   cmake --build . --config Release
   ```

2. **启动服务器**
   ```bash
   # Windows (在llama.cpp目录)
   llama-server.exe -m sakura-7b-qwen2.5-v1.0-iq4xs.gguf -ngl 99 --port 8080
   
   # Linux/Mac
   ./llama-server -m sakura-7b-qwen2.5-v1.0-iq4xs.gguf -ngl 99 --port 8080
   ```
   
   参数说明：
   - `-m`: 模型文件路径
   - `-ngl 99`: 将所有层加载到GPU（99表示全部）
   - `--port 8080`: API端口

3. **在翻译工具中配置**
   ```
   API提供商: Sakura (本地模型)
   API Key: (留空)
   模型: sakura
   Base URL: http://localhost:8080/v1
   ```

---

## 🎯 第三步：在翻译工具中使用

### 配置界面操作：

1. **打开翻译工具**
   ```bash
   python translation_gui.py
   ```

2. **切换到"2️⃣ API翻译"标签页**

3. **配置API**
   ```
   API提供商: Sakura (本地模型)
   API Key: (留空，本地模型不需要)
   模型: sakura (如果你用Ollama导入时用了其他名字，填那个名字)
   Base URL: 
     - Ollama: http://localhost:11434
     - LM Studio: http://localhost:1234/v1
     - llama.cpp: http://localhost:8080/v1
   ```

4. **点击"保存API配置"**（下次自动加载）

5. **选择要翻译的文件**
   - 输入文件：通常是第一步生成的 `_new_entries.json`
   - 输出文件：`translated_new_entries.json`

6. **点击"开始翻译"**

7. **等待翻译完成**
   - 可以在日志中看到进度
   - RTX 4060翻译1000条大约需要30-60分钟

---

## 💡 使用技巧

### 1. 速度优化

**提高翻译速度：**
- 使用IQ4XS而不是Q6K（速度快2倍）
- 关闭其他占用GPU的程序
- 如果用llama.cpp，确保 `-ngl 99` 参数正确

### 2. 质量优化

**提高翻译质量：**
- 使用Q6K版本（如果显存够）
- 调整temperature参数（越低越稳定）
- 对重要剧情可以翻译两次，选最好的

### 3. 显存不足怎么办

**如果显存爆了：**
```bash
# Ollama
ollama create sakura -f Modelfile

# 在Modelfile中添加：
PARAMETER num_gpu 20  # 只用20层GPU，其余用CPU
```

**llama.cpp:**
```bash
./llama-server -m model.gguf -ngl 20  # 20层GPU，其余CPU
```

### 4. 混合使用策略

**最佳方案：Sakura + DeepSeek 混合**

```
普通对话（70%） → DeepSeek API（快速便宜）
H场景（30%） → Sakura本地（专业无审核）
```

手动分类，或者用程序自动判断。

---

## 🔧 故障排查

### 问题1：显存不足

**错误信息：**
```
CUDA out of memory
```

**解决方案：**
1. 关闭其他占GPU的程序（游戏、浏览器等）
2. 使用IQ4XS而不是Q6K
3. 减少GPU层数（`-ngl 20`）

---

### 问题2：翻译很慢

**可能原因：**
- 模型在CPU上运行（没有GPU加速）
- GPU加速没启用

**解决方案：**
```bash
# 检查是否使用GPU
# llama.cpp会显示：
# llama_new_context_with_model: using CUDA for GPU acceleration

# Ollama检查：
ollama ps  # 看到模型在运行

# 确保 -ngl 参数 > 0
```

---

### 问题3：翻译质量不好

**可能原因：**
- Prompt格式不对
- Temperature太高

**解决方案：**
修改 `api_translator.py` 中的 Sakura prompt：

```python
# 简单直接的prompt效果最好
prompt = f"将下面的日文翻译成中文：{text}"

# 不要用太复杂的prompt
```

---

### 问题4：连接失败

**错误信息：**
```
Connection refused
```

**解决方案：**
1. 确认服务正在运行
   ```bash
   # Ollama
   ollama ps
   
   # LM Studio: 看界面是否显示 "Server Running"
   
   # llama.cpp: 看命令行是否在运行
   ```

2. 检查端口是否正确
   ```
   Ollama: 11434
   LM Studio: 1234
   llama.cpp: 8080（或你设置的）
   ```

3. 检查防火墙是否阻止

---

## 📊 性能参考

### RTX 4060 8GB (你的配置)

| 版本 | 加载时间 | 翻译速度 | 显存占用 |
|------|---------|---------|---------|
| IQ4XS | ~10秒 | 8-12 token/s | 5-6GB |
| Q6K | ~15秒 | 5-8 token/s | 7-8GB |

**翻译1000条日文文本：**
- IQ4XS: 约30-45分钟
- Q6K: 约45-60分钟

---

## 🎯 推荐配置总结

### 对于你（RTX 4060 8GB）：

**最推荐方案：**
```
模型: sakura-7b-qwen2.5-v1.0-iq4xs.gguf
运行方式: LM Studio (最简单)
配置:
  - API提供商: Sakura (本地模型)
  - Base URL: http://localhost:1234/v1
  - 模型: sakura
  - API Key: (留空)
```

**如果追求质量：**
```
模型: sakura-7b-qwen2.5-v1.0-q6k.gguf
但要监控显存使用！
```

---

## ✅ 快速开始检查清单

- [ ] 下载 sakura-7b-qwen2.5-v1.0-iq4xs.gguf (4.25GB)
- [ ] 安装 LM Studio
- [ ] 在 LM Studio 中加载模型
- [ ] 启动本地服务器
- [ ] 在翻译工具中选择 "Sakura (本地模型)"
- [ ] Base URL 填 `http://localhost:1234/v1`
- [ ] 开始翻译！

---

**有问题？**
- 检查 LM Studio 是否显示 "Server Running"
- 查看翻译工具的日志输出
- 确认模型文件完整（4.25GB）

祝翻译愉快！🌸
