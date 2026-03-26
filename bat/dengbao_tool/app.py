"""等保文档迁移工具 — Flask Web 后端"""

import os
import sys
import json
import glob
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, jsonify
from models.project_data import ProjectData, ReportInfo

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用静态文件缓存

# Word 模版目录
DOC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "doc_templates")


@app.route("/")
def index():
    """主页"""
    beian_tpl = _find_file(DOC_TEMPLATE_DIR, "*备案表*.docx")
    report_tpl = _find_file(DOC_TEMPLATE_DIR, "*定级报告*.docx")
    return render_template("index.html",
                           beian_template=beian_tpl or "",
                           report_template=report_tpl or "")


@app.route("/api/scan_dir", methods=["POST"])
def scan_dir():
    """扫描项目目录，查找旧文件"""
    dir_path = request.json.get("dir_path", "")
    if not dir_path or not os.path.isdir(dir_path):
        return jsonify({"error": "目录不存在"}), 400

    beian = _find_file(dir_path, "*备案表*.docx") or _find_file(dir_path, "*备案表*.doc")
    report = _find_file(dir_path, "*定级报告*.docx") or _find_file(dir_path, "*定级报告*.doc")
    survey = (_find_file(dir_path, "*调查表*.docx") or
              _find_file(dir_path, "*基本情况*.docx") or
              _find_file(os.path.dirname(dir_path), "*调查表*" + os.path.basename(dir_path).split('_')[-1] + "*.docx") if dir_path else None)
    # 更宽泛的父目录搜索
    if not survey:
        parent = os.path.dirname(dir_path)
        if parent:
            survey = _find_file(parent, "*调查表*.docx") or _find_file(parent, "*基本情况*.docx")

    # 猜测项目名
    project_name = ""
    if beian:
        fname = os.path.splitext(os.path.basename(beian))[0]
        for prefix in ["备案表_", "01-新备案表"]:
            if prefix in fname:
                name = fname.split(prefix)[-1].strip()
                if name and "领取" not in name:
                    project_name = name
                    break
    if not project_name:
        project_name = os.path.basename(dir_path)

    return jsonify({
        "old_beian": beian or "",
        "old_report": report or "",
        "survey": survey or "",
        "project_name": project_name,
        "output_dir": dir_path,
    })


@app.route("/api/load_data", methods=["POST"])
def load_data():
    """从旧文件加载数据"""
    old_beian = request.json.get("old_beian", "")
    old_report = request.json.get("old_report", "")

    result = {"beian_data": None, "report_data": None, "changes": [], "errors": []}

    if old_beian and os.path.exists(old_beian):
        try:
            # .doc → .docx 转换
            if old_beian.lower().endswith('.doc'):
                from core.doc_converter import convert_doc_to_docx
                converted = convert_doc_to_docx(old_beian)
                if converted:
                    old_beian = converted
                else:
                    result["errors"].append(
                        f"备案表 .doc 转换失败，请手动用 Word 另存为 .docx\n文件: {old_beian}")
                    old_beian = ""

            if old_beian:
                from core.doc_reader import read_beian_docx
                data = read_beian_docx(old_beian)
                result["beian_data"] = _dataclass_to_dict(data)
                result["changes"].append(f"从备案表加载了单位信息、定级对象等数据")
        except Exception as e:
            result["errors"].append(f"读取备案表失败: {e}")

    if old_report and os.path.exists(old_report):
        try:
            if old_report.lower().endswith('.doc'):
                from core.doc_converter import convert_doc_to_docx
                converted = convert_doc_to_docx(old_report)
                if converted:
                    old_report = converted
                else:
                    result["errors"].append("定级报告 .doc 转换失败")
                    old_report = ""

            if old_report:
                from core.doc_reader import read_report_docx
                report = read_report_docx(old_report)
                result["report_data"] = _dataclass_to_dict(report)
                result["changes"].append(f"从定级报告加载了责任主体、等级等数据")
        except Exception as e:
            result["errors"].append(f"读取定级报告失败: {e}")

    return jsonify(result)


@app.route("/api/generate", methods=["POST"])
def generate():
    """生成文档"""
    payload = request.json
    paths = payload["paths"]
    form_data = payload["form_data"]
    report_data = payload["report_data"]

    try:
        data = _dict_to_project_data(form_data)
        report = _dict_to_report(report_data)
        name = paths["project_name"]
        highlighted = form_data.get("highlighted_fields", [])

        from core.doc_writer import generate_beian, generate_report

        out_dir = paths["output_dir"]
        os.makedirs(out_dir, exist_ok=True)

        beian_out = os.path.join(out_dir, f"备案表_{name}.docx")
        generate_beian(paths["beian_template"], beian_out, data, highlighted_fields=highlighted)

        report_out = os.path.join(out_dir, f"定级报告_{name}.docx")
        generate_report(paths["report_template"], report_out, report, name, highlighted_fields=highlighted)

        return jsonify({
            "success": True,
            "files": [beian_out, report_out],
            "message": f"生成完成！\n备案表: {beian_out}\n定级报告: {report_out}"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"生成失败: {e}"}), 500


@app.route("/api/preview", methods=["POST"])
def preview():
    """生成预览文件并打开"""
    payload = request.json
    doc_type = payload.get("doc_type", "beian")
    paths = payload["paths"]
    form_data = payload["form_data"]
    report_data = payload["report_data"]

    try:
        data = _dict_to_project_data(form_data)
        report = _dict_to_report(report_data)
        name = paths["project_name"]
        highlighted = form_data.get("highlighted_fields", [])

        from core.doc_writer import generate_beian, generate_report

        temp_dir = os.path.join(tempfile.gettempdir(), "dengbao_preview")
        os.makedirs(temp_dir, exist_ok=True)

        if doc_type == "beian":
            out = os.path.join(temp_dir, f"预览_备案表_{name}.docx")
            generate_beian(paths["beian_template"], out, data, highlighted_fields=highlighted)
        else:
            out = os.path.join(temp_dir, f"预览_定级报告_{name}.docx")
            generate_report(paths["report_template"], out, report, name, highlighted_fields=highlighted)

        os.startfile(out)
        return jsonify({"success": True, "path": out})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/open_dir", methods=["POST"])
def open_dir():
    """打开目录"""
    dir_path = request.json.get("dir_path", "")
    if dir_path and os.path.isdir(dir_path):
        os.startfile(dir_path)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400


@app.route("/api/browse_dir", methods=["POST"])
def browse_dir():
    """弹出系统文件夹选择对话框"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        dir_path = filedialog.askdirectory(title="选择项目目录")
        root.destroy()
        return jsonify({"path": dir_path or ""})
    except Exception as e:
        return jsonify({"path": "", "error": str(e)})


@app.route("/api/browse_file", methods=["POST"])
def browse_file():
    """弹出系统文件选择对话框"""
    file_types = request.json.get("types", "")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        filetypes = [("Word文档", "*.docx *.doc"), ("所有文件", "*.*")]
        if file_types == "image":
            filetypes = [("图片", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")]
        path = filedialog.askopenfilename(title="选择文件", filetypes=filetypes)
        root.destroy()
        return jsonify({"path": path or ""})
    except Exception as e:
        return jsonify({"path": "", "error": str(e)})


@app.route("/api/load_survey", methods=["POST"])
def load_survey():
    """从调查表提取拓扑图和描述"""
    survey_path = request.json.get("survey_path", "")
    if not survey_path or not os.path.exists(survey_path):
        return jsonify({"error": "文件不存在"}), 400
    try:
        from core.doc_reader import read_survey_docx
        img_path, desc = read_survey_docx(survey_path)
        return jsonify({
            "topology_image": img_path or "",
            "topology_desc": desc or "",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 工具函数 ──

def _find_file(directory, pattern):
    """在目录中查找匹配文件"""
    matches = glob.glob(os.path.join(directory, pattern))
    return min(matches, key=len) if matches else None


def _dataclass_to_dict(obj):
    """递归将 dataclass 转为 dict"""
    import dataclasses
    if dataclasses.is_dataclass(obj):
        result = {}
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            result[f.name] = _dataclass_to_dict(val)
        return result
    elif isinstance(obj, list):
        return [_dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, bool):
        return obj
    else:
        return obj


def _dict_to_project_data(d):
    """从 dict 重建 ProjectData"""
    from models.project_data import (
        ProjectData, UnitInfo, ContactInfo, TargetInfo, GradingInfo,
        ScenarioInfo, CloudInfo, MobileInfo, IoTInfo, ICSInfo, BigDataInfo,
        AttachmentInfo, AttachmentItem, DataInfo
    )
    data = ProjectData()
    data.project_name = d.get("project_name", "")

    u = d.get("unit", {})
    data.unit = UnitInfo(
        unit_name=u.get("unit_name", ""), credit_code=u.get("credit_code", ""),
        province=u.get("province", ""), city=u.get("city", ""),
        county=u.get("county", ""), address=u.get("address", ""),
        postal_code=u.get("postal_code", ""), admin_code=u.get("admin_code", ""),
        leader=_dict_to_contact(u.get("leader", {})),
        security_dept=u.get("security_dept", ""),
        security_contact=_dict_to_contact(u.get("security_contact", {})),
        data_dept=u.get("data_dept", ""),
        data_contact=_dict_to_contact(u.get("data_contact", {})),
        affiliation=u.get("affiliation", ""), unit_type=u.get("unit_type", ""),
        industry=u.get("industry", ""),
        current_total=u.get("current_total", ""), current_level2=u.get("current_level2", ""),
        current_level3=u.get("current_level3", ""), current_level4=u.get("current_level4", ""),
        current_level5=u.get("current_level5", ""),
        all_total=u.get("all_total", ""), all_level1=u.get("all_level1", ""),
        all_level2=u.get("all_level2", ""), all_level3=u.get("all_level3", ""),
        all_level4=u.get("all_level4", ""), all_level5=u.get("all_level5", ""),
    )

    t = d.get("target", {})
    data.target = TargetInfo(
        name=t.get("name", ""), code=t.get("code", ""),
        target_type=t.get("target_type", ""), tech_type=t.get("tech_type", ""),
        biz_type=t.get("biz_type", ""), biz_desc=t.get("biz_desc", ""),
        service_scope=t.get("service_scope", ""), service_target=t.get("service_target", ""),
        deploy_scope=t.get("deploy_scope", ""), network_type=t.get("network_type", ""),
        source_ip=t.get("source_ip", ""), domain=t.get("domain", ""),
        protocol_port=t.get("protocol_port", ""), interconnect=t.get("interconnect", ""),
        run_date=t.get("run_date", ""), is_subsystem=t.get("is_subsystem", ""),
        parent_system=t.get("parent_system", ""), parent_unit=t.get("parent_unit", ""),
    )

    g = d.get("grading", {})
    data.grading = GradingInfo(
        biz_level=g.get("biz_level", "第二级"), service_level=g.get("service_level", "第二级"),
        final_level=g.get("final_level", "第二级"), grading_date=g.get("grading_date", ""),
        has_report=g.get("has_report", True), report_name=g.get("report_name", ""),
        has_review=g.get("has_review", True), review_name=g.get("review_name", ""),
        has_supervisor=g.get("has_supervisor", False),
        supervisor_name=g.get("supervisor_name", ""),
        supervisor_reviewed=g.get("supervisor_reviewed", False),
        supervisor_doc=g.get("supervisor_doc", ""),
        filler=g.get("filler", ""), fill_date=g.get("fill_date", ""),
    )

    att = d.get("attachment", {})
    data.attachment = AttachmentInfo(
        topology=_dict_to_att(att.get("topology", {})),
        org_policy=_dict_to_att(att.get("org_policy", {})),
        design_plan=_dict_to_att(att.get("design_plan", {})),
        product_list=_dict_to_att(att.get("product_list", {})),
        service_list=_dict_to_att(att.get("service_list", {})),
        supervisor_doc=_dict_to_att(att.get("supervisor_doc", {})),
    )

    dd = d.get("data", {})
    data.data = DataInfo(
        data_name=dd.get("data_name", ""), data_level=dd.get("data_level", ""),
        data_category=dd.get("data_category", ""), data_dept=dd.get("data_dept", ""),
        data_person=dd.get("data_person", ""), personal_info=dd.get("personal_info", ""),
        total_size=dd.get("total_size", ""), monthly_growth=dd.get("monthly_growth", ""),
        data_source=dd.get("data_source", ""), inflow_units=dd.get("inflow_units", ""),
        outflow_units=dd.get("outflow_units", ""), interaction=dd.get("interaction", ""),
        storage_cloud=dd.get("storage_cloud", ""), storage_room=dd.get("storage_room", ""),
        storage_region=dd.get("storage_region", ""),
    )

    return data


def _dict_to_report(d):
    """从 dict 重建 ReportInfo"""
    from models.project_data import ReportInfo, SubSystem
    r = ReportInfo()
    for key in ["system_name", "responsibility", "composition", "topology_image",
                 "business_desc", "security_resp", "biz_info_desc", "biz_victim",
                 "biz_degree", "biz_level", "svc_desc", "svc_victim",
                 "svc_degree", "svc_level", "final_level"]:
        setattr(r, key, d.get(key, ""))
    for s in d.get("subsystems", []):
        r.subsystems.append(SubSystem(
            index=s.get("index", ""), name=s.get("name", ""),
            description=s.get("description", "")))
    return r


def _dict_to_contact(d):
    from models.project_data import ContactInfo
    return ContactInfo(
        name=d.get("name", ""), title=d.get("title", ""),
        office_phone=d.get("office_phone", ""), mobile=d.get("mobile", ""),
        email=d.get("email", ""))


def _dict_to_att(d):
    from models.project_data import AttachmentItem
    return AttachmentItem(has_file=d.get("has_file", False), file_name=d.get("file_name", ""))


if __name__ == "__main__":
    import logging
    # 抑制 Flask/Werkzeug 的红色 WARNING 输出
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    print("  服务已启动: http://localhost:5000")
    app.run(debug=False, port=5000)
