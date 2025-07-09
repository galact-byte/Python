import os
import pandas as pd

# 输入路径
folder_path = input("请输入文件夹路径：").strip()

# 检验目录是否存在
if not os.path.isdir(folder_path):
    print("错误：文件夹路径不存在")
    exit(1)

# 导出格式
print("请输入导出格式:")
export_format = input("1.txt, 2.xlsx（默认txt）: ").strip()
if export_format == "" or export_format == "1" or export_format.lower() == "txt":
    export_format = "txt"
elif export_format == "2" or export_format.lower() == "xlsx":
    export_format = "xlsx"
else:
    print("错误：只支持导出为txt或xlsx")
    exit(1)

# 输出路径（可留空）
default_name = "output.txt" if export_format == "txt" else "output.xlsx"
output_file = input(f"请输入导出文件的路径（默认当前目录下的 {default_name}）：").strip()

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 处理导出路径
if output_file == "":
    output_file = os.path.join(script_dir, default_name)
elif os.path.isdir(output_file):
    output_file = os.path.join(output_file, default_name)
elif not os.path.isabs(output_file):
    output_file = os.path.join(script_dir, output_file)

# 获取不带扩展名的所有文件（递归）
file_names = [
    os.path.splitext(file)[0]
    for root, _, files in os.walk(folder_path)
    for file in files
]

# 写入文件
try:
    if export_format == "txt":
        with open(output_file, 'w', encoding='utf-8') as f:
            for name in file_names:
                f.write(f'{name}\n')
    else:
        df = pd.DataFrame({'文件名': file_names})
        df.to_excel(output_file, index=False)
    print(f'已成功导出 {len(file_names)} 个文件名到：{output_file}')
except Exception as e:
    print(f'写入文件时出错：{e}')
