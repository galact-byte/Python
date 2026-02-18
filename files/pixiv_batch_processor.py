#!/usr/bin/env python3
"""
Pixiv 批量ID处理器
快速从文本中提取ID并生成URL列表
"""

import re
import sys
from pathlib import Path


def extract_pixiv_ids(text):
    """提取所有Pixiv ID并去重"""
    pattern = r'id：(\d+)'
    ids = re.findall(pattern, text)
    # 去重但保持顺序
    unique_ids = list(dict.fromkeys(ids))
    return unique_ids


def save_id_list(ids, filepath):
    """保存ID列表"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for id in ids:
            f.write(f"{id}\n")
    print(f"✓ 保存 {len(ids)} 个ID到: {filepath}")


def save_url_list(ids, filepath):
    """保存URL列表"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for id in ids:
            f.write(f"https://www.pixiv.net/artworks/{id}\n")
    print(f"✓ 保存 {len(ids)} 个URL到: {filepath}")


def process_text(text, output_dir='pixiv_images'):
    """处理文本并生成输出文件"""
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 提取ID
    print("\n正在提取ID...")
    ids = extract_pixiv_ids(text)
    
    if not ids:
        print("❌ 未找到任何ID！")
        return
    
    print(f"✓ 提取到 {len(ids)} 个唯一ID")
    
    # 保存文件
    save_id_list(ids, output_path / 'pixiv_ids.txt')
    save_url_list(ids, output_path / 'pixiv_urls.txt')
    
    # 显示前10个ID作为预览
    print(f"\n前10个ID预览：")
    for i, id in enumerate(ids[:10], 1):
        print(f"  {i}. {id}")
    
    if len(ids) > 10:
        print(f"  ... 还有 {len(ids) - 10} 个")
    
    print(f"\n✓ 完成！所有文件保存在 '{output_dir}/' 目录")
    
    return ids


def main():
    print("=" * 60)
    print("Pixiv ID 批量提取工具")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        # 从文件读取
        input_file = sys.argv[1]
        print(f"\n读取文件: {input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                text = f.read()
            process_text(text)
        except FileNotFoundError:
            print(f"❌ 文件不存在: {input_file}")
        except Exception as e:
            print(f"❌ 读取文件出错: {e}")
    else:
        # 从标准输入读取
        print("\n请粘贴包含ID的文本（完成后按 Ctrl+D (Linux/Mac) 或 Ctrl+Z (Windows) 结束）：")
        print("-" * 60)
        
        try:
            lines = []
            while True:
                try:
                    line = input()
                    lines.append(line)
                except EOFError:
                    break
            
            text = '\n'.join(lines)
            
            if text.strip():
                process_text(text)
            else:
                print("\n❌ 未输入任何内容")
        
        except KeyboardInterrupt:
            print("\n\n操作已取消")


if __name__ == '__main__':
    main()
