"""新文档生成 — 精准 run 级填充，保留模版格式"""

import os
import shutil
from docx import Document
from docx.shared import Inches
from docx.oxml.ns import qn
from models.project_data import ProjectData, ReportInfo
from core.format_style import (
    set_cell_text, FONT_FANG_GB, SIZE_TABLE, _set_east_asia_font
)


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

def generate_beian(template_path: str, output_path: str, data: ProjectData):
    """基于新备案表模版生成填充后的备案表（精准填充）"""
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
                for run in p.runs:
                    if run.text.strip() == '' and len(run.text) >= 3:
                        # 找到（盖章）前面的空格 run
                        run.text = unit_name
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

    # 安全保护等级（勾选）
    level_cell = t4.rows[11].cells[2]
    if g.final_level:
        _find_and_check(level_cell, g.final_level)

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
                    report: ReportInfo, project_name: str):
    """基于新定级报告模版生成填充后的定级报告"""
    shutil.copy2(template_path, output_path)
    doc = Document(output_path)

    for p in doc.paragraphs:
        text = p.text.strip()

        # 替换标题（XX可能在单独run）
        if "XX" in text and "定级报告" in text:
            for run in p.runs:
                if "XX" in run.text:
                    run.text = run.text.replace("XX", project_name)

        # 清除填写说明
        if "【填写说明" in text or "【描述参考示例】" in text or "【网络边界描述示例】" in text:
            _replace_paragraph_text(p, "")
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

        # 替换子系统表描述
        if "该定级对象包括以下子系统" in text:
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

    # 插入网络拓扑图
    if report.topology_image and os.path.exists(report.topology_image):
        _insert_topology_image(doc, report.topology_image)

    # 填充子系统表格
    if report.subsystems:
        for table in doc.tables:
            if _cell_text_safe(table, 0, 0) == "序号":
                while len(table.rows) > 1:
                    table._tbl.remove(table.rows[-1]._tr)
                for sub in report.subsystems:
                    row = table.add_row()
                    set_cell_text(row.cells[0], sub.index)
                    set_cell_text(row.cells[1], sub.name)
                    set_cell_text(row.cells[2], sub.description)
                break

    # 填充最终等级汇总表
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
    """在定级对象构成章节后插入拓扑图"""
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if "网络拓扑图" in text or ("定级对象构成" in text and "（二）" in text):
            for j in range(i + 1, min(i + 5, len(doc.paragraphs))):
                next_p = doc.paragraphs[j]
                if not next_p.text.strip() or "【" in next_p.text:
                    run = next_p.add_run()
                    run.add_picture(image_path, width=Inches(5.5))
                    return
            break
