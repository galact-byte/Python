# 修改记录 — 项目进度数据爬虫

> **修订记录**
>
> - v2.0: 功能升级 — 支持 7 种项目类型爬取 + Web GUI 界面
> - v1.0: 初始版本，支持从项目管理系统爬取等保测评全部数据并导出 Excel

## v2.0 — 多项目类型 + Web GUI

### 修改文件

#### `scraper.py` — CLI 脚本升级

- **修改位置**：全局重构
- **修改内容**：
  - 新增 `PROJECT_TYPES` 字典，定义 7 种项目类型（等保测评/密码评估/安全评估/风险评估/软件测试/安全服务/综合服务）及对应 API 路径
  - `fetch_page`/`fetch_all`/`check_session` 函数新增 `api_path` 参数，支持不同类型使用不同接口
  - `export_excel` 新增 `type_name` 参数，文件名按类型区分
  - 新增 `--type` 命令行参数（默认 `dengbao`），支持 `--type all` 爬取全部类型
  - 新增 `run_scrape` 函数封装单类型爬取流程，多类型时逐个执行并汇总结果
  - 向后兼容：无参数执行等同于 `--type dengbao`

### 新增文件

#### `gui.py` — Web GUI 界面

- **功能**：基于 `http.server` 的本地 Web 界面，在浏览器中操作爬虫
- **实现原理**：
  - 内嵌完整 HTML/CSS/JS 页面（暗色主题，Obsidian 配色）
  - 后台线程执行爬取，前端轮询 `/api/status` 获取实时日志
  - 支持多选项目类型、保存配置、下载已导出文件
- **端点**：
  - `GET /` — 主页面
  - `POST /api/scrape` — 启动爬取
  - `GET /api/status` — 查询爬取状态和日志
  - `GET /api/config` / `POST /api/config` — 读取/保存配置
  - `GET /api/files` — 列出已导出文件
  - `GET /download/<filename>` — 下载 Excel 文件（含路径穿越防护）
- **使用方法**：`python gui.py` 或双击 `start_gui.bat`

#### `start_gui.bat` — GUI 启动脚本

- **功能**：双击打开 Web GUI

---

### 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| **修改** | `scraper.py` |
| **新增** | `gui.py` |
| **新增** | `start_gui.bat` |

---

### 测试方式

1. CLI 方式：`python scraper.py --type dengbao` 确认单类型爬取正常
2. CLI 方式：`python scraper.py --type all` 确认多类型逐个爬取并汇总
3. CLI 方式：`python scraper.py --help` 确认 `--type` 参数显示正确
4. GUI 方式：`python gui.py`，浏览器自动打开，选择类型并点击「开始爬取」
5. GUI 方式：确认日志实时滚动、文件列表更新、文件可下载

## 新增文件

### scraper.py — 核心爬虫脚本

- **功能**：连接项目管理系统 API，分页获取等保测评数据，导出为格式化 Excel
- **实现原理**：
  - 使用 PFX 客户端证书（运行时转换为 PEM）建立 HTTPS 连接
  - 通过浏览器 Session Cookie（PHPSESSID）鉴权
  - 调用 FastAdmin JSON API 分页获取数据（每页 50 条，自动遍历全部页）
  - 嵌套字段（hand/setup）展平为 24 列 Excel 表格
- **用法**：
  - 手动执行：`python scraper.py --cookie <PHPSESSID>`
  - 使用已保存 Cookie：`python scraper.py`
  - 保存 Cookie：`python scraper.py --cookie <值> --save-cookie`

### config.json — 配置文件（运行时自动生成）

- **功能**：存储 base_url、pfx_path、cookie 等配置，避免每次手动输入

### start.bat — Windows 启动脚本

- **功能**：双击运行爬虫

## 文件清单总览

| 操作 | 文件路径 |
| :--- | :--- |
| **新增** | scraper.py |
| **新增** | config.json |
| **新增** | start.bat |
| **新增** | output/等保测评_*.xlsx |

## 测试方式

- 运行 `python scraper.py --cookie 3te7a3rt0bq6vr6oa6ou2v83mn`
- 确认输出 `[OK] 总记录数: 664`，全部 14 页数据获取完成
- 检查 `output/` 目录下生成的 Excel 文件，确认 664 行 24 列数据完整

## 定时任务配置（部署到服务器后）

### 方式一：Windows 任务计划程序（每周执行）

```
schtasks /create /tn "DengbaoScraper" /tr "python E:\path\to\scraper.py" /sc weekly /d MON /st 09:00
```

### 方式二：Linux Crontab（服务器）

```
# 每周一早上 9 点执行
0 9 * * 1 cd /path/to/dengbao-scraper && python3 scraper.py >> scraper.log 2>&1
```

### 手动执行

随时双击 `start.bat` 或命令行运行 `python scraper.py`

### Cookie 过期处理

Session Cookie 会过期，过期后脚本会提示"Session 已过期"。需要重新在浏览器登录后获取新的 PHPSESSID：
1. 浏览器 F12 → Application → Cookies → 复制 PHPSESSID
2. 运行 `python scraper.py --cookie <新值> --save-cookie`
