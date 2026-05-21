"""模板清洗工具

新模板由实际项目（河津国京）填好的版本演变而来，包含两类杂质：
1. 所有勾选项已经按那个项目选过（w:sym F0FE）
2. 单位名称、定级对象名称、业务描述、附件名等单元格预填了具体值

把这些清空后，才能作为通用空白模板使用。
"""

import os
import re
import sys
import shutil
from docx import Document
from docx.oxml.ns import qn


ZH_PROPER_NOUNS = [
    "河津国京新能源开发有限公司",
    "电力监控系统",
    "运城市河津国京新能源开发有限公司变电站继电保护室",
]


def _reset_all_syms(doc):
    """把所有 w:sym 复位为未勾选（Wingdings 2 / char=0030）。"""
    cnt = 0
    for run_el in doc.element.iter(qn('w:r')):
        sym = run_el.find(qn('w:sym'))
        if sym is None:
            continue
        sym.set(qn('w:font'), 'Wingdings 2')
        sym.set(qn('w:char'), '0030')
        cnt += 1
    return cnt


def _clear_pre_filled_text(doc):
    """清除已知的预填具体内容（项目专有名词、《》附件引用、业务描述等）。

    支持跨 run 的 《...》 引用：扫描段落中 run 序列，从含 《 的 run 起，
    到含 》 的 run 止，全部清空。
    """
    cleared_runs = 0

    def _walk_paragraphs(parent):
        for p in parent.iter(qn('w:p')):
            yield p

    def _clear_brace_groups_in_paragraph(p_el):
        nonlocal cleared_runs
        runs = list(p_el.iter(qn('w:r')))
        i = 0
        while i < len(runs):
            t_i = runs[i].find(qn('w:t'))
            if t_i is None or t_i.text is None or '《' not in t_i.text:
                i += 1
                continue
            # 找到结束 》
            j = i
            while j < len(runs):
                t_j = runs[j].find(qn('w:t'))
                if t_j is not None and t_j.text and '》' in t_j.text:
                    break
                j += 1
            if j >= len(runs):
                i += 1
                continue
            # 清空 i..j 之间的 text
            for k in range(i, j + 1):
                tk = runs[k].find(qn('w:t'))
                if tk is not None and tk.text:
                    tk.text = ''
                    cleared_runs += 1
            i = j + 1

    for p_el in _walk_paragraphs(doc.element):
        _clear_brace_groups_in_paragraph(p_el)

    # 然后再扫一遍清除残留专有名词 + 业务描述句
    pattern_biz = re.compile(r'是计算机及其相关的和配套的设备.*?处理的系统。')
    for run_el in doc.element.iter(qn('w:r')):
        t = run_el.find(qn('w:t'))
        if t is None or t.text is None:
            continue
        original = t.text
        new_text = original
        for noun in ZH_PROPER_NOUNS:
            if noun in new_text:
                new_text = new_text.replace(noun, '')
        new_text = pattern_biz.sub('', new_text)
        if new_text != original:
            t.text = new_text
            cleared_runs += 1
    return cleared_runs


def _restore_title_slash(doc):
    """把表标题里被填入的对象名替换回 ` / ` 占位。
    目标段落形如「表二（电力监控系统）定级对象情况」→「表二（ / ）定级对象情况」。
    """
    fixed = 0
    pattern = re.compile(r'（\s*）')
    for p in doc.paragraphs:
        full = p.text
        if '（' in full and '）' in full and re.search(r'表[一二三四五六七八九十]', full):
            # 已被清掉具体值后会留下空 ( )
            if pattern.search(full):
                # 找到含空括号的 run 替换为 「 / 」
                for run in p.runs:
                    if '（' in run.text and '）' in run.text:
                        run.text = run.text.replace('（）', '（ / ）')
                        fixed += 1
    return fixed


def sanitize(in_path: str, out_path: str):
    doc = Document(in_path)
    syms = _reset_all_syms(doc)
    runs = _clear_pre_filled_text(doc)
    titles = _restore_title_slash(doc)
    doc.save(out_path)
    print(f'[OK] {os.path.basename(in_path)} -> {os.path.basename(out_path)}: '
          f'syms={syms}, cleared_runs={runs}, title_slashes={titles}')


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    tpl_dir = os.path.join(root, 'doc_templates')
    beian = os.path.join(tpl_dir, '01-新备案表.docx')
    if not os.path.exists(beian):
        print('备案表模板不存在:', beian)
        return 1

    bak = beian + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(beian, bak)
        print('备份到:', bak)
    sanitize(bak, beian)
    return 0


if __name__ == '__main__':
    sys.exit(main())
