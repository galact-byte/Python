"""新文档生成 — 精准 run 级填充，保留模版格式"""

import os
import shutil
from docx import Document
from docx.shared import Inches, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from models.project_data import ProjectData, ReportInfo
from core.format_style import (
    set_cell_text, FONT_FANG_GB, SIZE_TABLE, _set_east_asia_font
)


# ══════════════════════════════════════════════════════
#  底层工具函数
# ══════════════════════════════════════════════════════

def _highlight_run(run, color="yellow"):
    """给 run 添加高亮色"""
    rpr = run._element.get_or_add_rPr()
    highlight = OxmlElement('w:highlight')
    highlight.set(qn('w:val'), color)
    rpr.append(highlight)


def _highlight_cell(cell, color="yellow"):
    """给单元格中所有 run 添加高亮"""
    for para in cell.paragraphs:
        for run in para.runs:
            _highlight_run(run, color)


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
                run.text = '  ' + text
                return True
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
                p.runs[0].text = str(text)
                for run in p.runs[1:]:
                    run.text = ''
                return
        # 没有 run 则新建
        if cell.paragraphs:
            run = cell.paragraphs[0].add_run(str(text))
            run.font.name = FONT_FANG_GB
            run.font.size = SIZE_TABLE
            _set_east_asia_font(run, FONT_FANG_GB)
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
    type_cell = t3.rows[1].cells[1]
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

    # 业务描述（纯值）
    _safe_set_value(t3, 3, 2, tgt.biz_desc)

    # 服务范围（勾选）
    if tgt.service_scope:
        code = tgt.service_scope.split('-')[0] if '-' in tgt.service_scope else tgt.service_scope
        _find_and_check(t3.rows[4].cells[2], code)

    # 服务对象（勾选）
    if tgt.service_target:
        code = tgt.service_target.split('-')[0] if '-' in tgt.service_target else tgt.service_target
        _find_and_check(t3.rows[5].cells[2], code)

    # 部署范围（勾选）
    if tgt.deploy_scope:
        code = tgt.deploy_scope.split('-')[0] if '-' in tgt.deploy_scope else tgt.deploy_scope
        _find_and_check(t3.rows[6].cells[2], code)

    # 网络性质（勾选）
    if tgt.network_type:
        code = tgt.network_type.split('-')[0] if '-' in tgt.network_type else tgt.network_type
        _find_and_check(t3.rows[7].cells[2], code)

    # 网络互联（勾选）
    if tgt.interconnect:
        _find_and_check(t3.rows[8].cells[1], tgt.interconnect)

    # 运行时间（纯值）
    _safe_set_value(t3, 9, 2, tgt.run_date)

    # 是否分系统（勾选）
    if tgt.is_subsystem:
        _find_and_check(t3.rows[10].cells[1], tgt.is_subsystem)

    # 上级系统
    _safe_set_value(t3, 11, 2, tgt.parent_system or '/')
    _safe_set_value(t3, 12, 2, tgt.parent_unit or '/')

    # ══════ 表4: 定级等级 (index 3, 5列) ══════
    t4 = doc.tables[3]

    # 安全保护等级（勾选）— 需要分别勾选业务信息等级、系统服务等级、最终等级
    # 表4 row11 包含三个等级的勾选区域
    level_cell = t4.rows[11].cells[2]
    if g.biz_level:
        _find_and_check(level_cell, g.biz_level, multi=True)
    if g.service_level:
        _find_and_check(level_cell, g.service_level, multi=True)
    if g.final_level:
        _find_and_check(level_cell, g.final_level, multi=True)

    # 定级时间
    _safe_set_value(t4, 12, 2, g.grading_date)

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
        # 上级主管部门审核情况：有主管部门但未审核时勾选"未审核"
        if len(t4.rows) > 17:
            audit_cell = t4.rows[17].cells[2]
            if g.supervisor_reviewed:
                _find_and_check(audit_cell, '已审核')
            else:
                _find_and_check(audit_cell, '未审核')
    else:
        _find_and_check(supervisor_cell, '无')

    _safe_set_value(t4, 16, 2, g.supervisor_name or '/')

    # 填表人 / 填表日期
    _safe_set_value(t4, 18, 0, f"填表人：{g.filler}")
    _safe_set_value(t4, 18, 3, f"填表日期：{g.fill_date}")

    # ══════ 表5: 应用场景 (index 4) — 保持模版默认，仅填已有数据 ══════
    if len(doc.tables) > 4:
        t5 = doc.tables[4]
        sc = data.scenario
        if sc.cloud.enabled and sc.cloud.provider_name:
            _safe_set_value(t5, 9, 2, sc.cloud.provider_name)
        if sc.cloud.client_ops_location:
            _safe_set_value(t5, 10, 2, sc.cloud.client_ops_location)

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
        _safe_set_value(t7, 1, 1, d.data_category)
        _safe_set_value(t7, 2, 1, d.data_dept)
        _safe_set_value(t7, 2, 3, d.data_person)
        # 个人信息（勾选）
        if d.personal_info:
            code = d.personal_info.split('-')[0] if '-' in d.personal_info else d.personal_info
            _find_and_check(t7.rows[3].cells[1], code)
        # 数据总量 / 月增长量 — 只填数字到下划线处
        if d.total_size:
            _fill_underline_field(t7.rows[4].cells[1], d.total_size)
        if d.monthly_growth:
            _fill_underline_field(t7.rows[5].cells[1], d.monthly_growth)

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
                                p1_runs[j].text = detail
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
                    runs[j].text = value
                    return
            break


def _fill_underline_field(cell, value):
    """填充下划线占位字段（如数据总量"___GB"），只替换下划线部分"""
    for para in cell.paragraphs:
        for run in para.runs:
            if '_' in run.text:
                # 替换下划线为值
                import re
                run.text = re.sub(r'_+', value, run.text, count=1)
                return
    # fallback: 如果没找到下划线，在第一个run前追加
    if cell.paragraphs and cell.paragraphs[0].runs:
        first = cell.paragraphs[0].runs[0]
        first.text = value + first.text.lstrip()


# ══════════════════════════════════════════════════════
#  定级报告生成
# ══════════════════════════════════════════════════════

def generate_report(template_path: str, output_path: str,
                    report: ReportInfo, project_name: str, highlighted_fields=None):
    """基于新定级报告模版生成填充后的定级报告"""
    if highlighted_fields is None:
        highlighted_fields = []
    shutil.copy2(template_path, output_path)
    doc = Document(output_path)

    # ── 第一遍：替换文本、删除说明 ──
    paragraphs_to_remove = []
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue

        # 替换标题（XX → 项目名），保持格式一致
        if "XX" in text and "定级报告" in text:
            for run in p.runs:
                if "XX" in run.text:
                    run.text = run.text.replace("XX", project_name)

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
            _replace_paragraph_text(p, report.responsibility)
        elif "网络中部署了XXX防火墙" in text and report.composition:
            _replace_paragraph_text(p, report.composition)
        elif "该定级对象承载着综合办公业务" in text and report.business_desc:
            _replace_paragraph_text(p, report.business_desc)
        elif "按照网络安全法" in text and report.security_resp:
            _replace_paragraph_text(p, report.security_resp)

        # 填充业务信息描述/侵害客体/侵害程度
        if "业务信息描述的内容" in text and report.biz_info_desc:
            _replace_paragraph_text(p, report.biz_info_desc)
        elif "对客体的侵害" in text and "业务信息" in text and report.biz_victim:
            _replace_paragraph_text(p, report.biz_victim)
        elif "侵害程度的描述" in text and "业务信息" in text and report.biz_degree:
            _replace_paragraph_text(p, report.biz_degree)

        # 填充系统服务描述/侵害客体/侵害程度
        if "系统服务描述的内容" in text and report.svc_desc:
            _replace_paragraph_text(p, report.svc_desc)
        elif "对客体的侵害" in text and "系统服务" in text and report.svc_victim:
            _replace_paragraph_text(p, report.svc_victim)
        elif "侵害程度的描述" in text and "系统服务" in text and report.svc_degree:
            _replace_paragraph_text(p, report.svc_degree)

        # 替换子系统表描述
        if "该定级对象包括以下子系统" in text:
            if not report.subsystems:
                paragraphs_to_remove.append(p)
            else:
                _replace_paragraph_text(p, "该定级对象包括以下子系统：")

        # 替换等级占位
        if "第X级" in text:
            new_text = text
            if "最终确定" in text:
                new_text = text.replace("第X级", report.final_level)
                new_text = new_text.replace("XXX", project_name)
            elif "业务信息安全保护等级" in text and "系统服务" not in text:
                new_text = text.replace("第X级", report.biz_level)
            elif "系统服务安全保护等级" in text:
                new_text = text.replace("第X级", report.svc_level)
            else:
                new_text = text.replace("第X级", report.final_level)
            if new_text != text:
                _replace_paragraph_text(p, new_text)

        # 替换 XXX
        if "XXX" in text and "第X级" not in text:
            _replace_paragraph_text(p, text.replace("XXX", project_name))

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
                _safe_set_value(table, 1, 0, project_name)
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
    level_map = {"第一级": 1, "第二级": 2, "第三级": 3, "第四级": 4, "第五级": 5}

    for table in doc.tables:
        header = _cell_text_safe(table, 0, 0)
        # 业务信息安全保护等级矩阵表
        if "受到破坏时所侵害的客体" in header or "客体" in header:
            level_val = 0
            # 判断是业务信息还是系统服务矩阵表
            # 通过查找前面段落的上下文来判断
            table_xml = table._tbl
            prev = table_xml.getprevious()
            is_biz = True
            while prev is not None:
                prev_text = prev.text if hasattr(prev, 'text') else ''
                if '系统服务' in prev_text:
                    is_biz = False
                    break
                if '业务信息' in prev_text:
                    is_biz = True
                    break
                prev = prev.getprevious()

            if is_biz:
                level_val = level_map.get(report.biz_level, 2)
            else:
                level_val = level_map.get(report.svc_level, 2)

            _shade_level_in_matrix(table, level_val)


def _shade_level_in_matrix(table, level):
    """
    在矩阵表中对应等级的单元格涂黑。
    矩阵表结构：第0行是表头，第1-3行是"公民/法人/其他"或类似客体行，
    列代表侵害程度（一般/严重/特别严重），交叉处是等级。
    找到文本为"第X级"（对应level）的单元格涂黑。
    """
    level_text = {1: "第一级", 2: "第二级", 3: "第三级", 4: "第四级", 5: "第五级"}
    target = level_text.get(level, "")
    if not target:
        return

    for row in table.rows:
        for cell in row.cells:
            text = cell.text.strip()
            if text == target:
                _shade_cell_black(cell)


def _shade_cell_black(cell):
    """给单元格设置黑色背景、白色文字"""
    # 设置单元格底纹
    tc_pr = cell._element.get_or_add_tcPr()
    shading = OxmlElement('w:shd')
    shading.set(qn('w:val'), 'clear')
    shading.set(qn('w:color'), 'auto')
    shading.set(qn('w:fill'), '000000')
    tc_pr.append(shading)
    # 设置文字为白色
    for para in cell.paragraphs:
        for run in para.runs:
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _replace_paragraph_text(paragraph, new_text):
    """替换段落文本，保留第一个 run 的格式"""
    if not paragraph.runs:
        paragraph.add_run(new_text)
        return
    paragraph.runs[0].text = new_text
    for run in paragraph.runs[1:]:
        run.text = ""


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
                    new_p = OxmlElement('w:p')
                    p._element.addprevious(new_p)
                    from docx.text.paragraph import Paragraph
                    para = Paragraph(new_p, p._element.getparent())
                    run = para.add_run()
                    run.add_picture(image_path, width=Inches(5.5))
                return
