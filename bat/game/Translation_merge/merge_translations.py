#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
游戏翻译JSON文件合并工具
比对两个翻译文件，将已翻译的内容合并到新文件中，并找出需要翻译的新条目
"""

import json
import sys
import re
from pathlib import Path


def try_decode_mojibake(text):
    """
    尝试修复乱码文本（mojibake）
    常见情况：UTF-8文本被误认为是其他编码
    """
    if not text:
        return text, False

    # 检查是否包含可疑的乱码字符
    suspicious_chars = ['�', 'ï', 'â', 'ã', 'ä', 'å', 'æ', 'ç', 'è', 'é']
    has_suspicious = any(char in text for char in suspicious_chars)

    # 检查是否包含大量反斜杠转义
    if '\\x' in text or has_suspicious:
        # 尝试各种编码组合修复
        encoding_pairs = [
            ('cp1252', 'utf-8'),  # Windows误编码
            ('latin1', 'utf-8'),  # ISO-8859-1误编码
            ('cp932', 'utf-8'),  # Shift-JIS误编码
            ('iso-8859-1', 'utf-8'),
        ]

        for wrong_enc, correct_enc in encoding_pairs:
            try:
                # 先用错误的编码encode，再用正确的编码decode
                fixed = text.encode(wrong_enc).decode(correct_enc)
                # 检查修复后是否包含日文字符
                if contains_japanese(fixed):
                    return fixed, True
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue

    return text, False


def contains_japanese(text):
    """检查文本是否包含日文字符（平假名、片假名、汉字）"""
    text = str(text)
    for char in text:
        code = ord(char)
        if (0x3040 <= code <= 0x309F or  # 平假名
                0x30A0 <= code <= 0x30FF or  # 片假名
                0x4E00 <= code <= 0x9FFF):  # 汉字(CJK)
            return True
    return False


def is_skip_entry(key, value):
    """判断是否应该跳过的条目（不需要翻译）"""
    key_str = str(key).strip()
    value_str = str(value).strip()

    # key和value必须相同才考虑跳过（未翻译的条目）
    if key_str != value_str:
        return False

    # 空字符串
    if not value_str:
        return True

    # 纯数字（包含小数点和逗号分隔的坐标）
    if re.match(r'^[\d,\.]+$', value_str):
        return True

    # 游戏脚本标签 <xxx:yyy> 或 <xxx>
    if re.match(r'^<[A-Za-z\u4e00-\u9fffぁ-んァ-ン]+[:：]?.*>$', value_str):
        return True
    
    # 以尖括号包裹的技术标签
    if value_str.startswith('<') and value_str.endswith('>'):
        return True
    
    # 文件引用 (xxx.pic, xxx.png等)
    if re.match(r'^.*\.(pic|png|jpg|mp3|ogg|wav|json|js|txt)$', value_str, re.IGNORECASE):
        return True
    
    # 纯英文标识符 (ST_xxx, map_xxx, block等)
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', value_str):
        return True
    
    # 下划线分隔的技术名称
    if re.match(r'^[A-Za-z0-9_]+$', value_str) and '_' in value_str:
        return True
    
    # 重复的符号串（如 ・・・・・・・・・）
    if len(value_str) >= 3:
        unique_chars = set(value_str.replace(' ', '').replace('　', ''))
        if len(unique_chars) <= 2:
            return True

    # 尝试修复可能的乱码
    fixed_text, was_fixed = try_decode_mojibake(value_str)
    if was_fixed:
        # 如果修复成功，说明原文是日文，不应该跳过
        return False

    # 不包含日文字符的全部跳过（纯英文、符号、代码等）
    if not contains_japanese(value_str):
        return True

    # 纯符号串（重复的■◆▲？！等）
    if len(set(value_str)) <= 3:
        unique_chars = set(value_str)
        if all(c in '■◆▲●？！…：＋－×÷＝　 ' for c in unique_chars):
            return True

    # 包含明显的代码特征
    code_patterns = [
        r'var\s+', r'function\s*\(', r'this\.', r'=>', r'return\s+',
        r'console\.', r'Math\.', r'Graphics\.',
        r'http://', r'https://',
        r'\{.*\}', r'\[.*\]',
        r'\.js', r'\.css', r'\.png', r'\.mp3',
        r'//', r'\\n', r'\\t',
        r'rgba\(', r'url\(',
        r'コモンイベント\d+：',  # 通用事件标签
        r'PictureLive2D',  # Live2D技术标签
    ]
    for pattern in code_patterns:
        if re.search(pattern, value_str):
            return True

    # 包含代码符号的（但允许日文中的全角符号）
    if any(c in value_str for c in ['=', '{', '}', '[', ']', ';']):
        # 如果同时包含这些符号，可能是代码
        return True

    return False


def load_json(filepath):
    """加载JSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取文件失败 {filepath}: {e}")
        sys.exit(1)


def save_json(data, filepath):
    """保存JSON文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 文件已保存: {filepath}")
    except Exception as e:
        print(f"❌ 保存文件失败 {filepath}: {e}")
        sys.exit(1)


def find_json_files(path):
    """在路径中查找JSON文件"""
    path_obj = Path(path)

    # 如果是文件，直接返回
    if path_obj.is_file() and path_obj.suffix.lower() == '.json':
        return [path_obj]

    # 如果是文件夹，查找所有JSON文件
    if path_obj.is_dir():
        json_files = list(path_obj.glob('*.json'))
        return json_files

    return []


def select_file(path_input, description):
    """选择文件，支持文件夹自动查找"""
    path_obj = Path(path_input)

    if not path_obj.exists():
        print(f"❌ 路径不存在: {path_input}")
        sys.exit(1)

    # 如果是文件，直接返回
    if path_obj.is_file():
        if path_obj.suffix.lower() != '.json':
            print(f"❌ 不是JSON文件: {path_input}")
            sys.exit(1)
        return str(path_obj)

    # 如果是文件夹，列出所有JSON文件供选择
    if path_obj.is_dir():
        json_files = list(path_obj.glob('*.json'))

        if not json_files:
            print(f"❌ 文件夹中没有找到JSON文件: {path_input}")
            sys.exit(1)

        if len(json_files) == 1:
            print(f"✅ 自动选择唯一的JSON文件: {json_files[0].name}")
            return str(json_files[0])

        print(f"\n📁 在文件夹中找到 {len(json_files)} 个JSON文件:")
        for idx, file in enumerate(json_files, 1):
            print(f"  {idx}. {file.name}")

        while True:
            try:
                choice = input(f"\n请选择{description} (1-{len(json_files)}): ").strip()
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(json_files):
                    selected = json_files[choice_idx]
                    print(f"✅ 已选择: {selected.name}")
                    return str(selected)
                else:
                    print(f"❌ 请输入 1 到 {len(json_files)} 之间的数字")
            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n👋 已取消操作")
                sys.exit(0)

    print(f"❌ 无效的路径: {path_input}")
    sys.exit(1)


def merge_translations(new_file, old_translated_file, output_file):
    """
    合并翻译文件

    参数:
        new_file: 只有原文的新文件路径
        old_translated_file: 有原文和译文的旧文件路径
        output_file: 输出文件路径
    """
    print("=" * 60)
    print("🔄 开始处理翻译文件...")
    print("=" * 60)

    # 加载文件
    new_data = load_json(new_file)
    old_data = load_json(old_translated_file)

    print(f"\n📖 新文件条目数: {len(new_data)}")
    print(f"📖 旧文件条目数: {len(old_data)}")

    # 创建旧文件的原文->译文映射
    translation_map = {}
    for key, value in old_data.items():
        translation_map[key] = value

    # 合并数据
    merged_data = {}
    matched_count = 0
    new_entries = []
    skipped_count = 0
    fixed_mojibake = []

    for idx, (key, value) in enumerate(new_data.items(), 1):
        if key in translation_map:
            # 找到匹配的原文，复制译文
            merged_data[key] = translation_map[key]
            matched_count += 1
        else:
            # 新增的条目
            # 先尝试修复乱码
            fixed_value, was_fixed = try_decode_mojibake(value)

            if was_fixed:
                # 记录修复的乱码
                merged_data[key] = fixed_value
                fixed_mojibake.append({
                    'index': idx,
                    'original': value,
                    'fixed': fixed_value
                })
                new_entries.append({
                    'index': idx,
                    'key': key,
                    'value': fixed_value,
                    'was_mojibake': True
                })
            else:
                # 未修复的保持原样
                merged_data[key] = value

                # 检查是否应该跳过（不需要翻译的）
                if is_skip_entry(key, value):
                    skipped_count += 1
                else:
                    # 只记录需要翻译的新条目
                    new_entries.append({
                        'index': idx,
                        'key': key,
                        'value': value,
                        'was_mojibake': False
                    })

    # 保存合并后的文件
    save_json(merged_data, output_file)

    # 输出统计信息
    print("\n" + "=" * 60)
    print("📊 处理结果统计")
    print("=" * 60)
    print(f"✅ 匹配并复制的译文: {matched_count} 条")
    print(f"🔧 修复的乱码文本: {len(fixed_mojibake)} 条")
    print(f"⏭️  自动跳过的条目: {skipped_count} 条 (数字/代码/符号/英文)")
    print(f"🆕 需要翻译的新条目: {len(new_entries)} 条 (仅日文文本)")
    print(f"📝 输出文件总条目数: {len(merged_data)} 条")

    # 显示修复的乱码
    if fixed_mojibake:
        print("\n" + "=" * 60)
        print("🔧 已修复的乱码文本")
        print("=" * 60)
        for item in fixed_mojibake[:10]:  # 最多显示前10条
            print(f"\n第 {item['index']} 行:")
            print(f"  原文(乱码): {item['original']}")
            print(f"  修复后: {item['fixed']}")

        if len(fixed_mojibake) > 10:
            print(f"\n... 还有 {len(fixed_mojibake) - 10} 条乱码已修复 ...")

    # 显示新增条目详情
    if new_entries:
        print("\n" + "=" * 60)
        print("🆕 需要翻译的日文新条目详情")
        print("=" * 60)

        # 分别显示普通条目和修复后的条目
        normal_entries = [e for e in new_entries if not e.get('was_mojibake')]
        mojibake_entries = [e for e in new_entries if e.get('was_mojibake')]

        if normal_entries:
            print("\n📝 普通日文条目:")
            for entry in normal_entries[:15]:  # 最多显示前15条
                print(f"  第 {entry['index']} 行: {entry['value']}")
            if len(normal_entries) > 15:
                print(f"  ... 还有 {len(normal_entries) - 15} 条 ...")

        if mojibake_entries:
            print(f"\n🔧 修复后的条目 (共{len(mojibake_entries)}条，已包含在需翻译列表中)")

        # 保存新增条目到单独的文件
        new_entries_file = output_file.replace('.json', '_new_entries.json')
        new_entries_dict = {entry['key']: entry['value'] for entry in new_entries}
        save_json(new_entries_dict, new_entries_file)
        print(f"\n💾 新增条目已单独保存到: {new_entries_file}")
        print(f"   该文件包含 {len(new_entries)} 条需要翻译的日文文本")
        print(f"   (其中 {len(mojibake_entries)} 条是自动修复的乱码)")
    else:
        print("\n✨ 没有新增的日文文本需要翻译！")

    print("\n" + "=" * 60)
    print("✅ 处理完成！")
    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("🎮 游戏翻译JSON文件合并工具 v2.0")
    print("=" * 60)

    # 获取文件路径
    print("\n请提供文件或文件夹路径（可以拖拽到终端）:")
    print("💡 提示: 如果提供文件夹路径，会自动列出其中的JSON文件供选择")

    new_file_input = input("\n📄 新文件（只有原文）路径: ").strip().strip('"').strip("'")
    old_file_input = input("📄 旧文件（有译文）路径: ").strip().strip('"').strip("'")
    output_file = input("💾 输出文件路径（直接回车默认为 merged_translation.json）: ").strip().strip('"').strip("'")

    if not output_file:
        output_file = "merged_translation.json"

    # 选择文件
    new_file = select_file(new_file_input, "新文件（只有原文）")
    old_file = select_file(old_file_input, "旧文件（有译文）")

    # 执行合并
    merge_translations(new_file, old_file, output_file)


if __name__ == "__main__":
    main()