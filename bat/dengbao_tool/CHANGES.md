# 修改记录 — 等保文档迁移工具

> **修订记录**
>
> - v2.14: 拓扑图重复(模板已含占位图)、其它选项残留(电力专网)、storage_cloud前端误传、下划线保留视觉长度
> - v2.13: 字体丢失修复(font.name=None副作用)、服务范围其他重复、T6数据流转/存储位置残留兼容
> - v2.12: 备案表封面备案单位/数量字段补"个"/表5标题项目名/河津残留清除/报告多段首行缩进/carried_data端到端打通
> - v2.11: 定级报告章节填充重构（一~五 + 业务/系统 1/2/3）、承载数据新增字段、表六栅格化、多行单位输入
> - v2.10: 大数据双角色分支补全（前端/后端/回读）、表四前端栅格化、单 run 多占位填充修复
> - v2.9: 新模板替换、命名规则统一、IoT/工控/大数据补全、旧版备案表通用 XML 解析
> - v2.8: 云附录A回填、单字段标黄、报告正文 1/2/3 填充、矩阵精确涂灰、下划线保留
> - v2.7: 日期控件、等级损害项勾选、云角色分支、数据量单位重构、报告预览修复
> - v2.6: 单项目/批量双入口、表二/三/四/六字段重构、标黄交互修正、备案表填充增强
> - v2.5: 开发模式自动重载 — 新增 `start-dev.bat`，支持 Flask 自动重载与浏览器自动刷新
> - v2.4: 批量更新引擎与亮暗主题 — 支持总目录批量扫描、项目内多系统切换、状态文件跳过、Excel 清单导入、亮暗主题切换
> - v2.3: UI优化 — 移除扫描按钮、alert替换为居中弹窗
> - v2.2: 大量功能修复与增强 — UI交互、表二/四/六完善、标黄功能、定级报告矩阵表涂色
> - v2.1: 精准填充修复 — 勾选框、地址填空、表标题、封面、调查表拓扑图
> - v2.0: 整体重构 UI 为 Flask Web 界面
> - v1.0: 初版 PyQt6 桌面 GUI

## v2.14 — 拓扑图重复 / "其他"残留 / 下划线视觉保留

### 1. 报告网络拓扑图出现两张（关键 bug）

**根因**：定级报告模板 L10 段本身就含一张占位拓扑图（示例图）。`_insert_topology_image` 找到"（二）定级对象构成"后扫到首个空段（L10），直接在该 paragraph 上 `add_run().add_picture()` —— 旧示例图保留，新图追加，于是变成 2 张图。

**修复**：插入新图前调用 `_clear_drawings(target_p)`，删除目标段内所有 `w:drawing` 元素及其所属 `w:r` 节点。

### 2. 表二部署范围"电力专网"残留

模板 T2 R6 C2 P0 r13 预填示例值 `'电力专网'`（在"9-其他"标签后）。user 选 deploy_scope='1-局域网' 不进 `code=='9'` 分支，`_fill_other_option` 不被调用，残留保留。

**修复**：新增 `_clear_other_residue(cell, option_labels)` 函数，扫描 cell 中"其他/其它"label run 后到下一个 sym 之间的非空 run 全部清空。对 4 个 "其他/其它" 选项（biz_type / service_scope / service_target / deploy_scope）追加 `else: _clear_other_residue(...)` 分支。

### 3. T6 存储位置 5-非云计算平台 重复填写

user 选 storage_type='5-非云计算平台' 但前端 `storage_cloud_name` 留空时，HTML 的 `setField('storage_cloud_name', dd.storage_cloud_name || dd.storage_cloud)` 会拿 `dd.storage_cloud`（前端历史字段可能含 select 显示文本 `"5-非云计算平台"`）填入 input，进而被 `_fill_option_line` 写到 cell 里——表面看是"重复填了 5-非云计算平台"。

**修复**：在 `_fill_option_line` 调用前过滤误传值：`raw_name` 等于 `storage_type` 或以 `"<code>-"` / `"<code> "` 开头时视为前端把 select 值塞过来，置空跳过。

### 4. T6 数据流转 "横线被删了"

之前 v2.13 把 `数据来源单位2_____________________` 整段下划线替换为 user 值（`数据来源单位2来源单位乙`），视觉填空线全无。

**修复**：`_fill_placeholder_run` 增加 `keep_length=True` 参数 —— value 占用部分下划线宽度（按中文 2 字符宽 / 英文 1 字符宽估算），剩余部分追加字面 `_` 保持原视觉占位长度。`_fill_numbered_lines` 和 `_fill_option_line` 在含 `_+` 占位的"情况 a"分支均启用此选项。

输出示例：
- 之前: `数据来源单位2来源单位乙`
- 修复后: `数据来源单位2来源单位乙___________`（共保留原 21 个 `_` 减去 `来源单位乙`(10) = 11 个 `_`）

## 修改文件

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | `core/doc_writer.py` (`_insert_topology_image` 清除占位图、`_clear_other_residue` 新增、4 个其他选项分支追加清理、`_fill_option_line` 过滤前端误传、`_fill_placeholder_run` 加 `keep_length` 参数) |
| **修改** | `CHANGES.md` |

## 测试方式

```bash
python -c "
# 测拓扑图
from PIL import Image; Image.new('RGB',(300,200),'lightgray').save('test_topo.png')
# topology_image='test_topo.png' 生成报告，应只有 1 张图

# 测部署范围其它残留
data.target = TargetInfo(deploy_scope='1-局域网')  # 选局域网，不选其他
# 表二 R6 不应含 '电力专网'

# 测 storage_cloud 误传
data.data = DataInfo(storage_type='5-非云计算平台', storage_cloud='5-非云计算平台')
# T6 R10 P4 不应再次显示 '5-非云计算平台'

# 测下划线保留
data.data.inflow_units = '来源单位甲\n来源单位乙'
# T6 R7 应输出 '数据来源单位2来源单位乙___________'（带剩余下划线）
"
```

实测全部 PASS：
- ✓ 拓扑图 1 张
- ✓ T2 部署范围: `'1局域网      2城域网      3广域网      9其他  '` 无电力专网
- ✓ T6 R10 5 行: `'5非云计算平台'` 无重复
- ✓ T6 R7 来源单位: `'数据来源单位1来源单位甲\n数据来源单位2来源单位乙___________\n数据来源单位3来源单位丙___________（可根据实际情况添加）'` 下划线保留

---

## v2.13 — 字体丢失根因 / T6 数据流转 / 服务范围"其它"重复

### 1. 报告"承载数据"和"系统服务"段字体回退到宋体（关键 bug）

**根因**：`_copy_run_style` 在 deepcopy rPr 后，又用 `dst_run.font.name = src_run.font.name` 二次覆盖。当 src_run 模板只有 `eastAsia="仿宋_GB2312"` 没设 `ascii`（即 `font.name=None`）时，**python-docx 的 setter 在 ascii=None 时会删除整个 `w:rFonts` 元素**，把 eastAsia 一并带走，中文回退到默认宋体。

**修复**：deepcopy(rPr) 已包含完整字体信息，对 `font.name/size/bold/italic` 加防御性条件：仅当 src 值非 None 且与 dst 不同时才赋值，避免触发 setter 的副作用。

### 2. 表二服务范围"99-其它"自定义=本单位 → "本单位本单位"

T3 R4 C2 P3 模板 runs：`['', '99', '其它', ' ', '本单位', ' ']` —— 模板已预填示例值"本单位"在 r4。`_fill_other_option` 找到首个空白 run 写入后 return，r4 残留未清。

**修复**：填入后继续扫描到下一个 sym 之间，把所有非空 run 清空。

### 3. T6 数据来源单位 / 数据流出单位 残留 + 用户值被顶下去

模板预填示例：
- R7 数据来源单位 P0: `['数据来源单位1', '  ', '...', '无', '...']` —— 残留"无"
- R7 P1/P2 是单 run：`'数据来源单位2_____________________'` —— label 和占位在同一 run
- R8 数据流出单位 P0 残留"运城市电力调度中心"

旧 `_fill_numbered_lines` 只找 `_+` 占位填值，对 P0（无下划线只有残留）失效；对 P1（单 run）会把值 add_run 追加导致"label 占位 用户值"并列。

**修复**：按段落处理，**情况 a)** 单 run 含 `_+` → `_fill_placeholder_run` 原地替换；**情况 b)** 多 run 结构 → 首个非 sym 非 label run 写值、其余清空；用户未填的段也清空非 label 残留。

### 4. T6 R10/R11/R12 存储位置用户值没填上 + 河津残留

模板：
- R10 P0r3 = `'__________________________________'`（下划线占位 OK）
- R11 P0r3 = `'运城市变电站继电保护室'`（河津残留，无 `_`）
- R12 P0r5 = `'山西省运城市'`（河津残留）

旧 `_fill_option_line` 仅找 `_+` 占位，对预填值段返回 False（既没填上用户值，残留也保留）。

**修复**：与 `_fill_numbered_lines` 同样改造为三态兼容（label 含 `_+` / 后续 value 区 / 残留覆盖）。

## 修改文件

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | `core/doc_writer.py` (`_copy_run_style` 防御 None 副作用、`_fill_other_option` 后扫清残留、`_fill_numbered_lines` / `_fill_option_line` 三态兼容) |
| **修改** | `CHANGES.md` |

## 测试方式

```bash
python -c "
# 字体检查
from core.doc_writer import generate_report
# ... 生成报告后检查 L11/L12 (承载数据) + L29-L34 (系统服务 1/2/3 正文) 全部 eastAsia='仿宋_GB2312'

# 备案表
data.data = DataInfo(inflow_units='单位甲\n单位乙\n单位丙', storage_room='1', storage_room_name='本单位主机房')
# ... R7 应输出 '数据来源单位1单位甲\n数据来源单位2单位乙\n数据来源单位3单位丙' 全无下划线、无河津残留
"
```

实测全部 PASS：
- ✓ L12/L13 承载数据 + L29/L30/L32/L34 系统服务正文全部 `eastAsia='仿宋_GB2312'`
- ✓ T3 服务范围"99 其它 本单位"，"本单位" 仅出现 1 次
- ✓ T6 R7/R8 用户值正确填入 1/2/3 段，未填的段自动清空，所有下划线/河津残留清除
- ✓ T6 R10/R11/R12 存储位置用户值正确填入，"运城市变电站继电保护室" / "山西省运城市" 残留清除

---

## v2.12 — 备案表/报告 6 项实测问题修复

用户反馈生成的 docx 有 6 个问题，全部为根因级修复：

### 1. 备案表封面"备案单位"未填充（`core/doc_writer.py`）

模板 L12 runs = `['备',' ','案',' ','单',' ','位：','',' ']` —— **没有"盖章"二字**！原判断条件 `'盖章' in full and '受理' not in full` 把 L12 永远排除，从一开始就根本没填进去。改为 `'受理' not in full and '盖章' not in full`，并按"位：" run 的下一个 run 写入 `unit_name`，清空之后多余空格 run。

### 2. T1 R17-R21 数量字段补"个"

模板预填 `'1个'`，`_safe_set_value` 直接写"2"把"个"覆盖了。新增 `_cnt()` lambda 自动给 11 个数量字段补"个"后缀（空值置 "0个" 保持视觉一致）。

### 3. 表5标题括号内填项目名

P49 `'表五（  ）定级对象提交材料情况'` 之前未处理。`re.sub(r'表五（\s*）', f'表五（{target_name}）', txt)` 与表二/三/四 的 `（ / ）` 统一处理。

### 4. 河津残留清除（核心根因）

模板里有大量预填的"河津国京/邵家岭光伏电站/樊村镇/固镇村"等示例值，user 没填对应字段时旧代码的 `_safe_set_value` 直接 `return` 让残留保留下来。

**修复**：
- `_safe_set_value` 改为**空值也清空 cell**（保留 cell 结构与首 run 格式，将文本置 `''`）。所有 user 字段（unit_name/credit_code/leader.name/security_dept/data_dept 等）未填时不再留河津示例值
- `_fill_address` 完全重写，兼容"空格占位"和"已预填值残留"两种结构：用 `_is_label()` 判断 run 是标签（含 '省(' '地(' '县(' '详细地址'）还是值 run，label 间区间内首个非 label run 写值、其余清空（**不跨越 label 边界**，避免误清已写入的相邻字段）

### 5. 定级报告多段时首行缩进失效

`_replace_paragraph_text` 把含 `\n` 的整段塞到一个 run，Word 渲染为软回车，新行不继承段落首行缩进。

**修复**：按 `\r\n / \n / \r` 拆行，第一行写入原段落；后续行用 `OxmlElement('w:p')` 新建段落并 `deepcopy(src_pPr)` 继承首行缩进与所有段落属性，addnext 插入到锚点段后。

### 6. 承载数据未填到报告（端到端链路断）

`app.py::_dict_to_report` 的 key 列表里**完全没有 `carried_data`**——前端 textarea 提交的承载数据进到后端就被丢掉。补齐 key 列表。

## 修改文件

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | `app.py`（`_dict_to_report` key 列表补 `carried_data`） |
| **修改** | `core/doc_writer.py`（封面备案单位、数量字段、表5标题、地址重写、多段缩进、空值清空） |
| **修改** | `CHANGES.md` |

## 测试方式

```bash
python -c "
from models.project_data import ProjectData, ReportInfo, UnitInfo, TargetInfo, GradingInfo, ContactInfo, DataInfo
from core.doc_writer import generate_beian, generate_report
# 备案表 6 字段未填，验证不留河津残留
# 报告 composition 多段，验证每段都有首行缩进
# carried_data 验证端到端写入到 (四)
"
```

实测全部 PASS：
- 封面 L12 = `'备 案 单 位：测试公司'` ✓
- T1 数量 = `'2个/0个/1个'`（不再丢失"个"）✓
- T1 R2 详细地址 = 用户填的省市县地址，无邵家岭/樊村残留 ✓
- T1 R6/R10 + T6 R2 = 空字符串（user 没填则清空，不留邵家岭）✓
- 表5 = `'表五（测试系统）定级对象提交材料情况'` ✓
- 报告 composition `第一段\n第二段\n第三段` → L06/L07/L08 三段全部 fli=355600 ✓
- 报告 carried_data 端到端正确写入 L13/L14 ✓

---

## v2.11 — 定级报告章节填充重构 / 承载数据 / 表六对齐

### 报告填充算法重构（`core/doc_writer.py`）

新模板章节顺序变更：原 `(三)承载业务 → (四)安全责任` 改为 `(三)承载业务 → (四)承载数据 → (五)安全责任`；同时 `1、业务信息描述` 等小节的下方不再是 `【填写说明】` 占位，而是直接的示例正文段（且 `1、系统服务描述` 下面有连续 4 段示例）。原算法依赖「标题→紧邻 `【` 段」匹配，新模板下完全失效，导致：
- `biz_degree / svc_degree` 完全没填进去（标题后没 `【` 段）
- `svc_victim` 错填到「系统服务描述」位置（旧关键字 `该定级对象承载着综合办公业务` 不存在）

**新算法**：按段落顺序划分章节，将「标题段之后、下一标题之前的所有非空段」视为该节正文。首段替换为新值，其余示例段标记删除合并。覆盖 11 个章节：`(一)责任主体 (二)定级对象构成 (三)承载业务 (四)承载数据 (五)安全责任` + 业务/系统 各 `1/2/3` 小节。

```python
section_title_to_value = {
    "（一）责任主体": report.responsibility,
    "（二）定级对象构成": report.composition,
    "（三）承载业务": report.business_desc,
    "（四）承载数据": report.carried_data,
    "（五）安全责任": report.security_resp,
    "1、业务信息描述": report.biz_info_desc,
    "2、业务信息受到破坏时所侵害客体的确定": report.biz_victim,
    "3、业务信息受到破坏时对侵害客体的侵害程度的确定": report.biz_degree,
    "1、系统服务描述": report.svc_desc,
    "2、系统服务受到破坏时所侵害客体的确定": report.svc_victim,
    "3、系统服务受到破坏时对侵害客体的侵害程度的确定": report.svc_degree,
}
```

废弃旧的「定级对象于XX年 / 网络中部署了XXX防火墙 / 该定级对象承载着综合办公业务 / 按照网络安全法」等关键字定位（这些参考示例文本在新模板里已被替换为实际项目内容，关键字不再匹配）。

### 承载数据字段补齐

- **`models/project_data.py`** — `ReportInfo` 新增 `carried_data: str = ""`
- **`core/doc_reader.py`** — 章节判断扩展：
  - `(三) 承载业务` 限定为 `"业务" or "承载" in text and "数据" not in text`，避免被 `(四) 承载数据` 误命中
  - `(四) 承载数据` → `current_section = "carried_data"`
  - `(四) 安全责任`（旧模板兼容） / `(五) 安全责任`（新模板）→ `current_section = "security"`
- **`templates/index.html`** — 定级报告 Tab 新增 `rpt_carried_data` textarea，原 `(四) 安全责任` 标签改为 `(五) 安全责任`；`collectReportData` / `fillReportData` 接入 `carried_data`

### `_fill_cloud_provider_line` 空 value sentinel 修复

之前用 `\x01 / \x02` 控制字符作为空值占位 sentinel —— python-docx/lxml 拒绝写入控制字符，导致 `ValueError: All strings must be XML compatible`。改用全角下划线 `＿` 作为 sentinel：
- `_+` 正则只匹配半角 `_`，全角 `＿` 不会被命中，达到屏蔽效果
- 函数末尾还原 `＿ → _`，最终视觉占位仍是半角下划线

### 表六前端对齐 / 多行单位输入（`templates/index.html` + `static/style.css`）

- **数据来源 checkbox**：旧 `checkbox-row checkbox-wrap` → 新 `checkbox-grid`，按 1fr 自适应栅格对齐（与表四 IoT/工控/大数据 同款）
- **数据来源单位 / 数据流出单位**：textarea（每行一个）→ **3 个独立 input**（最多 3 个），更清晰更易编辑
  - 新增 `collectMultiLineInputs(dataAttr)` 收集后用 `\n` 拼接（保持后端 schema 不变）
  - 新增 `fillMultiLineInputs(dataAttr, rawValue)` 按 `\n / 、 / ; / ；` 拆分回填到 3 个 input
  - 新增 `.multi-line-inputs` CSS（`flex-direction: column`，3 行等宽）

## 修改文件

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | `models/project_data.py`（`ReportInfo.carried_data`） |
| **修改** | `core/doc_writer.py`（报告章节填充重构、`_fill_cloud_provider_line` sentinel 修复） |
| **修改** | `core/doc_reader.py`（章节判断扩展，支持 (四) 承载数据 / (五) 安全责任） |
| **修改** | `templates/index.html`（(四)(五) 标签、`rpt_carried_data`、表六栅格化、多行单位输入、JS helper） |
| **修改** | `static/style.css`（`.multi-line-inputs`） |
| **修改** | `CHANGES.md` |

## 测试方式

```bash
# 编译 + 报告 11 字段 round-trip + 备案表大数据回归
python -c "
from core.doc_writer import ProjectData, ReportInfo, generate_beian, generate_report
from core.doc_reader import read_beian_docx, read_report_docx
r = ReportInfo(...)  # 11 字段
generate_report('doc_templates/02-定级报告.docx', 'output/r.docx', r, '测试系统')
back = read_report_docx('output/r.docx')
assert back.carried_data == r.carried_data
"
```

实测结果：
- 报告 11 字段：(一)~(五) + 业务/系统的 1/2/3 全部正确填入对应段落，多余示例段自动合并删除
- 备案表大数据回归（platform_scale/provider/level/cert）：全绿
- r30 部分填充（仅服务商+等级）：未填字段保留半角下划线占位 `_____________ ___________` ✓

---

## v2.10 — 大数据双角色分支 / 表四前端栅格化 / 单 run 多占位

### 前端 — 大数据双角色分支字段（参照云计算）

- **`templates/index.html`** 大数据 form-group 新增两个条件子卡片：
  - **大数据平台填写**（勾选「大数据平台」时展开）：平台规模/基础设施地点/运维地点
  - **大数据应用、大数据资源填写**（勾选「大数据应用」或「大数据资源」时展开）：服务商/平台等级/平台名称/备案编号/备案证明附件
- 新增 `onBigdataCompChange()` JS 函数：根据 `data-bigdata-comp` 多选状态自动切换两个子区域的 `display`
- `collectFormData` 与 `fillBeianData` 接入新 8 个字段：`platform_scale / platform_infra / platform_ops / platform_provider / platform_level / platform_name / platform_code / platform_cert`
- `toggleSection('bigdata')` 现在会触发 `onBigdataCompChange()`；DOMContentLoaded 也会初始化一次

### 前端 — 表四物联网/工业控制/大数据 整齐化

- **`static/style.css` 新增 `.scenario-fields / .checkbox-grid / .scenario-subgroup` 三个类**：
  - `.scenario-fields`：子表单整体包裹（带左侧主色细边、淡背景，缩进 18px）
  - `.checkbox-grid`：CSS Grid `repeat(auto-fill, minmax(180px, 1fr))`，按内容自适应换行，标签等宽对齐
  - `.scenario-subgroup`：嵌套卡片虚线边框，用于「大数据平台填写」「大数据应用、大数据资源填写」两个分支
  - `.checkbox-other-input`：「其他」对应的文本框 `grid-column: 1/-1`，占满整行
- 物联网/工控/大数据的 checkbox 容器从 `checkbox-row checkbox-wrap` 改为 `checkbox-grid`

### 后端 — t5 大数据 r25-r31 完整填充（`core/doc_writer.py`）

- **`_fill_cloud_provider_line` 重构**：兼容「单 run 含多个 `_+` 占位」结构。原实现一个 run 只填一处占位，对大数据 r30 这种 `'大数据平台服务商_____平台安全等级___________'`（单 run 双占位）会错填。新版按 cell 重复扫描首个未填占位，空 value 用 sentinel marker 临时保护避免重复命中，最后还原。
- **`_fill_after_keyword` 升级**：keyword 与下划线在同一 run 时（如 `'附件___________________________'`），直接在该 run 内替换占位；之前只查 keyword 之后的 run 导致 r31 附件名一直没写入
- **大数据 r25-r31 接入填充**：
  - r26 `大数据应用数量____个` → `_fill_underline_field` 填 `platform_scale`
  - r27/r28 → `_safe_set_value` 填 `platform_infra` / `platform_ops`
  - r30 双段落 4 占位 → `_fill_cloud_provider_line` 顺序填 服务商/等级/名称/编号
  - r31 → `_fill_after_keyword` 填 `platform_cert`
  - 仅在 `composition` 含「大数据平台」时填 r26-r28，仅在含「大数据应用」或「大数据资源」时填 r30-r31

### 后端 — 回读支持（`core/doc_reader.py`）

- 新增 `_parse_bigdata_platform_line()` 正则解析 r30 的四段下划线值
- `_read_beian_new()` 的 t5 处理路径补充 r22-r31 完整读取：是否启用、系统组成多选、出境、平台规模/基础设施/运维、应用资源四项、备案证明

### 后端 — 旧版备案表的应用场景兜底（`core/doc_reader_legacy.py`）

- 新增 `_scan_scenario_legacy(doc, data)`：旧版备案表表 5 结构不一定存在，按行标签关键字兜底扫描：
  - `是否采用大数据 / 大数据系统组成 / 大数据出境` → 写入 `sc.bigdata.enabled/composition/cross_border`
  - `是否采用云计算 / 是否采用移动互联 / 是否为物联网` → 写入对应 `sc.xxx.enabled`
  - `系统感知层 / 系统网络传输层` → 写入 `sc.iot.perception/transport`
  - `系统功能层次 / 工业控制系统组成` → 写入 `sc.ics.function_layer/composition`
- 旧文档若无对应字段，扫描静默跳过，不污染默认值

## 修改文件

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | `templates/index.html`（IoT/工控/大数据 form-group 重构、collectFormData / fillBeianData 接入、onBigdataCompChange、DOMContentLoaded） |
| **修改** | `static/style.css`（新增 `.scenario-fields / .checkbox-grid / .scenario-subgroup / .checkbox-other-input / .suffix-note`） |
| **修改** | `core/doc_writer.py`（`_fill_cloud_provider_line` 单 run 多占位修复、`_fill_after_keyword` 单 run 兼容、t5 大数据 r25-r31 填充） |
| **修改** | `core/doc_reader.py`（`_parse_bigdata_platform_line`、t5 大数据 r22-r31 回读） |
| **修改** | `core/doc_reader_legacy.py`（`_scan_scenario_legacy` 兜底） |
| **修改** | `CHANGES.md` |

## 测试方式

```bash
# 1. 编译检查
python -m py_compile app.py core/doc_writer.py core/doc_reader.py core/doc_reader_legacy.py

# 2. 大数据写入 + 回读 round-trip
python -c "
from core.doc_writer import ProjectData, generate_beian
from core.doc_reader import read_beian_docx
p = ProjectData()
p.unit.unit_name = '某某新能源开发有限公司'
p.target.name = '光伏监控系统'
p.scenario.bigdata.enabled = True
p.scenario.bigdata.composition = '大数据平台,大数据应用,大数据资源'
p.scenario.bigdata.platform_scale = '5'
p.scenario.bigdata.platform_infra = '山西省运城市河津市'
p.scenario.bigdata.platform_provider = '阿里云'
p.scenario.bigdata.platform_level = '第三级'
p.scenario.bigdata.platform_name = '阿里云大数据平台'
p.scenario.bigdata.platform_code = '11000000000000-00000'
p.scenario.bigdata.platform_cert = '《阿里云-大数据平台-备案证明》'
generate_beian('doc_templates/01-新备案表.docx', 'output/_smoke.docx', p)
back = read_beian_docx('output/_smoke.docx')
print('roundtrip OK:', back.scenario.bigdata.platform_provider == '阿里云')
"

# 3. 启动应用并在浏览器实测
start.bat
```

实测结果：
- r22 是否采用大数据：勾「是」✓
- r23 大数据系统组成：「大数据平台」「大数据应用」「大数据资源」全部勾上 ✓
- r24 出境情况：勾「无出境需求」✓
- r26 大数据应用数量：`5` ✓ (下划线内联替换)
- r27/r28 基础设施/运维地点：填入完整地址 ✓
- r30 服务商/等级/名称/编号：4 段下划线顺序填入 `阿里云/第三级/阿里云大数据平台/11000000000000-00000` ✓
- r31 附件证明：`《阿里云-大数据平台-备案证明》` ✓
- 11 个字段回读全部正确

---



## v2.9 — 模板/命名/旧版兼容三件套

### 模板替换与清洗

- **替换为河津国京新版模板**：`doc_templates/01-新备案表.docx` 与 `doc_templates/02-定级报告.docx` 改为 `河津国京新能源开发有限公司-电力监控系统-备案资料更新` 提供的版本
- **新增模板清洗脚本 `scripts/sanitize_template.py`**：
  - 把模板里 228 处预勾选的 `w:sym` 全部复位为未勾（`Wingdings 2` / `0030`）
  - 段落级扫描清除跨 run 的 `《...》` 附件引用（避免出现 `《某某-定级报告》《--定级报告》` 残留）
  - 清除业务描述、河津国京/电力监控系统等专有名词
  - 把表标题里被覆写的对象名改回 `（ / ）` 占位
- **原模板备份**：清洗前备份到 `doc_templates/01-新备案表.docx.bak`

### 命名规则统一

- **`单位名称-系统名称-文件名称.docx`**：生成的备案表/定级报告文件名统一为该形式，预览文件同样规则
- **附件名自动派生**：`_autofill_attachment_names` 会按命名规则补齐用户未填的：定级报告附件名（`《单位-系统-定级报告》`）、专家评审意见表（`《单位-系统-专家评审意见表》`）、网络拓扑结构及说明、系统安全组织机构及管理制度、安全建设整改方案、安全产品/服务清单、主管部门定级文件
- **`app.py` 新增 `_resolve_filename_prefix` / `_sanitize_filename`**：剔除 Windows 文件名非法字符

### 字体统一

- **`_set_run_text` 重构**：所有写入内容统一中文 `仿宋_GB2312` + 西文 `Times New Roman`
- **备案表 fill mode**：新增模块级 `_FILL_FORCE_SIZE`，`generate_beian` 入口设置为 `Pt(10.5)`（五号），`generate_report` 设为 `None`（沿用模板字号）；try/finally 保证状态隔离

### 表四 IoT / 工控 / 大数据 补全

- 新增 `_fill_scenario_options(cell, text)`：把 `'感知节点,RFID标签'` 这类逗号/顿号分隔的多选 token，逐个 `_find_and_check`，未命中的 token 写入 `其他___` 占位
- IoT 行 17（感知层）、18（传输层）；工控行 20（功能层次）、21（系统组成）；大数据行 23（系统组成）全部接入
- `_find_and_check` 在 `multi=True` 模式下改为返回是否至少命中一次，便于 leftover 判断

### 旧版备案表通用 XML 解析（新增 `core/doc_reader_legacy.py`）

- **`read_beian_docx` 自动路由**：表数 < 7 或表[1] 行数 < 18 → 走 legacy 通用扫描；否则走当前的索引读取
- **标签扫描 `scan_label_pairs`**：
  - 按 `_tc` 身份去重相邻合并单元格（修复邮编 `0,4,3,3,3,0,0` 被压成 `0430` 的 bug）
  - section 上下文仅在同一合并块内有效，离开后立即重置（修复 `level_count` section 渗到表[2]的问题）
  - 嵌套字段（单位负责人/责任部门联系人）按 section prefix 防止 key 冲突
- **`_parse_address`**：剔除 `（自治区、直辖市）` 等标签括号注释后再按顺序匹配省/市/县；detail 头部 `县/区/市/旗` 残留也清掉
- **`_leading_code`**：从勾选文本提取前缀编码（`'4县（区、市、旗）'` → `'4'`），匹配下游 select 选项格式
- **`read_report_docx` 同样回退**：新格式解析后字段全空时改用 legacy 扫描

## 修改文件

| 操作 | 文件路径 |
| :--- | :--- |
| **替换** | `doc_templates/01-新备案表.docx` |
| **替换** | `doc_templates/02-定级报告.docx` |
| **备份** | `doc_templates/01-新备案表.docx.bak` |
| **新增** | `scripts/sanitize_template.py` |
| **新增** | `core/doc_reader_legacy.py` |
| **修改** | `app.py`（命名规则、_resolve_filename_prefix、_sanitize_filename） |
| **修改** | `core/doc_writer.py`（fill mode、_set_run_text、_find_and_check 多选返回值、_fill_scenario_options、_autofill_attachment_names、IoT/ICS/BigData 补全） |
| **修改** | `core/doc_reader.py`（read_beian_docx / read_report_docx 路由分发） |
| **修改** | `CHANGES.md` |

## 测试方式

```bash
# 1. 清洗模板（已执行一次，备份保留）
python scripts/sanitize_template.py

# 2. 冒烟测试（新模板填充 + IoT/ICS/BigData）
python -c "from core.doc_writer import generate_beian; ..."

# 3. 旧版备案表读取
python -c "from core.doc_reader import read_beian_docx; d = read_beian_docx(r'D:\...\信息系统安全等级保护备案表_20221221110237.docx')"

# 4. 端到端：旧文档 → 新模板
python -c "..."
```

实测结果：
- 河津国京旧版 `信息系统安全等级保护备案表_20221221110237.docx`（5 表，14×20 宽合并）成功提取单位名、地址（省/市/县/详细）、邮编、行政区划、负责人/联系人完整信息、勾选项编码、对象名称、业务描述、定级时间、最终等级
- 旧版 `02-电力监控系统定级报告.docx`（3 表）成功提取系统名称、等级
- 新模板生成：单位名/对象名/业务描述/附件名/IoT/工控/大数据勾选项全部正确写入，字体为 仿宋_GB2312 + Times New Roman + 五号

---

## v2.8 — 云附录A与正文填充修复

### 文档生成修复

- **表四云计算回填增强**：调查表接口新增附录 A 云字段解析，自动回填云服务商、平台名称、云服务模式、云计算形态，并将平台等级默认补为三级；备案编号按报告编号前两段截取
- **下划线字段保留横线**：表四云平台行、定级报告/评审附件、表六数据总量、月增长量、数据存储位置等改为 run 级填充，写入后仍保留剩余横线
- **填空横线改为“值在横线上”**：对模板里原本就是 `_` 占位的字段，改为只替换命中的那一段横线，并让填充值本身带下划线效果；不再出现“文字后面拖着一串 `_`”或“填完横线直接消失”
- **表六勾选修复**：补齐“拟定数据级别”勾选，存储位置名称按实际勾选项定向填入，不再总是写到第一行
- **报告正文修复**：对象构成、安全责任不再被模板 `XXX` 二次覆盖；业务信息/系统服务 1、2、3 小节改为替换说明段正文，重新恢复正文填充
- **矩阵精确涂灰**：业务信息/系统服务等级矩阵改为按“客体 + 损害程度”精确定位，只涂对应客体、对应程度和交叉级别，底色改为 `#808080`
- **身份证号局部标黄**：定级报告正文对 `身份证号码：XXXXXXXXXXXXXXXXXX` 这类占位改为整段字段级高亮，不再整段发黄

### 前端交互修复

- **标黄模式改单字段切换**：编辑页开启标黄模式后，点击哪个输入框就只切哪个字段，不再按整行字段组一起标黄
- **调查表自动补云字段**：加载调查表时，除拓扑图和拓扑描述外，也会把附录 A 里识别出的云字段自动带入表四
- **数据级别回显补齐**：旧备案表回读后，表六“数据级别”会正确回显到下拉框

### 测试方式

- `python -m py_compile app.py core\\doc_writer.py core\\doc_reader.py models\\project_data.py`
- 通过 `core.doc_writer.generate_beian()` 生成 `output/_verify_beian_v28.docx`
- 通过 `core.doc_writer.generate_report()` 生成 `output/_verify_report_v28.docx`
- 回读生成文档，确认云平台编号截断、数据级别勾选、第三方托管机房名称落点、身份证号局部高亮、正文 1/2/3 小节填充、矩阵灰色涂层均已写入

---

## v2.7 — 勾选与预览修复

### 表单结构调整

- **日期改为日历选择**：将运行时间、定级时间、填表日期改为 `date` 输入，并兼容旧文档中的中文日期回填
- **等级损害项拆细**：业务信息等级、系统服务等级新增对应损害项勾选，不再只保留等级下拉
- **主管部门审核状态拆分**：把“已审核/未审核”改成独立状态字段，并支持填写审核附件名
- **云角色分支显示**：按“云服务商 / 云服务客户 / 二者均勾选”切换不同字段；新增云平台备案证明输入
- **数据量单位修正**：数据总量、月增长量改为“单位 + 单值”输入，避免同时填写 GB 和 TB
- **表六录入样式贴近原表**：数据总量/月增长量改成备案表式横排录入，按 `01` 容量、`02` 万条分开展示，减少把整句误当成值的情况

### 文档生成修复

- **备案表勾选修复**：修正定级对象类型、是否分系统、业务信息等级、系统服务等级、最终等级、主管部门未审核、各类场景“否”选项的勾选
- **表四角色化填充**：云服务商与云服务客户分开填充，修正云服务商信息重复叠加问题，并预置华为云平台名称/备案编号
- **表六精准填空**：数据总量和月增长量改为按下划线精准填值，避免文本重叠
- **统一填写字体**：备案表新增填写内容统一为宋体五号，降低模板中字号不一致的问题
- **局部标黄修复**：定级报告正文中保留 `XXXX`/下划线占位时，仅高亮占位片段，不再整段发黄

### 预览与启动

- **定级报告预览修复**：修复插入拓扑图时 `CT_Body` 缺少 `part` 导致的预览失败
- **启动错误直出**：`launch.py` 在稳定模式下遇到 Flask 启动失败会打印 stdout/stderr，`start.bat` 可直接看到报错
- **旧备案表回读提纯**：表六数据总量、月增长量改为按 run 结构解析，回读时只保留纯数值/单位，不再出现 `1 30`、`22万条说明文字` 这类脏内容

### 测试方式

- `python` 导入 `app` 并渲染 `templates/index.html`，确认模板可正常生成
- 通过 `core.doc_writer.generate_beian()` 生成 `output/_verify_beian.docx`
- 通过 `core.doc_writer.generate_report()` 生成含拓扑图的 `output/_verify_report.docx`
- 回读生成文档，确认对象类型、是否分系统、业务/服务损害项、主管部门未审核、各场景“否”、局部高亮均已写入

---

## v2.6 — 双入口与字段重构

### Step 1 入口改造

- **单项目 / 批量页签**：Step 1 拆为两个入口页签，避免单项目和批量入口混在一起
- **自动触发扫描**：选择批量总目录后自动扫描；选择 Excel 清单后自动导入

### Step 2 表单修复

- **表二“其他”补全**：业务类型、服务范围、服务对象、部署范围、网络性质、互联情况均支持“选择 + 其他说明”
- **互联情况改为选择**：由手填改为标准选项，并保留“其他”补充输入
- **表三默认值**：未勾选上级行业主管部门时，主管部门默认填 `/`
- **表四云计算拆分**：区分云服务商与云服务客户，新增预置云厂商/第三方托管机房字典，并允许手动覆盖
- **表六结构化输入**：数据总量/月增长量拆为 GB/TB/万条；数据来源改为多选；存储位置拆为云/机房/区域三段

### 标黄与文档生成

- **标黄交互修正**：改为行级独立“标黄”按钮，不再拦截输入框点击
- **备案表填充增强**：补充表二/表四/表六的“其他说明”、下划线、多段存储位置与云平台字段填充
- **字体继承优化**：优先复用模板原有 run 样式，降低生成内容与周边字体不一致的问题

---

## v2.5 — 开发模式自动重载

### 启动方式增强

- **新增开发模式启动脚本**：新增 `start-dev.bat`，用于开发时启动自动重载模式
- **稳定/开发分离**：保留原 `start.bat` 作为稳定模式，避免日常使用也进入开发态
- **启动器参数化**：`launch.py` 支持 `--dev` 参数，并通过环境变量切换 Flask 开发模式

### Flask 自动重载

- **后端自动重启**：开发模式下启用 `debug=True` 和 `use_reloader=True`
- **控制台日志直出**：开发模式不再吞掉 Flask 输出，便于查看重载和报错日志

### 浏览器自动刷新

- **开发态文件签名接口**：新增 `/api/dev_status`
- **页面轮询刷新**：开发模式页面会轮询模板/静态资源/后端源码签名；检测到变化后自动刷新
- **重启恢复刷新**：后端因重载短暂中断后，浏览器会在服务恢复时自动刷新

---

## v2.4 — 批量更新与主题切换

### 批量更新引擎

- **总目录批量扫描**：新增总目录扫描入口，自动识别多个项目子目录
- **项目内多系统切换**：同一项目下可维护多个系统，系统级数据独立保存
- **状态文件跳过机制**：每个项目目录新增 `batch_update_state.json`，记录系统草稿、生成结果和源文件签名；已更新项可自动跳过
- **当前系统保存/重载**：支持保存当前系统到状态文件，并从旧备案表/定级报告重新加载
- **批量生成待更新项**：新增一键批量生成接口，自动汇总生成/跳过/失败数量

### Excel 清单导入

- **清单导入入口**：支持导入 `.xlsx` 项目清单
- **项目/系统名称辅助匹配**：按项目名称分组后合并到批量面板，用于辅助补齐系统列表

### 亮暗主题切换

- **主题切换按钮**：页头新增亮/暗主题切换
- **本地记忆**：主题选择写入浏览器本地存储，下次打开自动恢复
- **批量面板适配**：新增批量项目列表、系统状态条、工具栏的双主题样式

---

## 修改文件

### `core/batch_manager.py` — 批量扫描与状态持久化

- **新增内容**：项目/系统扫描、状态文件读写、生成跳过判断、Excel 清单解析

### `app.py` — 批量接口与单系统兼容增强

- **修改位置**：新增 `/api/scan_batch_root`、`/api/load_system`、`/api/save_system`、`/api/import_manifest`、`/api/generate_batch`
- **修改内容**：保留原有单系统接口，同时支持批量扫描、状态保存、批量生成和系统级命名

### `templates/index.html` — 批量入口与主题按钮

- **修改位置**：页头、Step 1、Step 2、Step 3
- **修改内容**：新增总目录扫描、Excel 清单导入、项目概览、系统切换工具条、批量生成入口、主题切换按钮

### `static/batch.js` — 批量前端控制器

- **新增内容**：项目/系统切换、当前系统保存、批量生成调用、主题切换、本地表单快照恢复

### `static/style.css` — 批量面板与亮暗主题样式

- **修改内容**：抽离主题变量，增加浅色主题和批量工作台样式，补充移动端适配

### `.gitignore` — 忽略状态文件

- **修改内容**：忽略 `batch_update_state.json`

---

## 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| **新增** | `core/batch_manager.py` |
| **新增** | `static/batch.js` |
| **修改** | `app.py` |
| **修改** | `templates/index.html` |
| **修改** | `static/style.css` |
| **修改** | `.gitignore` |
| **修改** | `CHANGES.md` |

---

## 测试方式

1. 启动 `start.bat`
2. 在 Step 1 选择一个包含多个项目子目录的总目录，确认项目列表出现
3. 切换不同项目/系统，确认表单内容能分别保存和恢复
4. 点击“保存当前系统”，确认项目目录生成 `batch_update_state.json`
5. 在 Step 3 执行“批量生成待更新项”，确认已更新项会被自动跳过
6. 点击页头主题按钮，确认亮/暗主题切换并在刷新后保留

---

## v2.3 — UI优化

### 移除扫描按钮

- 选择文件夹后已自动触发扫描，移除多余的"扫描"按钮

### alert替换为居中弹窗

- 新增 `showModal(msg)` / `closeModal()` 函数，替代浏览器原生 `alert()`
- 弹窗居中显示，支持点击遮罩层或"确定"按钮关闭
- 替换位置：项目名称校验、目录路径校验、加载错误提示、自动填充结果、加载失败提示、输出目录校验（共6处）
- 新增 CSS：`.modal-overlay`、`.modal-box`、`.modal-msg`、`.modal-footer`、`.modal-btn`

---

## v2.2 — 功能修复与增强

### UI 交互改进

- **定级对象数量五级溢出修复**：inline-group 允许换行，输入框宽度缩小
- **Step2 下一步导航**：点击下一步在Tab内依次切换，最后一个Tab才进入Step3；上一步同理
- **选择文件夹后自动扫描**：browseDir选择完毕后自动触发scanDir
- **网络服务"其他"文本输入**：服务范围/服务对象选"其他"时弹出文本框填写具体内容

### 表二定级对象增强

- **勾选项自动填充**：对象类型、业务类型、服务范围、服务对象、部署范围、网络性质等select字段从旧文件加载
- **技术类型多选**：对象类型选"信息系统"时显示技术类型勾选（云计算/移动互联/物联网/工控/大数据/其他）

### 表四与表二联动

- 表二勾选技术类型后，表四应用场景自动勾选对应项（如云计算→表四云计算启用）

### 表六数据信息完善

- **个人信息自动填充**：从旧文件读取后自动选中对应select
- **新增字段**：数据来源（select）、数据来源单位、数据流出单位、存储位置（云/非云切换）、机房位置、数据位置（境内/境外）
- **数据总量/月增长量**：分离数字和单位（GB后缀显示在输入框外）

### 标黄功能

- 编辑页面新增"标黄模式"开关，开启后点击任意输入框可标黄/取消
- 标黄字段在生成的Word文档中以黄色高亮显示，提示客户需要填写
- 支持备案表中主要字段的标黄映射

### 备案表生成修复 (doc_writer.py)

- **封面字体一致**：备案单位名称复制模板标签run的字体格式
- **表三等级打勾**：分别勾选业务信息等级、系统服务等级、最终等级
- **上级主管部门审核联动**：有主管部门时显示审核勾选，自动勾选"未审核"/"已审核"

### 定级报告生成大修 (doc_writer.py)

- **矩阵表涂色**：业务信息/系统服务安全保护等级矩阵表根据等级在对应单元格涂黑（黑底白字）
- **内容填充**：业务信息描述、侵害客体、侵害程度、系统服务描述等字段正确填充
- **填写说明删除**：清除所有【】标记的说明文字、"说明："段落、新技术采用提示
- **空行压缩**：连续空段落压缩为最多1个
- **图片位置修复**：拓扑图放在定级对象构成描述文字之后，而非页面顶部
- **子系统表**：无子系统时删除整个表格及描述段落
- **最终等级汇总表**：正确填充项目名、业务等级、服务等级

---

## 修改文件

### static/style.css — UI样式

- **修改位置**：inline-group、新增 highlight-yellow / highlight-toggle / highlight-btn 样式
- **修改内容**：flex-wrap: wrap, width: 60px, 标黄模式相关CSS

### templates/index.html — 前端页面

- **修改位置**：Step2导航逻辑、Tab B/E/C、JS函数区
- **修改内容**：
  - nextStep/prevStep 改为 Tab 内导航
  - 表二新增技术类型多选区域、服务范围/对象其他文本
  - 表六新增数据来源/流转/存储字段
  - 定级等级新增主管部门审核勾选
  - 标黄模式开关及交互逻辑
  - 选择文件夹后自动扫描
  - fillBeianData 增加 select 字段填充

### core/doc_writer.py — 文档生成

- **修改位置**：generate_beian、generate_report 全函数
- **修改内容**：
  - 新增 _highlight_run/_highlight_cell/_shade_cell_black/_shade_matrix_tables/_remove_consecutive_blanks
  - 封面字体格式复制、表三分等级勾选、上级主管审核
  - 定级报告：矩阵表涂色、内容填充、说明删除、空行压缩、图片定位、子系统表删除

### app.py — 后端接口

- **修改位置**：generate、preview 接口
- **修改内容**：传递 highlighted_fields 给 generate_beian/generate_report

---

## 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | static/style.css |
| **修改** | templates/index.html |
| **修改** | core/doc_writer.py |
| **修改** | app.py |

---

## 测试方式

1. 启动 `start.bat`，浏览器打开 http://localhost:5000
2. 选择包含旧备案表/定级报告的项目目录，确认选择后自动扫描
3. 进入Step2，检查各Tab字段是否正确填充（对象类型、服务范围等select）
4. 在表二选"信息系统"，确认技术类型多选出现且与表四联动
5. 开启标黄模式，点击几个字段标黄，预览Word确认高亮
6. 检查表六新增字段（数据来源/存储位置）
7. 预览备案表：封面字体、表三打勾、上级主管审核
8. 预览定级报告：矩阵表涂色、内容填充完整、无说明文字、图片位置正确
- **调查表字段**：Step 1 新增调查表文件路径（自动从父目录扫描）
- **勾选自动选中**：隶属关系、单位类型、行业类别自动匹配下拉值
- **Flask 红字**：抑制 Werkzeug WARNING 输出

---

## 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| **重写** | `core/doc_writer.py` |
| **重写** | `core/doc_reader.py` |
| **修改** | `app.py` |
| **修改** | `templates/index.html` |
| **修改** | `launch.py` |
| **修改** | `start.bat` |
| **修改** | `core/doc_converter.py` |

---

## 测试方式

1. 双击 `start.bat`，浏览器自动打开
2. 粘贴旧项目目录路径，点"扫描"
3. 确认备案表、定级报告、调查表三个文件自动检测到
4. 点"下一步"，确认数据自动填充（蓝色高亮）
5. Step 3 点"预览备案表"用 Word 打开验证：
   - 封面有单位名称
   - 表标题有定级对象名
   - 地址在正确位置，模版文字不变
   - 隶属关系/单位类型等正确打勾 ☑
   - 定级报告有/无正确勾选
   - 附件名称在正确位置
6. 点"预览定级报告"验证拓扑图插入
7. 确认后点"正式生成"
