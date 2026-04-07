"""新文档生成 — 精准 run 级填充，保留模版格式"""

import os
import shutil
import re
from copy import deepcopy
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, RGBColor, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from models.project_data import ProjectData, ReportInfo
from core.format_style import (
    set_cell_text, FONT_FANG_GB, FONT_SONG, SIZE_TABLE, INDENT_2CHAR, _set_east_asia_font
)


FONT_REPORT_TITLE = "方正小标宋简体"
SIZE_REPORT_TITLE = Pt(22)
SIZE_REPORT_BODY = Pt(14)


# ══════════════════════════════════════════════════════
#  底层工具函数
# ══════════════════════════════════════════════════════

def _highlight_run(run, color="yellow"):
    """给 run 添加高亮色"""
    rpr = run._element.get_or_add_rPr()
    for node in list(rpr):
        if node.tag == qn('w:highlight'):
            rpr.remove(node)
    highlight = OxmlElement('w:highlight')
    highlight.set(qn('w:val'), color)
    rpr.append(highlight)


def _clear_run_highlight(run):
    """移除 run 上已有高亮。"""
    rpr = run._element.get_or_add_rPr()
    for node in list(rpr):
        if node.tag == qn('w:highlight'):
            rpr.remove(node)


def _highlight_cell(cell, color="yellow"):
    """给单元格中所有 run 添加高亮"""
    for para in cell.paragraphs:
        for run in para.runs:
            _highlight_run(run, color)


def _apply_fill_style(run):
    """统一填写内容样式为宋体五号。"""
    if run is None:
        return
    run.font.name = FONT_SONG
    run.font.size = Pt(10.5)
    _set_east_asia_font(run, FONT_SONG)


def _set_run_font_slots(run, east_asia_font=None, western_font=None):
    if run is None:
        return
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    if western_font:
        run.font.name = western_font
        rfonts.set(qn('w:ascii'), western_font)
        rfonts.set(qn('w:hAnsi'), western_font)
        rfonts.set(qn('w:cs'), western_font)
    if east_asia_font:
        rfonts.set(qn('w:eastAsia'), east_asia_font)


def _insert_paragraph_after(paragraph):
    """在指定段落后插入一个新段落。"""
    new_p = OxmlElement('w:p')
    paragraph._p.addnext(new_p)
    return Paragraph(new_p, paragraph._parent)


def _apply_report_title_format(paragraph):
    """统一报告标题格式：方正小标宋简体二号。"""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = None
    for run in paragraph.runs:
        run.font.bold = None
        run.font.size = SIZE_REPORT_TITLE
        _set_run_font_slots(
            run,
            east_asia_font=FONT_REPORT_TITLE,
            western_font=FONT_REPORT_TITLE,
        )


def _apply_report_body_format(paragraph):
    """统一报告正文格式：仿宋_GB2312 四号，首行缩进两字符。"""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.first_line_indent = INDENT_2CHAR
    for run in paragraph.runs:
        run.font.bold = None
        run.font.size = SIZE_REPORT_BODY
        _set_run_font_slots(
            run,
            east_asia_font=FONT_FANG_GB,
            western_font="Times New Roman",
        )


def _set_run_text(run, text):
    run.text = text
    if run.font.size is None:
        run.font.size = Pt(10.5)
    raw_text = str(text or "")
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", raw_text))
    has_western = bool(re.search(r"[A-Za-z0-9@.\-_/]", raw_text))
    if has_chinese:
        _set_run_font_slots(
            run,
            east_asia_font=FONT_FANG_GB,
            western_font="Times New Roman" if has_western else (run.font.name or "Times New Roman"),
        )
    elif has_western:
        _set_run_font_slots(run, western_font="Times New Roman")


def _fill_text_into_underscores(text, value, min_tail=0):
    value = str(value or "")
    if "_" not in text:
        return value
    return re.sub(r"_+", value, text, count=1)


def _is_placeholder_text(text):
    if text is None:
        return False
    stripped = text.strip()
    return (not stripped) or all(ch in " _\u3000" for ch in text) or "_" in text


def _parse_date_parts(value):
    raw = str(value or "").strip()
    if not raw:
        return "", "", ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        year, month, day = raw.split("-")
        return year, str(int(month)), str(int(day))
    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", raw)
    if match:
        year, month, day = match.groups()
        return year, str(int(month)), str(int(day))
    return raw, "", ""


def _fill_date_cell(cell, value):
    year, month, day = _parse_date_parts(value)
    if not year:
        return False
    parts = [year, month, day]
    part_idx = 0
    for para in cell.paragraphs:
        runs = para.runs
        for idx, run in enumerate(runs):
            if any(mark in run.text for mark in ("年", "月", "日")) and idx > 0:
                prev_run = runs[idx - 1]
                if _is_placeholder_text(prev_run.text) and part_idx < len(parts):
                    _set_run_text(prev_run, parts[part_idx])
                    part_idx += 1
        if part_idx >= len(parts):
            return True
    return part_idx > 0


def _check_first_sym_in_paragraph(paragraph, checked):
    if paragraph is None:
        return
    for run in paragraph.runs:
        if run._element.find(qn('w:sym')) is not None:
            _check_sym(run, checked)
            return


# ══════════════════════════════════════════════════════
#  底层工具函数
# ══════════════════════════════════════════════════════

def _check_sym(run, checked=True):
    """将 run 中的 w:sym 元素设为勾选或未勾选"""
    sym = run._element.find(qn('w:sym'))
    if sym is None:
        return
    if checked:
        sym.set(qn('w:font'), 'Wingdings')
        sym.set(qn('w:char'), 'F0FE')
    else:
        # 恢复为未勾选（保持原始字体）
        current_font = sym.get(qn('w:font'))
        if current_font == 'Wingdings':
            sym.set(qn('w:font'), 'Wingdings 2')
        sym.set(qn('w:char'), '0030')


def _find_and_check(cell, match_text, multi=False):
    """
    在单元格中查找 match_text 对应选项并打勾。
    match_text 可以是选项编号（如"4"）或选项文字（如"企业"）。
    multi=True 时可同时勾选多个匹配项。

    结构: [sym_run][编号_run][文字_run][空格_run] [sym_run][编号_run]...
    sym_run 在编号/文字 run 的前面。
    """
    for para in cell.paragraphs:
        runs = para.runs
        for i, run in enumerate(runs):
            sym = run._element.find(qn('w:sym'))
            if sym is None:
                continue
            # 找 sym 后面的选项编号和文字
            option_parts = []
            for j in range(i + 1, min(i + 4, len(runs))):
                next_run = runs[j]
                # 碰到下一个 sym 就停
                if next_run._element.find(qn('w:sym')) is not None:
                    break
                text = next_run.text.strip()
                if text:
                    option_parts.append(text)

            option_str = ''.join(option_parts)
            # 匹配：编号匹配、文字匹配、或编号+文字匹配
            if (match_text in option_parts or
                match_text in option_str or
                any(match_text == p for p in option_parts)):
                _check_sym(run, True)
                if not multi:
                    return True
    return False


def _find_and_check_multiple(cell, match_texts):
    """勾选多个选项"""
    for text in match_texts:
        if text:
            _find_and_check(cell, text, multi=True)


def _fill_run(cell, para_idx, run_idx, text):
    """精准替换指定位置 run 的文本，不动其他 run"""
    try:
        para = cell.paragraphs[para_idx]
        run = para.runs[run_idx]
        run.text = text
    except (IndexError, AttributeError):
        pass


def _fill_after_keyword(cell, keyword, text):
    """在单元格中找到 keyword 后面的空白/下划线 run，填入 text"""
    for para in cell.paragraphs:
        runs = para.runs
        found_keyword = False
        for i, run in enumerate(runs):
            if keyword in run.text:
                found_keyword = True
                continue
            if found_keyword and (run.text.strip() == '' or
                                   all(c in ' _\u3000' for c in run.text)):
                if '_' in run.text:
                    _fill_placeholder_run(run, text)
                else:
                    _set_run_text(run, '  ' + text)
                return True
    return False


def _copy_run_style(src_run, dst_run):
    """复制 run 的基础字体样式。"""
    if src_run is None or dst_run is None:
        return
    src_rpr = src_run._element.rPr
    if src_rpr is not None:
        dst_rpr = dst_run._element.rPr
        if dst_rpr is not None:
            dst_run._element.remove(dst_rpr)
        dst_run._element.insert(0, deepcopy(src_rpr))
    dst_run.font.name = src_run.font.name
    dst_run.font.size = src_run.font.size
    dst_run.font.bold = src_run.font.bold
    dst_run.font.italic = src_run.font.italic


def _insert_run_after(run):
    """在当前 run 后插入一个新 run，并保留段落归属。"""
    if run is None:
        return None
    paragraph = run._parent
    new_run = paragraph.add_run("")
    run._element.addnext(new_run._element)
    return new_run


def _fill_placeholder_run(run, value, pattern=r"_+"):
    """
    仅替换当前 run 中命中的下划线占位段，并让填充值本身保留下划线效果。
    不再把 `_` 字符残留在填充值后面。
    """
    if run is None:
        return False
    value = str(value or "")
    if not value:
        return False
    original_text = run.text or ""
    match = re.search(pattern, original_text)
    if not match:
        return False

    prefix = original_text[:match.start()]
    suffix = original_text[match.end():]

    if prefix:
        fill_run = _insert_run_after(run)
        if fill_run is None:
            return False
        _copy_run_style(run, fill_run)
        suffix_run = None
        if suffix:
            suffix_run = _insert_run_after(fill_run)
            if suffix_run is None:
                return False
            _copy_run_style(run, suffix_run)
        _set_run_text(run, prefix)
    else:
        fill_run = run
        suffix_run = None
        if suffix:
            suffix_run = _insert_run_after(run)
            if suffix_run is None:
                return False
            _copy_run_style(run, suffix_run)

    _set_run_text(fill_run, value)
    fill_run.font.underline = True

    if suffix_run is not None:
        _set_run_text(suffix_run, suffix)

    return True


def _fill_other_option(cell, option_label, text):
    """在“其他_____”这类选项后填充补充文本。"""
    if not text:
        return False
    for para in cell.paragraphs:
        runs = para.runs
        for i, run in enumerate(runs):
            if option_label in run.text:
                for j in range(i + 1, len(runs)):
                    target = runs[j]
                    if '_' in target.text or target.text.strip() == '':
                        if '_' in target.text:
                            _fill_placeholder_run(target, text)
                        else:
                            _set_run_text(target, text)
                        return True
    return False


def _fill_underline_in_paragraph(paragraph, index, value):
    """将段落中第 index 个下划线 run 替换为值。"""
    count = -1
    for run in paragraph.runs:
        if '_' not in run.text:
            continue
        count += 1
        if count == index:
            _fill_placeholder_run(run, value)
            return True
    return False


def _fill_numbered_lines(cell, values):
    """按段落顺序填充“1xxx____ / 2xxx____”这类多行下划线。"""
    values = [str(v).strip() for v in values if str(v).strip()]
    if not values:
        return False
    value_idx = 0
    for para in cell.paragraphs:
        for run in para.runs:
            if '_' in run.text and value_idx < len(values):
                if _fill_placeholder_run(run, values[value_idx]):
                    value_idx += 1
                    break
        if value_idx >= len(values):
            return True
    return value_idx > 0


def _fill_option_line(cell, code, value):
    code = str(code or "").strip()
    value = str(value or "").strip()
    if not code or not value:
        return False
    for para in cell.paragraphs:
        para_text = "".join(run.text for run in para.runs).strip()
        if not para_text.startswith(code):
            continue
        for run in para.runs:
            if "_" in run.text:
                return _fill_placeholder_run(run, value)
    return False


def _safe_set_value(table, row, col, text):
    """
    安全设置「纯值单元格」的文本。
    适用于整个单元格就是值的情况（如单位名称、信用代码等）。
    保留第一个 run 的格式，清除其他 run。
    """
    if not text or not str(text).strip():
        return
    try:
        cell = table.rows[row].cells[col]
        for p in cell.paragraphs:
            if p.runs:
                style_run = p.runs[0]
                _set_run_text(p.runs[0], str(text))
                _copy_run_style(style_run, p.runs[0])
                _set_run_text(p.runs[0], str(text))
                for run in p.runs[1:]:
                    run.text = ''
                return
        # 没有 run 则新建
        if cell.paragraphs:
            run = cell.paragraphs[0].add_run(str(text))
            if cell.paragraphs[0].runs:
                _copy_run_style(cell.paragraphs[0].runs[0], run)
            _set_run_text(run, str(text))
    except (IndexError, AttributeError):
        pass


# ══════════════════════════════════════════════════════
#  备案表生成
# ══════════════════════════════════════════════════════

def generate_beian(template_path: str, output_path: str, data: ProjectData, highlighted_fields=None):
    """基于新备案表模版生成填充后的备案表（精准填充）"""
    if highlighted_fields is None:
        highlighted_fields = []
    shutil.copy2(template_path, output_path)
    doc = Document(output_path)

    if len(doc.tables) < 7:
        raise ValueError(f"模版表格数不足: 期望>=7, 实际{len(doc.tables)}")

    u = data.unit
    tgt = data.target
    g = data.grading
    target_name = tgt.name or data.project_name  # 定级对象名（用于表标题）
    unit_name = u.unit_name                       # 单位名称（用于封面）

    # ── 封面：备案单位填写 ──
    # 段12: run[7] 是"备案单位："后的空格占位
    if unit_name:
        for p in doc.paragraphs:
            full = p.text
            if '备' in full and '案' in full and '单' in full and '位' in full and '盖章' in full and '受理' not in full:
                # 找到"备案单位"标签 run，复制其格式
                label_run = None
                for run in p.runs:
                    if '备' in run.text or '案' in run.text or '单' in run.text or '位' in run.text:
                        label_run = run
                        break
                for run in p.runs:
                    if run.text.strip() == '' and len(run.text) >= 3:
                        run.text = unit_name
                        # 复制标签 run 的字体格式
                        if label_run:
                            run.font.name = label_run.font.name
                            run.font.size = label_run.font.size
                            run.font.bold = label_run.font.bold
                            if label_run.font.name:
                                _set_east_asia_font(run, label_run.font.name)
                        break
                break

    # ── 表标题替换 （ / ） → （定级对象名） ──
    if target_name:
        for p in doc.paragraphs:
            if '（ / ）' in p.text:
                for run in p.runs:
                    if '（ / ）' in run.text:
                        run.text = run.text.replace('（ / ）', f'（{target_name}）')
                    elif '/' in run.text and run.text.strip() in ['/', '/ ']:
                        run.text = run.text.replace('/', target_name)

    # ══════ 表2: 单位信息 (index 1, 8列) ══════
    t2 = doc.tables[1]

    # 纯值字段：直接替换整个值区域
    _safe_set_value(t2, 0, 1, u.unit_name)      # 单位名称
    _safe_set_value(t2, 1, 1, u.credit_code)     # 信用代码

    # 地址：精准填空（只替换空格占位 run）
    _fill_address(t2.rows[2].cells[1], u.province, u.city, u.county, u.address)

    _safe_set_value(t2, 3, 1, u.postal_code)     # 邮编
    _safe_set_value(t2, 3, 6, u.admin_code)       # 行政区划代码

    # 负责人
    _safe_set_value(t2, 4, 2, u.leader.name)
    _safe_set_value(t2, 4, 6, u.leader.title)
    _safe_set_value(t2, 5, 2, u.leader.office_phone)
    _safe_set_value(t2, 5, 6, u.leader.email)

    # 安全责任部门
    _safe_set_value(t2, 6, 1, u.security_dept)
    _safe_set_value(t2, 7, 2, u.security_contact.name)
    _safe_set_value(t2, 7, 6, u.security_contact.title)
    _safe_set_value(t2, 8, 2, u.security_contact.office_phone)
    _safe_set_value(t2, 8, 6, u.security_contact.email)
    _safe_set_value(t2, 9, 2, u.security_contact.mobile)
    _safe_set_value(t2, 9, 6, u.security_contact.email)

    # 数据安全部门
    _safe_set_value(t2, 10, 1, u.data_dept)
    _safe_set_value(t2, 11, 2, u.data_contact.name)
    _safe_set_value(t2, 11, 6, u.data_contact.title)
    _safe_set_value(t2, 12, 2, u.data_contact.office_phone)
    _safe_set_value(t2, 12, 6, u.data_contact.email)
    _safe_set_value(t2, 13, 2, u.data_contact.mobile)
    _safe_set_value(t2, 13, 6, u.data_contact.email)

    # 隶属关系（勾选）
    if u.affiliation:
        code = u.affiliation.split('-')[0] if '-' in u.affiliation else u.affiliation
        _find_and_check(t2.rows[14].cells[1], code)

    # 单位类型（勾选）
    if u.unit_type:
        code = u.unit_type.split('-')[0] if '-' in u.unit_type else u.unit_type
        _find_and_check(t2.rows[15].cells[1], code)

    # 行业类别（勾选）- 行16的单元格结构比较特殊，数字编号在不同run中
    if u.industry:
        code = u.industry.split('-')[0] if '-' in u.industry else u.industry
        _find_and_check(t2.rows[16].cells[1], code)

    # 定级对象数量
    _safe_set_value(t2, 17, 1, u.current_total)
    _safe_set_value(t2, 17, 3, u.current_level2)
    _safe_set_value(t2, 17, 7, u.current_level3)
    _safe_set_value(t2, 18, 3, u.current_level4)
    _safe_set_value(t2, 18, 7, u.current_level5)
    _safe_set_value(t2, 19, 1, u.all_total)
    _safe_set_value(t2, 19, 3, u.all_level1)
    _safe_set_value(t2, 19, 7, u.all_level2)
    _safe_set_value(t2, 20, 3, u.all_level3)
    _safe_set_value(t2, 20, 7, u.all_level4)
    _safe_set_value(t2, 21, 3, u.all_level5)

    # ══════ 表3: 定级对象 (index 2, 9列) ══════
    t3 = doc.tables[2]
    _safe_set_value(t3, 0, 2, tgt.name)

    # 编号填入各独立单元格
    code = tgt.code
    row0 = t3.rows[0].cells
    seen = set()
    code_idx = 0
    for i in range(4, len(row0)):
        cell_id = id(row0[i])
        if cell_id not in seen:
            seen.add(cell_id)
            if code_idx < len(code):
                _safe_set_value(t3, 0, i, code[code_idx])
                code_idx += 1

    # 定级对象类型（勾选）
    type_cell = t3.rows[1].cells[2]
    if tgt.target_type:
        _find_and_check(type_cell, tgt.target_type)
    # 技术类型多选
    if tgt.tech_type:
        for tech in tgt.tech_type.split(','):
            tech = tech.strip()
            if tech:
                _find_and_check(type_cell, tech, multi=True)

    # 业务类型（勾选）
    if tgt.biz_type:
        code = tgt.biz_type.split('-')[0] if '-' in tgt.biz_type else tgt.biz_type
        _find_and_check(t3.rows[2].cells[2], code)
        if code == '9' and tgt.biz_type_other:
            _fill_other_option(t3.rows[2].cells[2], '其他', tgt.biz_type_other)

    # 业务描述（纯值）
    _safe_set_value(t3, 3, 2, tgt.biz_desc)

    # 服务范围（勾选）
    if tgt.service_scope:
        code = tgt.service_scope.split('-')[0] if '-' in tgt.service_scope else tgt.service_scope
        _find_and_check(t3.rows[4].cells[2], code)
        service_scope_other = tgt.service_scope_other or ('本单位' if code == '99' else '')
        if code == '99' and service_scope_other:
            _fill_other_option(t3.rows[4].cells[2], '其它', service_scope_other)

    # 服务对象（勾选）
    if tgt.service_target:
        code = tgt.service_target.split('-')[0] if '-' in tgt.service_target else tgt.service_target
        _find_and_check(t3.rows[5].cells[2], code)
        if code == '9' and tgt.service_target_other:
            _fill_other_option(t3.rows[5].cells[2], '其他', tgt.service_target_other)

    # 部署范围（勾选）
    if tgt.deploy_scope:
        code = tgt.deploy_scope.split('-')[0] if '-' in tgt.deploy_scope else tgt.deploy_scope
        _find_and_check(t3.rows[6].cells[2], code)
        if code == '9' and tgt.deploy_scope_other:
            _fill_other_option(t3.rows[6].cells[2], '其他', tgt.deploy_scope_other)

    # 网络性质（勾选）
    if tgt.network_type:
        code = tgt.network_type.split('-')[0] if '-' in tgt.network_type else tgt.network_type
        _find_and_check(t3.rows[7].cells[2], code)
        if code == '2':
            _fill_numbered_lines(t3.rows[7].cells[2], [tgt.source_ip, tgt.domain, tgt.protocol_port])
        if code == '9' and tgt.network_type_other:
            _fill_other_option(t3.rows[7].cells[2], '其他', tgt.network_type_other)

    # 网络互联（勾选）
    if tgt.interconnect:
        code = tgt.interconnect.split('-')[0] if '-' in tgt.interconnect else tgt.interconnect
        _find_and_check(t3.rows[8].cells[2], code)
        interconnect_other = tgt.interconnect_other or ('无连接' if code == '9' else '')
        if code == '9' and interconnect_other:
            _fill_other_option(t3.rows[8].cells[2], '其它', interconnect_other)

    # 运行时间（纯值）
    _fill_date_cell(t3.rows[9].cells[2], tgt.run_date)

    # 是否分系统（勾选）
    if tgt.is_subsystem:
        _find_and_check(t3.rows[10].cells[2], tgt.is_subsystem)

    # 上级系统
    _safe_set_value(t3, 11, 2, tgt.parent_system or '/')
    _safe_set_value(t3, 12, 2, tgt.parent_unit or '/')

    # ══════ 表4: 定级等级 (index 3, 5列) ══════
    t4 = doc.tables[3]

    biz_row_map = {"第一级": 1, "第二级": 2, "第三级": 3, "第四级": 4, "第五级": 5}
    svc_row_map = {"第一级": 6, "第二级": 7, "第三级": 8, "第四级": 9, "第五级": 10}

    if g.biz_level in biz_row_map:
        _check_paragraph_items(t4.rows[biz_row_map[g.biz_level]].cells[1], g.biz_level_items)
        _check_first_sym_in_paragraph(t4.rows[biz_row_map[g.biz_level]].cells[4].paragraphs[0], True)
    if g.service_level in svc_row_map:
        _check_paragraph_items(t4.rows[svc_row_map[g.service_level]].cells[1], g.service_level_items)
        _check_first_sym_in_paragraph(t4.rows[svc_row_map[g.service_level]].cells[4].paragraphs[0], True)
    if g.final_level:
        _find_and_check(t4.rows[11].cells[2], g.final_level, multi=True)

    # 定级时间
    _fill_date_cell(t4.rows[12].cells[2], g.grading_date)

    # 定级报告（勾选有/无 + 填附件名）
    report_cell = t4.rows[13].cells[2]
    if g.has_report:
        _find_and_check(report_cell, '有')
    else:
        _find_and_check(report_cell, '无')
    if g.report_name:
        _fill_after_keyword(report_cell, '附件名称', g.report_name)

    # 专家评审（勾选 + 附件名）
    review_cell = t4.rows[14].cells[2]
    if g.has_review:
        _find_and_check(review_cell, '已评审')
    else:
        _find_and_check(review_cell, '未评审')
    if g.review_name:
        _fill_after_keyword(review_cell, '附件名称', g.review_name)

    # 上级主管部门
    supervisor_cell = t4.rows[15].cells[2]
    if g.has_supervisor:
        _find_and_check(supervisor_cell, '有')
    else:
        _find_and_check(supervisor_cell, '无')

    _safe_set_value(t4, 16, 2, g.supervisor_name or '/')
    audit_cell = t4.rows[17].cells[2]
    audit_status = g.supervisor_review_status or ('已审核' if g.supervisor_reviewed else '未审核')
    _find_and_check(audit_cell, audit_status)
    if audit_status == '已审核' and g.supervisor_doc:
        _fill_after_keyword(audit_cell, '附件名称', g.supervisor_doc)

    # 填表人 / 填表日期
    _safe_set_value(t4, 18, 0, f"填表人：{g.filler}")
    _fill_date_cell(t4.rows[18].cells[3], g.fill_date)

    # ══════ 表5: 应用场景 (index 4) — 保持模版默认，仅填已有数据 ══════
    if len(doc.tables) > 4:
        t5 = doc.tables[4]
        sc = data.scenario
        if sc.cloud.enabled:
            _find_and_check(t5.rows[0].cells[2], '是')
            if sc.cloud.role:
                if sc.cloud.role == '二者均勾选':
                    _find_and_check(t5.rows[1].cells[2], '云服务商', multi=True)
                    _find_and_check(t5.rows[1].cells[2], '云服务客户', multi=True)
                else:
                    _find_and_check(t5.rows[1].cells[2], sc.cloud.role, multi=True)
            if sc.cloud.service_model:
                _find_and_check(t5.rows[2].cells[2], sc.cloud.service_model)
                if sc.cloud.service_model == '其他' and sc.cloud.service_model_other:
                    _fill_other_option(t5.rows[2].cells[2], '其他', sc.cloud.service_model_other)
            if sc.cloud.deploy_model:
                _find_and_check(t5.rows[3].cells[2], sc.cloud.deploy_model)
                if sc.cloud.deploy_model == '其他' and sc.cloud.deploy_model_other:
                    _fill_other_option(t5.rows[3].cells[2], '其他', sc.cloud.deploy_model_other)
            if sc.cloud.role in ('云服务商', '二者均勾选'):
                _fill_underline_field(t5.rows[5].cells[2], sc.cloud.provider_scale)
                _safe_set_value(t5, 6, 2, sc.cloud.infra_location)
                _safe_set_value(t5, 7, 2, sc.cloud.ops_location)
            if sc.cloud.role in ('云服务客户', '二者均勾选'):
                _fill_cloud_provider_line(
                    t5.rows[9].cells[2],
                    sc.cloud.provider_name,
                    sc.cloud.platform_level or '三级',
                    sc.cloud.platform_name,
                    _normalize_platform_code(sc.cloud.platform_code),
                )
                _safe_set_value(t5, 10, 2, sc.cloud.client_ops_location)
                if sc.cloud.platform_cert:
                    _fill_after_keyword(t5.rows[11].cells[2], '附件', sc.cloud.platform_cert)
        else:
            _find_and_check(t5.rows[0].cells[2], '否')
        _find_and_check(t5.rows[12].cells[2], '是' if sc.mobile.enabled else '否')
        if sc.mobile.enabled:
            _safe_set_value(t5, 13, 2, sc.mobile.app_name)
            if sc.mobile.wireless:
                _find_and_check(t5.rows[14].cells[2], sc.mobile.wireless, multi=True)
            if sc.mobile.terminal:
                _find_and_check(t5.rows[15].cells[2], sc.mobile.terminal, multi=True)
        _find_and_check(t5.rows[16].cells[2], '是' if sc.iot.enabled else '否')
        _find_and_check(t5.rows[19].cells[2], '是' if sc.ics.enabled else '否')
        _find_and_check(t5.rows[22].cells[2], '是' if sc.bigdata.enabled else '否')
        if sc.bigdata.enabled and sc.bigdata.cross_border:
            _find_and_check(t5.rows[24].cells[2], sc.bigdata.cross_border, multi=True)

    # ══════ 表6: 附件清单 (index 5) — 勾选有/无 ══════
    if len(doc.tables) > 5:
        t6 = doc.tables[5]
        att = data.attachment
        items = [
            (0, att.topology), (1, att.org_policy), (2, att.design_plan),
            (3, att.product_list), (4, att.service_list), (5, att.supervisor_doc)
        ]
        for row_idx, item in items:
            cell = t6.rows[row_idx].cells[1]
            if item.has_file:
                _find_and_check(cell, '有')
                if item.file_name:
                    _fill_after_keyword(cell, '附件名称', item.file_name)
            else:
                _find_and_check(cell, '无')

    # ══════ 表7: 数据信息 (index 6) ══════
    if len(doc.tables) > 6:
        t7 = doc.tables[6]
        d = data.data
        _safe_set_value(t7, 0, 1, d.data_name)
        if d.data_level:
            code = d.data_level.split('-')[0] if '-' in d.data_level else d.data_level
            _find_and_check(t7.rows[0].cells[3], code)
        _safe_set_value(t7, 1, 1, d.data_category)
        _safe_set_value(t7, 2, 1, d.data_dept)
        _safe_set_value(t7, 2, 3, d.data_person)
        # 个人信息（勾选）
        if d.personal_info:
            code = d.personal_info.split('-')[0] if '-' in d.personal_info else d.personal_info
            _find_and_check(t7.rows[3].cells[1], code)
        # 数据总量 / 月增长量 — 只填数字到下划线处
        if d.total_size or d.total_size_tb or d.total_size_records:
            _fill_total_size_cell(
                t7.rows[4].cells[1],
                d.total_size_tb if d.total_size_unit == 'TB' else d.total_size,
                d.total_size_unit,
                d.total_size_records,
            )
        if d.monthly_growth or d.monthly_growth_tb:
            _fill_month_growth_cell(
                t7.rows[5].cells[1],
                d.monthly_growth_tb if d.monthly_growth_unit == 'TB' else d.monthly_growth,
                d.monthly_growth_unit,
            )
        if d.data_source:
            for source in d.data_source.split(','):
                code = source.strip().split('-')[0]
                if code:
                    _find_and_check(t7.rows[6].cells[1], code, multi=True)
            if '9-' in d.data_source and d.data_source_other:
                _fill_other_option(t7.rows[6].cells[1], '其他', d.data_source_other)
        _fill_numbered_lines(t7.rows[7].cells[1], [item.strip() for item in d.inflow_units.splitlines() if item.strip()])
        _fill_numbered_lines(t7.rows[8].cells[1], [item.strip() for item in d.outflow_units.splitlines() if item.strip()])
        if d.interaction:
            code = d.interaction.split('-')[0]
            _find_and_check(t7.rows[9].cells[1], code)
            if code != '4' and d.interaction_other:
                _fill_numbered_lines(t7.rows[9].cells[1], [d.interaction_other])
        if d.storage_type:
            code = d.storage_type.split('-')[0]
            _find_and_check(t7.rows[10].cells[1], code)
            _fill_option_line(t7.rows[10].cells[1], code, d.storage_cloud_name or d.storage_cloud)
        if d.storage_room:
            code = d.storage_room.split('-')[0]
            _find_and_check(t7.rows[11].cells[1], code)
            _fill_option_line(t7.rows[11].cells[1], code, d.storage_room_name)
        if d.storage_region:
            code = d.storage_region.split('-')[0]
            _find_and_check(t7.rows[12].cells[1], code)
            _fill_option_line(t7.rows[12].cells[1], code, d.storage_region_name)

    # ══════ 标黄处理 — 对用户标记的字段在文档中高亮 ══════
    if highlighted_fields:
        # UI field id → (table_index, row, col) 映射
        field_cell_map = {
            'unit_name': (1, 0, 1), 'credit_code': (1, 1, 1),
            'postal_code': (1, 3, 1), 'admin_code': (1, 3, 6),
            'leader_name': (1, 4, 2), 'leader_title': (1, 4, 6),
            'leader_phone': (1, 5, 2), 'leader_email': (1, 5, 6),
            'sec_dept': (1, 6, 1), 'sec_name': (1, 7, 2), 'sec_title': (1, 7, 6),
            'sec_phone': (1, 8, 2), 'sec_email': (1, 8, 6), 'sec_mobile': (1, 9, 2),
            'data_dept': (1, 10, 1), 'data_name': (1, 11, 2), 'data_title': (1, 11, 6),
            'data_phone': (1, 12, 2), 'data_email': (1, 12, 6), 'data_mobile': (1, 13, 2),
            'target_name': (2, 0, 2), 'biz_desc': (2, 3, 2),
            'run_date': (2, 9, 2), 'parent_sys': (2, 11, 2), 'parent_unit': (2, 12, 2),
            'grading_date': (3, 12, 2), 'report_name': (3, 13, 2), 'review_name': (3, 14, 2),
            'data_name_field': (6, 0, 1), 'data_category': (6, 1, 1),
            'data_sec_dept': (6, 2, 1), 'data_sec_person': (6, 2, 3),
            'total_size': (6, 4, 1), 'monthly_growth': (6, 5, 1),
        }
        for field_id in highlighted_fields:
            if field_id in field_cell_map:
                ti, ri, ci = field_cell_map[field_id]
                try:
                    cell = doc.tables[ti].rows[ri].cells[ci]
                    _highlight_cell(cell)
                except (IndexError, AttributeError):
                    pass

    doc.save(output_path)
    return output_path


def _fill_address(cell, province, city, county, detail):
    """精准填充地址单元格的空格占位 run"""
    # 模版结构:
    # p[0]: run[0]=spaces, run[1]="省", ... run[5]=spaces, run[6]="地", ...
    # p[1]: run[0]=spaces, run[1]="县", ... run[5]="详细地址", run[6]=spaces
    try:
        paras = cell.paragraphs
        if len(paras) >= 2:
            p0_runs = paras[0].runs
            p1_runs = paras[1].runs
            # 省名 → p[0] 第一个空格run（"省"前面）
            if province:
                _fill_space_run_before(p0_runs, '省', province)
            # 市名 → p[0] "地"前面的空格run
            if city:
                _fill_space_run_before(p0_runs, '地', city)
            # 县名 → p[1] "县"前面的空格run
            if county:
                _fill_space_run_before(p1_runs, '县', county)
            # 详细地址 → p[1] "详细地址"后面的空格run
            if detail:
                for i, run in enumerate(p1_runs):
                    if '详细地址' in run.text:
                        # 下一个run是空格占位
                        for j in range(i + 1, len(p1_runs)):
                            if p1_runs[j].text.strip() == '':
                                _set_run_text(p1_runs[j], detail)
                                return
                        break
    except (IndexError, AttributeError):
        pass


def _fill_space_run_before(runs, label, value):
    """在 runs 列表中找到 label 对应 run，将其前面的空格 run 替换为 value"""
    for i, run in enumerate(runs):
        if run.text.strip() == label or run.text.strip().startswith(label):
            # 往前找空格 run
            for j in range(i - 1, -1, -1):
                if runs[j].text.strip() == '':
                    _set_run_text(runs[j], value)
                    return
            break


def _fill_underline_field(cell, value):
    """填充下划线占位字段（如数据总量"___GB"），只替换下划线部分"""
    for para in cell.paragraphs:
        for run in para.runs:
            if '_' in run.text:
                if _fill_placeholder_run(run, value):
                    return
    # fallback: 如果没找到下划线，在第一个run前追加
    if cell.paragraphs and cell.paragraphs[0].runs:
        first = cell.paragraphs[0].runs[0]
        _set_run_text(first, value + first.text.lstrip())


def _fill_amount_unit_run(run, amount, unit):
    if run is None or not amount:
        return False
    if unit == "TB":
        return _fill_placeholder_run(run, str(amount), r"_+(?=TB)")
    return _fill_placeholder_run(run, str(amount), r"_+(?=GB)")


def _fill_total_size_cell(cell, amount, unit, records):
    amount = str(amount or "").strip()
    records = str(records or "").strip()
    unit = (unit or "GB").strip().upper()
    if not cell.paragraphs:
        return False
    if len(cell.paragraphs) >= 1:
        _check_first_sym_in_paragraph(cell.paragraphs[0], bool(amount))
        runs = cell.paragraphs[0].runs
        if len(runs) > 1:
            _fill_amount_unit_run(runs[1], amount, unit)
    if len(cell.paragraphs) >= 2:
        _check_first_sym_in_paragraph(cell.paragraphs[1], bool(records))
        runs = cell.paragraphs[1].runs
        if len(runs) > 1 and records:
            _fill_placeholder_run(runs[1], records)
    return True


def _fill_month_growth_cell(cell, amount, unit):
    amount = str(amount or "").strip()
    unit = (unit or "GB").strip().upper()
    if not amount or not cell.paragraphs or not cell.paragraphs[0].runs:
        return False
    return _fill_amount_unit_run(cell.paragraphs[0].runs[0], amount, unit)


def _fill_cloud_provider_line(cell, provider_name, level, platform_name, platform_code):
    values = [provider_name, level, platform_name, platform_code]
    value_idx = 0
    for para in cell.paragraphs:
        for run in para.runs:
            if "_" in run.text and value_idx < len(values):
                if _fill_placeholder_run(run, values[value_idx]):
                    value_idx += 1
        if value_idx >= len(values):
            return True
    return value_idx > 0


def _normalize_platform_code(platform_code):
    raw = str(platform_code or "").strip()
    if not raw:
        return ""
    parts = [part for part in raw.split("-") if part]
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return raw


def _check_paragraph_items(cell, items):
    targets = {str(item).strip() for item in (items or []) if str(item).strip()}
    if not targets:
        return False
    for para in cell.paragraphs:
        text = "".join(run.text for run in para.runs if run.text).strip()
        if any(target in text for target in targets):
            _check_first_sym_in_paragraph(para, True)
    return True


# ══════════════════════════════════════════════════════
#  定级报告生成
# ══════════════════════════════════════════════════════

def generate_report(template_path: str, output_path: str,
                    report: ReportInfo, project_name: str, highlighted_fields=None,
                    report_highlights=None):
    """基于新定级报告模版生成填充后的定级报告"""
    if highlighted_fields is None:
        highlighted_fields = []
    if report_highlights is None:
        report_highlights = {}
    system_name = (report.system_name or project_name or "").strip()
    shutil.copy2(template_path, output_path)
    doc = Document(output_path)

    # ── 第一遍：替换文本、删除说明 ──
    paragraphs_to_remove = []
    section_body_map = {
        "1、业务信息描述": (report.biz_info_desc, "rpt_biz_info", False),
        "2、业务信息受到破坏时所侵害客体的确定": (report.biz_victim, "rpt_biz_victim", False),
        "3、业务信息受到破坏时对侵害客体的侵害程度的确定": (report.biz_degree, "rpt_biz_degree", False),
        "1、系统服务描述": (report.svc_desc, "rpt_svc_desc", False),
        "2、系统服务受到破坏时所侵害客体的确定": (report.svc_victim, "rpt_svc_victim", False),
        "3、系统服务受到破坏时对侵害客体的侵害程度的确定": (report.svc_degree, "rpt_svc_degree", False),
    }
    pending_section = ""
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue

        if text in section_body_map:
            pending_section = text
            continue

        if pending_section and text.startswith("【"):
            replacement, field_id, split_lines = section_body_map.get(pending_section, ("", "", False))
            if replacement:
                _replace_body_paragraphs(
                    p,
                    replacement,
                    split_lines=split_lines,
                    highlight_snippets=report_highlights.get(field_id, []),
                )
            else:
                paragraphs_to_remove.append(p)
            pending_section = ""
            continue

        # 替换标题（XX → 项目名），保持格式一致
        if "XX" in text and "定级报告" in text:
            _replace_paragraph_text(p, text.replace("XX", system_name))
            _apply_report_title_format(p)
            continue

        # 清除所有填写说明（【...】标记的内容）
        if text.startswith("【") or "【填写说明" in text or "【描述参考示例】" in text or "【网络边界描述示例】" in text:
            paragraphs_to_remove.append(p)
            continue
        # 清除以"说明："开头的提示段落
        if text.startswith("说明："):
            paragraphs_to_remove.append(p)
            continue
        # 清除模板中残留的"该定级对象是否采用了新技术"等说明
        if "该定级对象是否采用了新技术" in text:
            paragraphs_to_remove.append(p)
            continue

        # 替换参考示例内容
        if "定级对象于XX年" in text and report.responsibility:
            _replace_body_paragraphs(
                p,
                report.responsibility,
                split_lines=False,
                highlight_snippets=report_highlights.get("rpt_responsibility", []),
            )
            continue
        elif "网络中部署了XXX防火墙" in text and report.composition:
            _replace_body_paragraphs(
                p,
                report.composition,
                split_lines=True,
                highlight_snippets=report_highlights.get("rpt_composition", []),
            )
            continue
        elif "该定级对象承载着综合办公业务" in text and report.business_desc:
            _replace_body_paragraphs(
                p,
                report.business_desc,
                split_lines=False,
                highlight_snippets=report_highlights.get("rpt_business", []),
            )
            continue
        elif "按照网络安全法" in text and report.security_resp:
            _replace_body_paragraphs(
                p,
                report.security_resp,
                split_lines=False,
                highlight_snippets=report_highlights.get("rpt_security", []),
            )
            continue

        # 替换子系统表描述
        if "该定级对象包括以下子系统" in text:
            if not report.subsystems:
                paragraphs_to_remove.append(p)
            else:
                _replace_body_paragraphs(p, "该定级对象包括以下子系统：")

        # 替换等级占位
        if "第X级" in text:
            new_text = text
            if "最终确定" in text:
                new_text = text.replace("第X级", report.final_level)
                new_text = new_text.replace("XXX", system_name)
            elif "业务信息安全保护等级" in text and "系统服务" not in text:
                new_text = text.replace("第X级", report.biz_level)
            elif "系统服务安全保护等级" in text:
                new_text = text.replace("第X级", report.svc_level)
            else:
                new_text = text.replace("第X级", report.final_level)
            if new_text != text:
                _replace_body_paragraphs(p, new_text)
                continue

        # 替换 XXX
        if "XXX" in text and "第X级" not in text:
            _replace_body_paragraphs(p, text.replace("XXX", system_name))

    # 删除标记的段落
    for p in paragraphs_to_remove:
        parent = p._element.getparent()
        if parent is not None:
            parent.remove(p._element)

    # ── 清除多余空行（连续2个以上空段落压缩为1个） ──
    _remove_consecutive_blanks(doc)

    # ── 插入网络拓扑图（放在"定级对象构成"描述文字之后） ──
    if report.topology_image and os.path.exists(report.topology_image):
        _insert_topology_image(doc, report.topology_image)

    # ── 子系统表格处理 ──
    for table in doc.tables:
        if _cell_text_safe(table, 0, 0) == "序号":
            if report.subsystems:
                while len(table.rows) > 1:
                    table._tbl.remove(table.rows[-1]._tr)
                for sub in report.subsystems:
                    row = table.add_row()
                    set_cell_text(row.cells[0], sub.index)
                    set_cell_text(row.cells[1], sub.name)
                    set_cell_text(row.cells[2], sub.description)
            else:
                # 无子系统时删除表格
                table._tbl.getparent().remove(table._tbl)
            break

    # ── 矩阵表涂色（业务信息 & 系统服务安全保护等级矩阵表） ──
    _shade_matrix_tables(doc, report)

    # ── 最终等级汇总表 ──
    for table in doc.tables:
        if _cell_text_safe(table, 0, 0) == "定级对象名称":
            if len(table.rows) > 1:
                _safe_set_value(table, 1, 0, system_name)
                _safe_set_value(table, 1, 1, report.final_level)
                _safe_set_value(table, 1, 2, report.biz_level)
                _safe_set_value(table, 1, 3, report.svc_level)
            break

    doc.save(output_path)
    return output_path


def _remove_consecutive_blanks(doc):
    """压缩连续空段落，最多保留1个"""
    prev_blank = False
    to_remove = []
    for p in doc.paragraphs:
        is_blank = not p.text.strip()
        if is_blank and prev_blank:
            to_remove.append(p)
        prev_blank = is_blank
    for p in to_remove:
        parent = p._element.getparent()
        if parent is not None:
            parent.remove(p._element)


def _shade_matrix_tables(doc, report):
    """
    对业务信息和系统服务安全保护等级矩阵表进行涂色。
    根据等级在对应行列交叉处涂黑（深色背景+白色文字）。
    """
    matrix_sources = [
        ("业务信息安全被破坏时所侵害的客体", report.biz_victim, report.biz_degree),
        ("系统服务安全被破坏时所侵害的客体", report.svc_victim, report.svc_degree),
    ]
    for header_text, victim_text, degree_text in matrix_sources:
        table = next((item for item in doc.tables if header_text in _cell_text_safe(item, 0, 0)), None)
        if table is None:
            continue
        row_idx = _match_matrix_row(victim_text)
        col_idx = _match_matrix_col(degree_text)
        if row_idx is None or col_idx is None:
            continue
        _shade_cell_gray(table.rows[row_idx].cells[col_idx])


def _match_matrix_row(text):
    raw = str(text or "")
    if "公民" in raw or "法人" in raw or "其他组织" in raw:
        return 2
    if "社会秩序" in raw or "公共利益" in raw:
        return 3
    if "国家安全" in raw or "地区安全" in raw or "国计民生" in raw:
        return 4
    return None


def _match_matrix_col(text):
    raw = str(text or "")
    if "特别严重" in raw:
        return 3
    if "严重" in raw:
        return 2
    if "一般" in raw:
        return 1
    return None


def _shade_cell_gray(cell):
    """给单元格设置灰色背景、白色文字。"""
    # 设置单元格底纹
    tc_pr = cell._element.get_or_add_tcPr()
    for node in list(tc_pr):
        if node.tag == qn('w:shd'):
            tc_pr.remove(node)
    shading = OxmlElement('w:shd')
    shading.set(qn('w:val'), 'clear')
    shading.set(qn('w:color'), 'auto')
    shading.set(qn('w:fill'), '808080')
    tc_pr.append(shading)
    # 设置文字为白色
    for para in cell.paragraphs:
        for run in para.runs:
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _replace_paragraph_text(paragraph, new_text):
    """替换段落文本，保留第一个 run 的格式"""
    placeholder_pattern = re.compile(r"(身份证号码[:：][X_]{3,}|X{4,}|_{3,})")
    style_run = paragraph.runs[0] if paragraph.runs else None
    if not paragraph.runs:
        paragraph.add_run("")
        style_run = paragraph.runs[0]

    for run in paragraph.runs:
        run.text = ""

    parts = [part for part in placeholder_pattern.split(new_text) if part]
    if not parts:
        parts = [new_text]

    for idx, part in enumerate(parts):
        run = paragraph.runs[0] if idx == 0 else paragraph.add_run()
        run.text = part
        if style_run is not None:
            _copy_run_style(style_run, run)
        if placeholder_pattern.fullmatch(part):
            _highlight_run(run, "yellow")


def _highlight_text_in_paragraph(paragraph, target):
    """在单段中高亮首个命中的文本片段。"""
    raw_target = str(target or "")
    if not raw_target:
        return False
    target = raw_target.strip()
    if not target:
        return False

    for run in list(paragraph.runs):
        run_text = run.text or ""
        if not run_text or target not in run_text:
            continue
        if run_text == target:
            _highlight_run(run, "yellow")
            return True

        before, _, after = run_text.partition(target)
        style_run = run
        if before:
            run.text = before
            _clear_run_highlight(run)
            match_run = _insert_run_after(run)
            _copy_run_style(style_run, match_run)
        else:
            match_run = run

        match_run.text = target
        _highlight_run(match_run, "yellow")

        if after:
            after_run = _insert_run_after(match_run)
            _copy_run_style(style_run, after_run)
            _clear_run_highlight(after_run)
            after_run.text = after
        return True
    return False


def _highlight_snippets_in_paragraphs(paragraphs, snippets):
    """将选中的正文片段高亮到对应段落。"""
    for snippet in snippets or []:
        raw = str(snippet or "").strip()
        if not raw:
            continue
        for paragraph in paragraphs:
            if raw in paragraph.text and _highlight_text_in_paragraph(paragraph, raw):
                break


def _normalize_single_paragraph_text(text):
    raw = str(text or "").strip()
    if not raw:
        return ""
    collapsed = re.sub(r"\s*\r?\n\s*", "", raw)
    return re.sub(r"[ \t]+", " ", collapsed).strip()


def _normalize_highlight_snippets(snippets, split_lines=False):
    normalized = []
    for snippet in snippets or []:
        raw = str(snippet or "").strip()
        if not raw:
            continue
        if split_lines:
            normalized.extend(part.strip() for part in re.split(r"\r?\n+", raw) if part.strip())
        else:
            single = _normalize_single_paragraph_text(raw)
            if single:
                normalized.append(single)
    return normalized


def _replace_body_paragraphs(paragraph, text, split_lines=False, highlight_snippets=None):
    """按报告正文格式写入段落，并支持局部标黄。"""
    if split_lines:
        lines = [line.strip() for line in re.split(r"\r?\n+", str(text or "")) if line.strip()]
    else:
        single = _normalize_single_paragraph_text(text)
        lines = [single] if single else []
    if not lines:
        _replace_paragraph_text(paragraph, "")
        _apply_report_body_format(paragraph)
        return

    _replace_paragraph_text(paragraph, lines[0])
    _apply_report_body_format(paragraph)

    paragraphs = [paragraph]
    anchor = paragraph
    for line in lines[1:]:
        new_paragraph = _insert_paragraph_after(anchor)
        if paragraph.style is not None:
            new_paragraph.style = paragraph.style
        _replace_paragraph_text(new_paragraph, line)
        _apply_report_body_format(new_paragraph)
        anchor = new_paragraph
        paragraphs.append(new_paragraph)

    _highlight_snippets_in_paragraphs(
        paragraphs,
        _normalize_highlight_snippets(highlight_snippets, split_lines=split_lines),
    )


def _cell_text_safe(table, row, col):
    try:
        return table.rows[row].cells[col].text.strip()
    except (IndexError, AttributeError):
        return ""


def _insert_topology_image(doc, image_path):
    """在定级对象构成章节的描述文字之后插入拓扑图"""
    found_section = False
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if ("定级对象构成" in text and "（二）" in text) or "网络拓扑图" in text:
            found_section = True
            continue
        if found_section:
            # 跳过描述性文字段落，找到第一个空段落或下一个标题之前的位置
            if not text or text.startswith("（三）") or text.startswith("（四）"):
                # 在当前位置之前（描述段落之后）插入图片
                # 使用上一个非空段落之后的位置
                target_p = doc.paragraphs[i]
                if not text:
                    # 空段落，直接在此处插入图片
                    run = target_p.add_run()
                    run.add_picture(image_path, width=Inches(5.5))
                else:
                    # 到了下一个标题，在前面插入新段落
                    para = p.insert_paragraph_before()
                    run = para.add_run()
                    run.add_picture(image_path, width=Inches(5.5))
                return
