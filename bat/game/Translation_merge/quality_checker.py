#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译质量检查模块
检测漏翻、语序错误等问题
"""

import json
import re
from typing import Dict, List, Tuple
from pathlib import Path


def contains_japanese(text: str) -> bool:
    """检查文本是否包含日文字符（平假名、片假名）"""
    for char in text:
        code = ord(char)
        if (0x3040 <= code <= 0x309F or  # 平假名
                0x30A0 <= code <= 0x30FF):  # 片假名
            return True
    return False


def should_skip_for_quality_check(text: str) -> bool:
    """判断是否应该跳过质量检查（技术内容、符号等）"""
    text = str(text).strip()
    
    # 空文本
    if not text:
        return True
    
    # 纯符号串（如 ーーーーー、・・・・・、◆ーーー◆ 等）
    unique_chars = set(text.replace(' ', '').replace('\u3000', ''))
    if len(unique_chars) <= 3:
        if all(c in 'ー・◆■▲●★☆～…、。！？―_-=+' for c in unique_chars):
            return True
    
    # 游戏脚本标签 <xxx:...>
    if re.match(r'^<[^>]+>$', text):
        return True
    
    # 代码/日志
    if 'console.log' in text or 'function(' in text:
        return True
    
    # 文件名
    if re.match(r'^.*\.(png|jpg|json|motion3\.json|pic)$', text, re.IGNORECASE):
        return True

    # 文件/目录路径（包含2个以上斜杠的路径格式）
    if text.count('/') >= 2 or text.count('\\') >= 2:
        return True
    
    # 纯假名字符表（字体测试）
    if len(text) > 50 and calculate_japanese_ratio(text) > 0.9:
        return True
    
    return False


def calculate_japanese_ratio(text: str) -> float:
    """计算日文字符占比"""
    if not text:
        return 0.0
    
    jp_count = 0
    total_count = 0
    
    for char in text:
        if char.strip():  # 忽略空白字符
            total_count += 1
            code = ord(char)
            if (0x3040 <= code <= 0x309F or  # 平假名
                    0x30A0 <= code <= 0x30FF):  # 片假名
                jp_count += 1
    
    return jp_count / total_count if total_count > 0 else 0.0


def check_missing_translation(original: str, translated: str) -> Tuple[bool, str]:
    """
    检测漏翻
    
    Returns:
        (是否漏翻, 原因描述)
    """
    original = str(original).strip()
    translated = str(translated).strip()
    
    # 1. 原文与译文完全相同
    if original == translated and contains_japanese(original):
        return True, "原文未翻译"
    
    # 2. 译文中日文占比过高
    jp_ratio = calculate_japanese_ratio(translated)
    if jp_ratio > 0.3:
        return True, f"日文占比 {jp_ratio:.0%}"
    
    return False, ""


def check_word_order_errors(translated: str) -> Tuple[bool, str, str]:
    """
    检测语序错误
    
    Returns:
        (是否有错误, 错误类型, 匹配到的内容)
    """
    translated = str(translated).strip()
    
    # 定义检测模式 - 更精确的语序错误模式
    patterns = [
        # 真正的语序错误：数字后直接跟中文动词/介词，但排除正常的 "X对Y" "X到Y" 格式
        # 如 "3请在" 是错误的，但 "2寳1" 是正确的
        (r'\d+请', "语序错误"),  # 如 "3请在日内"
        
        # 数字后跟方位词后跟量词（顺序错误）
        # 如 "1后小时" 应该是 "1小时后"
        (r'\d+(后|前|内|里)(小时|分钟|天|日|年|月|周|次|回|个)', "时间量词错位"),
        
        # 日文残留后紧跟中文
        # 如 "3日请在" 
        (r'\d+[ぁ-んァ-ン]+(请|在|把|被|是|有)', "日文残留"),
        
        # 助词未翻译
        (r'[がはをにでとのもへやかな][，。！？]', "助词未翻译"),
    ]
    
    for pattern, error_type in patterns:
        match = re.search(pattern, translated)
        if match:
            return True, error_type, match.group()
    
    return False, "", ""
    
    for pattern, error_type in patterns:
        match = re.search(pattern, translated)
        if match:
            return True, error_type, match.group()
    
    return False, "", ""


def check_translation_quality(original_file: str, translated_file: str, 
                             check_missing: bool = True,
                             check_order: bool = True) -> Dict:
    """
    检查翻译质量
    
    Args:
        original_file: 原文文件路径
        translated_file: 译文文件路径
        check_missing: 是否检测漏翻
        check_order: 是否检测语序错误
        
    Returns:
        检查结果字典
    """
    # 加载文件
    with open(original_file, 'r', encoding='utf-8') as f:
        original_data = json.load(f)
    
    with open(translated_file, 'r', encoding='utf-8') as f:
        translated_data = json.load(f)
    
    results = {
        "total_entries": len(translated_data),
        "missing_translations": [],
        "word_order_errors": [],
        "summary": {}
    }
    
    for key, translated in translated_data.items():
        original = original_data.get(key, key)
        
        # 跳过技术内容
        if should_skip_for_quality_check(original):
            continue
        
        # 检测漏翻
        if check_missing:
            is_missing, reason = check_missing_translation(original, translated)
            if is_missing:
                results["missing_translations"].append({
                    "key": key,
                    "original": original,
                    "translated": translated,
                    "reason": reason
                })
        
        # 检测语序错误
        if check_order:
            has_error, error_type, matched = check_word_order_errors(translated)
            if has_error:
                results["word_order_errors"].append({
                    "key": key,
                    "original": original,
                    "translated": translated,
                    "error_type": error_type,
                    "matched": matched
                })
    
    # 汇总
    results["summary"] = {
        "missing_count": len(results["missing_translations"]),
        "order_error_count": len(results["word_order_errors"])
    }
    
    return results


def check_with_ai(translator, entries: List[Dict], batch_size: int = 15) -> List[Dict]:
    """
    使用AI检测翻译问题
    
    Args:
        translator: 翻译器实例（用于调用API）
        entries: 要检查的条目列表 [{"original": ..., "translated": ...}, ...]
        batch_size: 每批发送的条目数
        
    Returns:
        有问题的条目列表
    """
    if not entries:
        return []
    
    issues = []
    
    # 分批处理
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        
        # 构建检查prompt
        prompt = """请检查以下日译中翻译，找出存在以下问题的条目：
1. 语序不通顺
2. 翻译不准确或意思偏差
3. 漏译或多译

只输出有问题的编号和简短原因，格式如：
1: 语序混乱
5: 翻译不准确

如果没有问题，输出"无问题"。

翻译列表：
"""
        for idx, entry in enumerate(batch, 1):
            prompt += f"\n{idx}. 原文: {entry['original']}\n   译文: {entry['translated']}\n"
        
        try:
            # 调用API
            response = translator.translate_single(prompt)
            
            # 解析响应
            if "无问题" not in response:
                # 解析出有问题的编号
                for line in response.strip().split('\n'):
                    match = re.match(r'(\d+)[：:]\s*(.+)', line.strip())
                    if match:
                        idx = int(match.group(1)) - 1
                        reason = match.group(2)
                        if 0 <= idx < len(batch):
                            entry = batch[idx]
                            # 过滤无效结果：纯数字、非日文相同内容等
                            orig = str(entry.get('original', '')).strip()
                            trans = str(entry.get('translated', '')).strip()
                            # 跳过纯数字条目
                            if orig.isdigit() or (orig == trans and not contains_japanese(orig)):
                                continue
                            issues.append({
                                **entry,
                                "ai_reason": reason
                            })
        except Exception as e:
            print(f"AI检查出错: {e}")
            continue
    
    return issues


def fix_with_ai(translator, issues: List[Dict], batch_size: int = 10) -> Dict[str, str]:
    """
    使用AI修复翻译问题
    
    Args:
        translator: 翻译器实例
        issues: 问题条目列表 [{"key": ..., "original": ..., "translated": ..., ...}, ...]
        batch_size: 每批处理的条目数
        
    Returns:
        修复后的翻译字典 {key: fixed_translation, ...}
    """
    if not issues:
        return {}
    
    fixed = {}
    
    # 分批处理
    for i in range(0, len(issues), batch_size):
        batch = issues[i:i + batch_size]
        
        # 构建修复prompt
        prompt = """请修正以下日译中翻译中的问题。对于每个条目，请直接输出修正后的中文翻译。

注意：
1. 保持原意，只修正语序或补充漏译
2. 如果是语序问题如"3请在日内"，应改为"请在3日内"
3. 如果是漏译，请翻译成中文
4. 每行一个，格式为：编号. 修正后的翻译

原文和当前译文：
"""
        for idx, item in enumerate(batch, 1):
            prompt += f"\n{idx}. 原文: {item['original']}\n   当前译文: {item['translated']}\n"
        
        try:
            response = translator.translate_single(prompt)
            
            # 解析响应
            lines = response.strip().split('\n')
            for line in lines:
                # 匹配格式：编号. 翻译内容
                match = re.match(r'(\d+)[\.、]\s*(.+)', line.strip())
                if match:
                    idx = int(match.group(1)) - 1
                    fixed_text = match.group(2).strip()
                    if 0 <= idx < len(batch):
                        key = batch[idx].get('key', batch[idx].get('original'))
                        original = batch[idx].get('original', '')
                        old_trans = batch[idx].get('translated', '')
                        
                        # 验证修复结果是否有效
                        # 1. 不应包含prompt污染
                        if '原文:' in fixed_text or '当前译文:' in fixed_text:
                            continue
                        # 2. 不应比原来更差（日文比例不应增加）
                        old_jp_ratio = calculate_japanese_ratio(old_trans)
                        new_jp_ratio = calculate_japanese_ratio(fixed_text)
                        if new_jp_ratio > old_jp_ratio and new_jp_ratio > 0.3:
                            continue
                        # 3. 不应是纯日文
                        if new_jp_ratio > 0.8:
                            continue
                        # 4. 不应为空或太短
                        if len(fixed_text) < 2:
                            continue
                        
                        fixed[key] = fixed_text
        except Exception as e:
            print(f"AI修复出错: {e}")
            continue
    
    return fixed


def apply_fixes(translated_file: str, fixes: Dict[str, str], output_file: str = None) -> int:
    """
    应用修复到翻译文件
    
    Args:
        translated_file: 原译文文件
        fixes: 修复字典 {key: fixed_translation}
        output_file: 输出文件(默认覆盖原文件)
        
    Returns:
        修复的条目数
    """
    with open(translated_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for key, fixed_value in fixes.items():
        if key in data:
            data[key] = fixed_value
            count += 1
    
    output = output_file or translated_file
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return count


def generate_report(results: Dict, output_file: str = None) -> str:
    """
    生成质量检查报告
    
    Args:
        results: 检查结果
        output_file: 输出文件路径（可选）
        
    Returns:
        报告内容
    """
    lines = []
    lines.append("=" * 60)
    lines.append("翻译质量检查报告")
    lines.append("=" * 60)
    lines.append(f"\n总条目数: {results['total_entries']}")
    lines.append(f"漏翻数量: {results['summary']['missing_count']}")
    lines.append(f"语序问题: {results['summary']['order_error_count']}")
    
    if results["missing_translations"]:
        lines.append("\n" + "-" * 60)
        lines.append("📋 漏翻条目")
        lines.append("-" * 60)
        for item in results["missing_translations"][:50]:  # 最多显示50条
            lines.append(f"\n原文: {item['original']}")
            lines.append(f"译文: {item['translated']}")
            lines.append(f"原因: {item['reason']}")
    
    if results["word_order_errors"]:
        lines.append("\n" + "-" * 60)
        lines.append("⚠️ 语序问题")
        lines.append("-" * 60)
        for item in results["word_order_errors"][:50]:
            lines.append(f"\n原文: {item['original']}")
            lines.append(f"译文: {item['translated']}")
            lines.append(f"问题: {item['error_type']} (检测到: {item['matched']})")
    
    if "ai_issues" in results and results["ai_issues"]:
        lines.append("\n" + "-" * 60)
        lines.append("🤖 AI检测问题")
        lines.append("-" * 60)
        for item in results["ai_issues"][:50]:
            lines.append(f"\n原文: {item['original']}")
            lines.append(f"译文: {item['translated']}")
            lines.append(f"AI意见: {item['ai_reason']}")
    
    report = "\n".join(lines)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
    
    return report
