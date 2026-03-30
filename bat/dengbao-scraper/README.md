# 项目进度数据爬虫

从内部项目管理系统自动爬取项目进度数据，导出为 Excel 文件。支持 7 种项目类型。

## 功能

- 自动登录（OCR 验证码识别，无需手动操作）
- 全量分页爬取（自动遍历所有页）
- 导出格式化 Excel（24 列字段，带样式/冻结首行/自动筛选）
- 支持 7 种项目类型，可单选或全部爬取
- Web GUI 界面（浏览器操作，可视化日志）
- Cookie 自动管理（过期自动重新登录）

## 支持的项目类型

| 类型 Key | 名称 | API 路径 |
|:---|:---|:---|
| `dengbao` | 等保测评 | `/djcp/projectstatus/index` |
| `password` | 密码评估 | `/smcp/projectstatus/index` |
| `security` | 安全评估 | `/aqpg/projectstatus/index` |
| `risk` | 风险评估 | `/fxpg/projectstatus/index` |
| `testing` | 软件测试 | `/rjcs/projectstatus/index` |
| `service` | 安全服务 | `/aqfw/projectstatus/index` |
| `comprehensive` | 综合服务 | `/zhfw/projectstatus/index` |

## 依赖

```
requests
cryptography
openpyxl
ddddocr
```

首次运行会自动安装 `openpyxl` 和 `ddddocr`，也可以手动安装：

```bash
pip install requests cryptography openpyxl ddddocr
```

## 配置

复制 `config.example.json` 为 `config.json`，填入实际配置：

```bash
cp config.example.json config.json
```

```json
{
  "base_url": "https://your-server/XYivUozEqQ.php",
  "pfx_path": "C:\\path\\to\\your.pfx",
  "pfx_password": null,
  "username": "your_username",
  "password": "your_password",
  "cookie": "",
  "page_size": 50,
  "output_dir": ""
}
```

| 字段 | 说明 |
|------|------|
| `base_url` | 项目管理系统地址 |
| `pfx_path` | 客户端 PFX 证书路径（用于 HTTPS 双向认证） |
| `pfx_password` | PFX 密码，无密码填 `null` |
| `username` / `password` | 系统登录账号密码 |
| `cookie` | PHPSESSID，留空则自动登录（OCR 验证码） |
| `page_size` | 每页爬取数量，默认 50 |
| `output_dir` | 输出目录，留空则默认 `output/` |

> `config.json` 包含敏感凭据，已在 `.gitignore` 中忽略。

## 使用方法

### CLI 模式

```bash
# 默认爬取等保测评
python scraper.py

# 指定项目类型
python scraper.py --type password

# 爬取全部类型
python scraper.py --type all

# 手动指定 Cookie（跳过自动登录）
python scraper.py --cookie <PHPSESSID值>
```

#### 命令行参数

| 参数 | 说明 | 示例 |
|:---|:---|:---|
| `--type` | 项目类型，默认 `dengbao`，可选 `all` | `--type all` |
| `--cookie` | 手动指定 PHPSESSID | `--cookie abc123` |
| `--username` | 登录账号 | `--username admin` |
| `--password` | 登录密码 | `--password 123456` |
| `--pfx` | PFX 证书路径 | `--pfx /path/to/cert.pfx` |
| `--url` | 系统 base URL | `--url https://ip/XYivUozEqQ.php` |
| `--output` | 输出目录 | `--output ./data` |
| `--limit` | 每页数量（默认 50） | `--limit 100` |

### Web GUI 模式

```bash
python gui.py
```

浏览器自动打开 `http://localhost:5050`，支持：
- 多选项目类型，一键爬取
- 实时日志输出
- 文件下载管理
- 在线修改连接配置

### Windows 双击启动

直接双击 `start.bat`。

## 定时任务

### Windows 任务计划程序（每周一 9:00）

```
schtasks /create /tn "DengbaoScraper" /tr "python E:\path\to\scraper.py --type all" /sc weekly /d MON /st 09:00
```

### Linux Crontab（每周一 9:00）

```cron
0 9 * * 1 cd /path/to/dengbao-scraper && python3 scraper.py --type all >> scraper.log 2>&1
```

## 导出字段

| 列名 | 来源 |
|:---|:---|
| 系统编号 | system_id |
| 系统名称 | hand.systemname |
| 客户名称 | hand.customername |
| 系统级别 | hand.systemlevel |
| 系统标签 | hand.systemtag |
| 业务类型 | hand.businesstype |
| 项目名称 | setup.projectname |
| 项目编号 | setup.project_id |
| 项目地点 | setup.belongcity |
| 立项状态 | setup.initstatus |
| 项目经理 | hand.projectmanager |
| 项目部门 | hand.pmdepartment |
| 销售负责人 | setup.salewheel |
| 要求进场时间 | hand.pstartdate |
| 要求完结时间 | hand.pfinishdate |
| 实施开始日期 | startdate |
| 实施结束日期 | finishdate |
| 项目状态 | projectstatus_text |
| 是否完结 | isfinish_text |
| 方案打印 | isplanprint |
| 报告打印 | isreportprint |
| 备案状态 | hand.isregister_text |
| 合同状态 | hand.contractstatus_text |
| 备注 | remark |
