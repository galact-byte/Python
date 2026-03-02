import csv
import json
import os

# 输入文件夹路径
folder_path = input("请输入CSV文件夹路径: ")

# 输入输出JSON文件的路径
output_json_path = input("请输入输出的JSON文件路径: ")

# 获取输出路径的文件夹部分
output_dir = os.path.dirname(output_json_path)

# 如果文件夹不存在，则创建文件夹
if not os.path.exists(output_dir) and output_dir != '':
    os.makedirs(output_dir)

# 用于存储所有原始文本的字典
all_translations = {}

# 遍历文件夹中的所有CSV文件
for filename in os.listdir(folder_path):
    if filename.endswith('.csv'):
        csv_file_path = os.path.join(folder_path, filename)

        # 读取CSV文件
        with open(csv_file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # 提取原始文本
            for row in reader:
                original_text = row['Original Text']

                # 如果原始文本非空，添加到字典
                if original_text:
                    all_translations[original_text] = ""

# 将所有原始文本写入指定路径的JSON文件
with open(output_json_path, mode='w', encoding='utf-8') as jsonfile:
    json.dump(all_translations, jsonfile, ensure_ascii=False, indent=4)

print(f"转换完成！所有原始文本已保存到 '{output_json_path}' 文件。")
