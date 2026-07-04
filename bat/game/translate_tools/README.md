# RPG Maker MV/MZ 汉化工具库

一套通用的 RPG Maker MV/MZ 游戏汉化辅助工具，适配任意 MV/MZ 游戏（图片汉化、资源加解密、隐藏水印、质量核查、防崩自检）。

## 依赖

```bash
pip install Pillow opencv-python numpy scipy
```

（`scipy` 仅 `translate_pngs.py` 的 `interp2d` 擦除模式用到，可选。）

---

## 工具一览

### 1. translate_pngs.py — 图片汉化渲染引擎（核心）

依据 `translation.json` 配置，批量把图片上的原文擦掉、写上中文，输出到指定目录。用 `cv2.inpaint` 修复式擦除，保留渐变/边框/纹理，不平涂、不超框。

```bash
python translate_pngs.py <translation.json路径> [--only=<文件名子串>]
```

`translation.json` 结构：`default`（字体/颜色等默认值）+ `images`（每张图的 `input_path`/`output_path`/`layers`）。每个 layer 可配 `zh`（中文）、`box_pct`（覆盖框百分比）、`font_size_pct`、`align`/`valign`、`text_color`、`stroke_*`、`erase`（擦除模式：inpaint / glyph2panel / transparent / solid 等）。

> 这是引擎，配置驱动；换游戏只需换一份 `translation.json`。

### 2. rpgmvp_tool.py — .rpgmvp 加解密

RPG Maker MV/MZ 的加密图（`.rpgmvp` / `.rpgmvo` 等）用 System.json 里的 `encryptionKey` 对前 16 字节做 XOR。

```bash
python rpgmvp_tool.py key     <System.json路径>                  # 读出该游戏的 encryptionKey
python rpgmvp_tool.py encrypt <PNG目录>    <输出rpgmvp目录> <key十六进制>
python rpgmvp_tool.py decrypt <rpgmvp目录> <输出PNG目录>   <key十六进制>
```

也可作模块导入：`encrypt_png_bytes(png, key)` / `decrypt_rpgmvp_bytes(data, key)`。

### 3. watermark_tool.py — 隐藏水印（证明归属）

把自定义签名 base64 埋进 data：`System.json` 的自定义键 + 多个数据库 `note` 字段末尾 `<gxsig:...>`。玩家不可见、插件不误读、分散冗余难全删。

```bash
python watermark_tool.py embed <www/data目录> "你的签名文字"
python watermark_tool.py check <www/data目录>          # 检测并解码·验证归属
```

### 4. scan_codekeys.py — 代码键误译扫描（防崩自检）

机翻常把「被 JS 当 `switch`/`==`/`MetaChecker` 匹配的日文魔法字符串」也译成中文，导致进图无怪、战斗白屏等 bug。此工具从插件提取这些「代码键」，比对原版与译版，揪出被误译的键。

```bash
python scan_codekeys.py <原版游戏www目录> <部署译版data目录>
```

### 5. qa_compare.py — 汉化图对照 QA

日文原图（上）vs 汉化图（下）逐对并排成一张 PNG，肉眼查擦除穿帮（盖痕/色块/超框/色差）。

```bash
python qa_compare.py <日文原图根目录> <汉化图根目录> <category子目录> [max_w]
```

### 6. qa_diff.py — 框保护差异 QA

输出「原图 | 汉化 | 差异热图」三联，红=大改、黄=轻改。用来核查擦除有没有动到边框（框区出现红=越界改框）。

```bash
python qa_diff.py <日文原图根目录> <汉化图根目录> <category子目录> [max_w]
```

---

## 典型汉化流程

1. **解密**：用第三方解密工具把游戏 `img` 解出 PNG（或用 `rpgmvp_tool.py decrypt`，key 由 `rpgmvp_tool.py key System.json` 读出）。
2. **配置**：在 `translation.json` 里为每张图写 `zh` 和覆盖框。
3. **渲染**：`translate_pngs.py translation.json` → 生成中文 PNG。
4. **核查**：`qa_compare.py` / `qa_diff.py` 检查擦除质量。
5. **加密回填**：`rpgmvp_tool.py encrypt <中文PNG目录> <输出目录> <key>` → 覆盖回游戏 `img`。
6. **数据自检**：改完 data 跑 `scan_codekeys.py` 防机翻误译代码键导致崩溃。
7. **水印**：`watermark_tool.py embed` 埋签名。

---

## 说明

- 各工具的加密 key、路径均通过命令行参数传入，不含任何特定游戏的硬编码。
- 加密 key 因游戏而异，务必用目标游戏 `System.json` 的 `encryptionKey`。
