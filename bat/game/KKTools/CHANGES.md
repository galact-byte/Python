# 修改记录 — KKTools 恋活角色卡工具箱

> **修订记录**
>
> - v0.3.1: 恶性 Bug 排查与修复。① 修复血型静默损坏（mod 扩展血型索引≥4 时下拉显示不出会被保存成 A，现改为 itemData 驱动+越界兜底）；② 修复 looks_like_zip 逻辑/性能 Bug（去掉永真的 testzip 全量校验，伪装大文件不再卡顿）；③ get_block_dict 重写为多策略解码链，KK Custom 等多段二进制块不再抛错。KK 本体目录全面体检通过（分类/依赖提取/manifest/Custom 容错）。
> - v0.3.0: 补齐全部剩余模块——卡片浏览器、解包/打包+隐写伪装、Mod仓库缺失检测、场景卡提取、分享整理。新增后台线程 Worker、日志总线、目录扫描、配置存储等基础设施。内核增加卡片分类(角色/服装/场景)与 Sideloader 依赖 GUID 提取。样式精修(等宽数据视图/进度条/复选框/类型色标等)。新增 README.md，补全 .gitignore。全部模块经真实 KK/KKS 卡与真 mod 库验证。
> - v0.2.0: 「角色卡编辑」升级为丰富版——新增 提问/特点/H相关 三个标签页（按真卡字段动态生成中文勾选项）、完整名、备注(条件)、敏感部位/积极性/勤奋/温柔/音调 数值项、卡片详情表、捏脸数据只读摘要、KK↔KKS 标识转换（实验性）、报告含 提问/特点/H接受 统计。内核 get_block_dict 增加二进制块容错(UTF-8 失败退回 raw)。
> - v0.1.0: 立项。搭建项目骨架 + PyQt6 桌面应用框架；实现并验证 KK/KKS 角色卡解析内核（地基）；完成「角色卡编辑」模块。

## v0.3.0 变更明细

### 新增核心模块

- **core/settings.py**：JSON 配置（游戏目录 / Mod 目录 / 输出目录），含 mods 目录推断。
- **core/card_scan.py**：目录扫描，识别角色/服装/场景卡并提取缩略图与角色名。
- **core/mod_index.py**：扫描 .zipmod 读 manifest.xml 建 GUID 索引（可缓存 JSON）；check_card 比对卡片依赖找缺失。
- **core/stego.py**：zip 打包/解包；把压缩包追加到载体后伪装（zipfile 原生支持带前缀 zip）；分卷/合并。
- **core/scene_card.py**：扫描场景卡内嵌角色 marker，以脸图作封面重建为独立角色卡；analyze_scene 聚合依赖。
- **core/share.py**：把角色卡与其依赖 mod 复制成分享包，写 README。

### 内核增强 (core/kk_card.py)

- 新增服装卡 marker、`classify()`（角色/服装/场景/其它判别）、`peek_header()`、`extract_mod_ids()`（解 KKEx→UAR→info blob 的 ModID）。

### 新增 UI

- **ui/worker.py**：通用后台线程，自动注入 progress 回调，信号回报结果/异常。
- **ui/applog.py**：全局日志总线。
- **ui/pages/**：browser / pack / mod / scene / share / settings / log 七个功能页。
- **ui/main_window.py**：接入 8 个真实页面，打通浏览器双击→编辑器。
- **ui/style.qss**：精修——等宽只读数据视图、进度条、复选框、列表/菜单/工具提示样式。
- **ui/pages/browser_page.py**：类型色标（角色蓝/服装绿/场景琥珀）。

### 文档

- 新增 **README.md**；.gitignore 补充 config.json / mod_index.json。

### 验证

- 真 KK 卡(5.27MB)、真 KKS 卡(27.9MB)、真服装卡、真场景卡(提取2角色)、真 mod 库(manifest解析+缺失检测54依赖)、隐写打包往返、分卷合并字节一致——全部通过；核心单元测试 7/7 绿。

## v0.2.0 变更明细

### 新增 core/kk_fields.py — 提问/特点/H相关 字段中文标签映射

- ANSWER_LABELS(提问9项) / ATTRIBUTE_LABELS(特点KK18+KKS并集) / DENIAL_LABELS(H接受5项) / SCALAR_LABELS(详情表)。
- `count_true` / `editable_items` 跳过 KKEx 占位键 `ExtendedSaveData`（展示跳过、写回保留）。

### 修改 core/kk_card.py — get_block_dict 二进制容错

- Custom 等内含二进制的块用 UTF-8 解码会抛 UnicodeDecodeError，现退回 `raw=True` 保留原始字节，避免上层崩溃。

### 重写 ui/pages/editor_page.py — 丰富版编辑器

- 字段区滚动化；新增 完整名(只读合成)、备注(仅原卡有该字段才可写)、提问/特点/H相关 三标签页勾选项（按真卡 key 动态生成）、H 数值项。
- 右侧信息面板四视图：报告(含 提问/特点/H接受 统计 + 块存在性) / 卡片详情(标量表) / 解析JSON / 捏脸数据(只读摘要)。
- 工具条新增「转换 KK/KKS」(实验性，仅切 marker，强提示另存为)。
- 嵌套布尔字典按 key 在原副本上回填，保留占位键；真 KK/KKS 卡验证编辑翻转持久化、其它块字节保持。

## 新增文件

### core/kk_card.py — KK/KKS 角色卡解析内核（地基）

- **功能**：解析恋活 (KK) / 恋活日光浴 (KKS) 角色卡 PNG，读取与安全写回。
- **实现原理**：角色卡 = 缩略图 PNG + 尾部追加二进制（productNo / marker / version / 脸图PNG / lstInfo(MessagePack块索引) / data(各块拼接，块本身也是 MessagePack)）。字符串用 C# BinaryWriter 的 7-bit 变长前缀 + UTF-8。
- **安全写回策略**：未编辑任何块时数据区与块索引**原样字节吐回**（保证读→存与原文件完全一致）；编辑过块时按物理顺序重排、只更新 pos/size，且仅重打包被改的块，其余块字节级保留。
- **真卡验证**：KK(5.27MB)、KKS(27.9MB) 真卡均通过「干净往返字节级一致」「块铺排无空隙」「编辑后重载有效且其它块字节保持」。

### core/kk_enums.py — 枚举友好名映射

- 性格 / 血型 等枚举的中文名映射，仅内置基础游戏取值，mod 扩展值回退为「未知(数值)」绝不报错。

### tests/test_kk_card.py — 内核往返单元测试

- 手工按格式规范拼合成卡验证解析正确性；覆盖字节级往返、编辑持久化、备份、非卡拒绝等 7 个用例，全部通过。

### main.py / launch.py / start.bat — 入口与启动器

- 遵循 bat-launcher 规范：start.bat 仅做引导（无中文），launch.py 负责 Python 版本检查、依赖自动补齐（PyQt6/msgpack/Pillow）、启动桌面应用。

### ui/ — PyQt6 界面

- **main_window.py**：左侧导航 + 右侧页面堆叠；支持拖拽角色卡直接进编辑器。
- **style.qss**：功能型暗色主题（GitHub-Dark 风），克制扁平、无渐变/无发光/无 AI 味。
- **widgets.py**：PageBase 页头基类 + 卡片/标题/提示等复用部件。
- **pages/editor_page.py**：角色卡编辑页（读卡、改姓名/昵称/性格/血型/社团/生日、另存为新卡、覆盖+备份、更换预览图、导出 JSON、报告/JSON 双视图）。
- **pages/placeholder.py**：其余 6 模块的占位页，保证应用整体可运行。

---

## 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| 新增 | core/kk_card.py, core/kk_enums.py, core/__init__.py |
| 新增 | tests/test_kk_card.py |
| 新增 | main.py, launch.py, start.bat, requirements.txt, .gitignore |
| 新增 | ui/main_window.py, ui/style.qss, ui/widgets.py, ui/__init__.py |
| 新增 | ui/pages/editor_page.py, ui/pages/placeholder.py, ui/pages/__init__.py |

---

## 测试方式

1. 双击 `start.bat`（或 `python launch.py`）启动；首次运行会自动补齐依赖。
2. 点「读卡」或把角色卡 PNG 拖入窗口 → 应显示缩略图、姓名/性格/血型/生日、右侧报告。
3. 改昵称 → 「另存为新卡」→ 用游戏或本工具重新读取，确认昵称已变、其它信息无损。
4. 命令行回归：`python tests/test_kk_card.py`（应 7 通过 0 失败）。

## 待办（后续模块）

- 卡片浏览器 / 解包打包+隐写 / Mod 仓库缺失检测 / 场景卡工具 / 分享整理导入 / 运行日志 / 设置。
