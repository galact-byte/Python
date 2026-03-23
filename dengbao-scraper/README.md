# 等保测评数据爬虫

从项目管理系统自动爬取等保测评项目数据，导出为 Excel 文件。

## 功能

- 自动登录（OCR 验证码识别，无需手动操作）
- 全量分页爬取（自动遍历所有页）
- 导出格式化 Excel（24 列字段，带样式/冻结首行/自动筛选）
- 支持定时任务和手动执行两种模式
- Cookie 自动管理（过期自动重新登录）

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

## 使用方法

### 全自动运行（推荐）

```bash
python scraper.py
```

自动完成：登录 → 爬取全部数据 → 导出 Excel 到 `output/` 目录。

### 手动指定 Cookie

如果自动登录失败，可以从浏览器获取 Cookie：

1. 浏览器打开系统页面，F12 → Application → Cookies → 复制 `PHPSESSID` 的值
2. 运行：

```bash
python scraper.py --cookie <PHPSESSID值>
```

### Windows 双击启动

直接双击 `start.bat`。

### 命令行参数

| 参数 | 说明 | 示例 |
|:---|:---|:---|
| `--cookie` | 手动指定 PHPSESSID | `--cookie abc123` |
| `--username` | 登录账号 | `--username admin` |
| `--password` | 登录密码 | `--password 123456` |
| `--pfx` | PFX 证书路径 | `--pfx /path/to/cert.pfx` |
| `--url` | 系统 base URL | `--url https://ip/XYivUozEqQ.php` |
| `--output` | 输出目录 | `--output ./data` |
| `--limit` | 每页数量（默认 50） | `--limit 100` |

## 配置文件

首次运行后会在脚本同目录生成 `config.json`，保存账号、密码、证书路径等配置：

```json
{
  "base_url": "https://10.10.10.215/XYivUozEqQ.php",
  "pfx_path": "C:\\path\\to\\liuxb.pfx",
  "pfx_password": null,
  "username": "liuxb",
  "password": "oa@123456",
  "cookie": "自动保存的session",
  "page_size": 50,
  "output_dir": ""
}
```

部署到服务器时，修改此文件中的 `base_url`、`pfx_path` 即可。

## 定时任务

### Windows 任务计划程序（每周一 9:00）

```
schtasks /create /tn "DengbaoScraper" /tr "python E:\path\to\scraper.py" /sc weekly /d MON /st 09:00
```

### Linux Crontab（每周一 9:00）

```cron
0 9 * * 1 cd /path/to/dengbao-scraper && python3 scraper.py >> scraper.log 2>&1
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
