"""等保文档迁移工具 — Flask Web 后端"""

import os
import sys
import json
import glob
import tempfile
import hashlib
import time

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, jsonify
from models.project_data import ProjectData, ReportInfo
from core.batch_manager import (
    get_system_entry,
    import_manifest as load_manifest_data,
    load_project_state,
    mark_generated,
    save_project_state,
    scan_batch_root as scan_batch_root_dirs,
    scan_project,
    upsert_system_entry,
)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用静态文件缓存
DEV_MODE = os.environ.get("DENGBAO_DEV_MODE") == "1"

# Word 模版目录
DOC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "doc_templates")


@app.route("/")
def index():
    """主页"""
    beian_tpl = _find_file(DOC_TEMPLATE_DIR, "*备案表*.docx")
    report_tpl = _find_file(DOC_TEMPLATE_DIR, "*定级报告*.docx")
    return render_template("index.html",
                           beian_template=beian_tpl or "",
                           report_template=report_tpl or "",
                           dev_mode=DEV_MODE)


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


@app.route("/api/scan_batch_root", methods=["POST"])
def scan_batch_root():
    """扫描总目录下的多个项目。"""
    root_dir = request.json.get("root_dir", "")
    if not root_dir or not os.path.isdir(root_dir):
        return jsonify({"success": False, "message": "总目录不存在"}), 400

    return jsonify({
        "success": True,
        "root_dir": root_dir,
        "projects": scan_batch_root_dirs(root_dir),
    })


@app.route("/api/load_data", methods=["POST"])
def load_data():
    """从旧文件加载数据"""
    old_beian = request.json.get("old_beian", "")
    old_report = request.json.get("old_report", "")
    return jsonify(_load_source_payload(old_beian, old_report))


@app.route("/api/load_system", methods=["POST"])
def load_system():
    """加载批量项目中的单个系统。"""
    project_dir = request.json.get("project_dir", "")
    system_id = request.json.get("system_id", "")
    force_reload = bool(request.json.get("force_reload", False))
    if not project_dir or not os.path.isdir(project_dir):
        return jsonify({"success": False, "message": "项目目录不存在"}), 400
    if not system_id:
        return jsonify({"success": False, "message": "缺少 system_id"}), 400

    project = scan_project(project_dir)
    system = next((item for item in project["systems"] if item["system_id"] == system_id), None)
    if not system:
        return jsonify({"success": False, "message": "未找到系统"}), 404

    state, entry = get_system_entry(project_dir, system_id)
    if not force_reload and entry.get("form_data") and entry.get("report_data"):
        return jsonify({
            "success": True,
            "project": project,
            "system": system,
            "form_data": entry.get("form_data"),
            "report_data": entry.get("report_data"),
            "ui_state": entry.get("ui_state", {}),
            "changes": [],
            "errors": [],
            "from_state": True,
        })

    loaded = _load_source_payload(system.get("old_beian", ""), system.get("old_report", ""))
    form_data = loaded["beian_data"] or _new_project_data_dict()
    report_data = loaded["report_data"] or _new_report_dict()
    form_data["project_name"] = project["project_name"]
    form_data.setdefault("target", {})
    if not form_data["target"].get("name"):
        form_data["target"]["name"] = system["system_name"]
    report_data["system_name"] = system["system_name"]

    upsert_system_entry(
        state,
        project_dir,
        system,
        project_name=project["project_name"],
        output_dir=system.get("output_dir") or project.get("output_dir") or project_dir,
        form_data=form_data,
        report_data=report_data,
    )
    save_project_state(project_dir, state)

    return jsonify({
        "success": True,
        "project": project,
        "system": system,
        "form_data": form_data,
        "report_data": report_data,
        "ui_state": entry.get("ui_state", {}),
        "changes": loaded["changes"],
        "errors": loaded["errors"],
        "from_state": False,
    })


@app.route("/api/save_system", methods=["POST"])
def save_system():
    """保存当前系统编辑状态。"""
    payload = request.json
    project_dir = payload.get("project_dir", "")
    system_id = payload.get("system_id", "")
    if not project_dir or not os.path.isdir(project_dir):
        return jsonify({"success": False, "message": "项目目录不存在"}), 400
    if not system_id:
        return jsonify({"success": False, "message": "缺少 system_id"}), 400

    form_data = payload.get("form_data") or _new_project_data_dict()
    report_data = payload.get("report_data") or _new_report_dict()
    ui_state = payload.get("ui_state") or {}
    project_name = payload.get("project_name") or form_data.get("project_name", "")
    system_meta = payload.get("system_meta") or {}
    system_meta["system_id"] = system_id
    system_meta.setdefault("system_name", form_data.get("target", {}).get("name", ""))

    state = load_project_state(project_dir)
    entry = upsert_system_entry(
        state,
        project_dir,
        system_meta,
        project_name=project_name,
        output_dir=payload.get("output_dir") or system_meta.get("output_dir") or project_dir,
        form_data=form_data,
        report_data=report_data,
        ui_state=ui_state,
    )
    save_project_state(project_dir, state)
    return jsonify({
        "success": True,
        "draft_hash": entry.get("draft_hash", ""),
        "updated_at": entry.get("updated_at", ""),
    })


@app.route("/api/import_manifest", methods=["POST"])
def import_manifest():
    """导入 Excel 项目清单。"""
    manifest_path = request.json.get("manifest_path", "")
    if not manifest_path or not os.path.exists(manifest_path):
        return jsonify({"success": False, "message": "清单文件不存在"}), 400

    try:
        data = load_manifest_data(manifest_path)
        return jsonify({
            "success": True,
            "manifest_path": manifest_path,
            **data,
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"导入清单失败: {e}"}), 500


@app.route("/api/dev_status", methods=["GET"])
def dev_status():
    """开发模式文件签名，用于浏览器自动刷新。"""
    return jsonify({
        "dev_mode": DEV_MODE,
        "signature": _get_dev_watch_signature(),
    })


@app.route("/api/generate", methods=["POST"])
def generate():
    """生成文档"""
    payload = request.json
    paths = payload["paths"]
    form_data = payload["form_data"]
    report_data = payload["report_data"]

    try:
        result = _generate_documents(paths, form_data, report_data)

        project_dir = paths.get("project_dir", "")
        system_id = paths.get("system_id", "")
        if project_dir and system_id and os.path.isdir(project_dir):
            system_meta = payload.get("system_meta") or {
                "system_id": system_id,
                "system_name": _resolve_document_name(paths, form_data, report_data),
                "source_dir": paths.get("source_dir", project_dir),
                "old_beian": paths.get("old_beian", ""),
                "old_report": paths.get("old_report", ""),
                "survey": paths.get("survey", ""),
                "output_dir": paths.get("output_dir", project_dir),
            }
            state = load_project_state(project_dir)
            upsert_system_entry(
                state,
                project_dir,
                system_meta,
                project_name=paths.get("project_name", ""),
                output_dir=paths.get("output_dir", project_dir),
                form_data=form_data,
                report_data=report_data,
                ui_state=payload.get("ui_state") or {},
            )
            mark_generated(state, system_id, result["files"])
            save_project_state(project_dir, state)

        return jsonify({"success": True, **result})
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
        name = _resolve_document_name(paths, form_data, report_data)
        highlighted = form_data.get("highlighted_fields", [])

        from core.doc_writer import generate_beian, generate_report

        temp_dir = os.path.join(tempfile.gettempdir(), "dengbao_preview")
        os.makedirs(temp_dir, exist_ok=True)
        preview_token = str(time.time_ns())

        if doc_type == "beian":
            out = os.path.join(temp_dir, f"预览_备案表_{name}_{preview_token}.docx")
            generate_beian(paths["beian_template"], out, data, highlighted_fields=highlighted)
        else:
            out = os.path.join(temp_dir, f"预览_定级报告_{name}_{preview_token}.docx")
            generate_report(paths["report_template"], out, report, name, highlighted_fields=highlighted)

        os.startfile(out)
        return jsonify({"success": True, "path": out})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/generate_batch", methods=["POST"])
def generate_batch():
    """批量生成多个项目下的系统文档。"""
    payload = request.json
    root_dir = payload.get("root_dir", "")
    paths = payload.get("paths", {})
    selected_projects = set(payload.get("selected_projects", []))
    selected_systems = {
        item.get("project_dir", ""): set(item.get("system_ids", []))
        for item in payload.get("selected_systems", [])
    }
    skip_updated = bool(payload.get("skip_updated", True))

    if not root_dir or not os.path.isdir(root_dir):
        return jsonify({"success": False, "message": "总目录不存在"}), 400

    projects = scan_batch_root_dirs(root_dir)
    generated_count = 0
    skipped_count = 0
    failed_count = 0
    results = []

    for project in projects:
        project_dir = project["project_dir"]
        if selected_projects and project_dir not in selected_projects:
            continue

        allow_system_ids = selected_systems.get(project_dir, set())
        state = load_project_state(project_dir)
        state_changed = False

        for system in project["systems"]:
            if allow_system_ids and system["system_id"] not in allow_system_ids:
                continue

            if skip_updated and not system.get("needs_update"):
                skipped_count += 1
                results.append({
                    "project_name": project["project_name"],
                    "system_name": system["system_name"],
                    "status": "skipped",
                    "message": "已更新，自动跳过",
                })
                continue

            entry = state.get("systems", {}).get(system["system_id"], {})
            form_data = entry.get("form_data")
            report_data = entry.get("report_data")
            if not form_data or not report_data:
                loaded = _load_source_payload(system.get("old_beian", ""), system.get("old_report", ""))
                form_data = loaded["beian_data"] or _new_project_data_dict()
                report_data = loaded["report_data"] or _new_report_dict()
                form_data["project_name"] = project["project_name"]
                form_data.setdefault("target", {})
                if not form_data["target"].get("name"):
                    form_data["target"]["name"] = system["system_name"]
                report_data["system_name"] = system["system_name"]

            try:
                result = _generate_documents(
                    {
                        "project_name": project["project_name"],
                        "document_name": form_data.get("target", {}).get("name") or system["system_name"],
                        "beian_template": paths.get("beian_template", ""),
                        "report_template": paths.get("report_template", ""),
                        "output_dir": system.get("output_dir") or project.get("output_dir") or project_dir,
                    },
                    form_data,
                    report_data,
                )
                upsert_system_entry(
                    state,
                    project_dir,
                    system,
                    project_name=project["project_name"],
                    output_dir=system.get("output_dir") or project.get("output_dir") or project_dir,
                    form_data=form_data,
                    report_data=report_data,
                    ui_state=entry.get("ui_state", {}),
                )
                mark_generated(state, system["system_id"], result["files"])
                state_changed = True
                generated_count += 1
                results.append({
                    "project_name": project["project_name"],
                    "system_name": system["system_name"],
                    "status": "generated",
                    "message": result["message"],
                })
            except Exception as e:
                failed_count += 1
                results.append({
                    "project_name": project["project_name"],
                    "system_name": system["system_name"],
                    "status": "failed",
                    "message": str(e),
                })

        if state_changed:
            save_project_state(project_dir, state)

    return jsonify({
        "success": True,
        "generated_count": generated_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results,
    })


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
        elif file_types == "excel":
            filetypes = [("Excel表格", "*.xlsx *.xls"), ("所有文件", "*.*")]
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
        img_path, desc, cloud_info = read_survey_docx(survey_path)
        return jsonify({
            "topology_image": img_path or "",
            "topology_desc": desc or "",
            "cloud_info": cloud_info or {},
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _load_source_payload(old_beian, old_report):
    """从旧备案表/定级报告读取结构化数据。"""
    result = {"beian_data": None, "report_data": None, "changes": [], "errors": []}

    if old_beian and os.path.exists(old_beian):
        try:
            if old_beian.lower().endswith('.doc'):
                from core.doc_converter import convert_doc_to_docx
                converted = convert_doc_to_docx(old_beian)
                if converted:
                    old_beian = converted
                else:
                    result["errors"].append(
                        f"备案表 .doc 转换失败，请手动用 Word 另存为 .docx\n文件: {old_beian}"
                    )
                    old_beian = ""

            if old_beian:
                from core.doc_reader import read_beian_docx
                data = read_beian_docx(old_beian)
                result["beian_data"] = _dataclass_to_dict(data)
                result["changes"].append("从备案表加载了单位信息、定级对象等数据")
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
                result["changes"].append("从定级报告加载了责任主体、等级等数据")
        except Exception as e:
            result["errors"].append(f"读取定级报告失败: {e}")

    return result


def _generate_documents(paths, form_data, report_data):
    """按当前表单生成正式文档。"""
    data = _dict_to_project_data(form_data)
    report = _dict_to_report(report_data)
    name = _resolve_document_name(paths, form_data, report_data)
    highlighted = form_data.get("highlighted_fields", [])

    from core.doc_writer import generate_beian, generate_report

    out_dir = paths["output_dir"]
    os.makedirs(out_dir, exist_ok=True)

    beian_out = os.path.join(out_dir, f"备案表_{name}.docx")
    generate_beian(paths["beian_template"], beian_out, data, highlighted_fields=highlighted)

    report_out = os.path.join(out_dir, f"定级报告_{name}.docx")
    generate_report(paths["report_template"], report_out, report, name, highlighted_fields=highlighted)

    return {
        "files": [beian_out, report_out],
        "message": f"生成完成！\n备案表: {beian_out}\n定级报告: {report_out}",
    }


def _resolve_document_name(paths, form_data, report_data):
    """统一文档命名，避免同项目多系统覆盖。"""
    return (
        paths.get("document_name")
        or form_data.get("target", {}).get("name", "").strip()
        or report_data.get("system_name", "").strip()
        or paths.get("project_name", "").strip()
        or "未命名系统"
    )


def _new_project_data_dict():
    return _dataclass_to_dict(ProjectData())


def _new_report_dict():
    return _dataclass_to_dict(ReportInfo())


def _get_dev_watch_signature():
    """计算开发模式监听文件签名。"""
    watch_roots = [
        os.path.join(os.path.dirname(__file__), "app.py"),
        os.path.join(os.path.dirname(__file__), "launch.py"),
        os.path.join(os.path.dirname(__file__), "templates"),
        os.path.join(os.path.dirname(__file__), "static"),
        os.path.join(os.path.dirname(__file__), "core"),
        os.path.join(os.path.dirname(__file__), "models"),
    ]
    payload = []
    for root in watch_roots:
        if os.path.isfile(root):
            payload.append(_file_watch_token(root))
            continue
        if not os.path.isdir(root):
            continue
        for current_root, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in {"__pycache__", ".git", ".omc", "output"}]
            for name in sorted(files):
                if not name.endswith((".py", ".html", ".css", ".js")):
                    continue
                payload.append(_file_watch_token(os.path.join(current_root, name)))
    raw = "|".join(item for item in payload if item)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _file_watch_token(path):
    try:
        stat = os.stat(path)
        rel_path = os.path.relpath(path, os.path.dirname(__file__)).replace("\\", "/")
        return f"{rel_path}:{int(stat.st_mtime_ns)}:{stat.st_size}"
    except OSError:
        return ""


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
        biz_type=t.get("biz_type", ""), biz_type_other=t.get("biz_type_other", ""),
        biz_desc=t.get("biz_desc", ""),
        service_scope=t.get("service_scope", ""), service_scope_other=t.get("service_scope_other", ""),
        service_target=t.get("service_target", ""), service_target_other=t.get("service_target_other", ""),
        deploy_scope=t.get("deploy_scope", ""), deploy_scope_other=t.get("deploy_scope_other", ""),
        network_type=t.get("network_type", ""), network_type_other=t.get("network_type_other", ""),
        source_ip=t.get("source_ip", ""), domain=t.get("domain", ""),
        protocol_port=t.get("protocol_port", ""), interconnect=t.get("interconnect", ""),
        interconnect_other=t.get("interconnect_other", ""),
        run_date=t.get("run_date", ""), is_subsystem=t.get("is_subsystem", ""),
        parent_system=t.get("parent_system", ""), parent_unit=t.get("parent_unit", ""),
    )

    g = d.get("grading", {})
    data.grading = GradingInfo(
        biz_level=g.get("biz_level", "第二级"), service_level=g.get("service_level", "第二级"),
        biz_level_items=g.get("biz_level_items", []),
        service_level_items=g.get("service_level_items", []),
        final_level=g.get("final_level", "第二级"), grading_date=g.get("grading_date", ""),
        has_report=g.get("has_report", True), report_name=g.get("report_name", ""),
        has_review=g.get("has_review", True), review_name=g.get("review_name", ""),
        has_supervisor=g.get("has_supervisor", False),
        supervisor_name=g.get("supervisor_name", ""),
        supervisor_reviewed=g.get("supervisor_reviewed", False),
        supervisor_review_status=g.get(
            "supervisor_review_status",
            "已审核" if g.get("supervisor_reviewed", False) else "未审核"
        ),
        supervisor_doc=g.get("supervisor_doc", ""),
        filler=g.get("filler", ""), fill_date=g.get("fill_date", ""),
    )

    s = d.get("scenario", {})
    data.scenario = ScenarioInfo(
        cloud=CloudInfo(
            enabled=s.get("cloud", {}).get("enabled", False),
            role=s.get("cloud", {}).get("role", ""),
            service_model=s.get("cloud", {}).get("service_model", ""),
            service_model_other=s.get("cloud", {}).get("service_model_other", ""),
            deploy_model=s.get("cloud", {}).get("deploy_model", ""),
            deploy_model_other=s.get("cloud", {}).get("deploy_model_other", ""),
            provider_scale=s.get("cloud", {}).get("provider_scale", ""),
            infra_location=s.get("cloud", {}).get("infra_location", ""),
            ops_location=s.get("cloud", {}).get("ops_location", ""),
            provider_preset=s.get("cloud", {}).get("provider_preset", ""),
            provider_kind=s.get("cloud", {}).get("provider_kind", ""),
            provider_name=s.get("cloud", {}).get("provider_name", ""),
            platform_level=s.get("cloud", {}).get("platform_level", ""),
            platform_name=s.get("cloud", {}).get("platform_name", ""),
            platform_code=s.get("cloud", {}).get("platform_code", ""),
            client_ops_location=s.get("cloud", {}).get("client_ops_location", ""),
            platform_cert=s.get("cloud", {}).get("platform_cert", ""),
        ),
        mobile=MobileInfo(
            enabled=s.get("mobile", {}).get("enabled", False),
            app_name=s.get("mobile", {}).get("app_name", ""),
            wireless=s.get("mobile", {}).get("wireless", ""),
            terminal=s.get("mobile", {}).get("terminal", ""),
        ),
        iot=IoTInfo(
            enabled=s.get("iot", {}).get("enabled", False),
            perception=s.get("iot", {}).get("perception", ""),
            transport=s.get("iot", {}).get("transport", ""),
        ),
        ics=ICSInfo(
            enabled=s.get("ics", {}).get("enabled", False),
            function_layer=s.get("ics", {}).get("function_layer", ""),
            composition=s.get("ics", {}).get("composition", ""),
        ),
        bigdata=BigDataInfo(
            enabled=s.get("bigdata", {}).get("enabled", False),
            composition=s.get("bigdata", {}).get("composition", ""),
            cross_border=s.get("bigdata", {}).get("cross_border", ""),
        ),
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
        total_size=dd.get("total_size", ""),
        total_size_unit=dd.get("total_size_unit", "GB"),
        total_size_tb=dd.get("total_size_tb", ""),
        total_size_records=dd.get("total_size_records", ""),
        monthly_growth=dd.get("monthly_growth", ""),
        monthly_growth_unit=dd.get("monthly_growth_unit", "GB"),
        monthly_growth_tb=dd.get("monthly_growth_tb", ""),
        data_source=dd.get("data_source", ""), data_source_other=dd.get("data_source_other", ""),
        inflow_units=dd.get("inflow_units", ""), outflow_units=dd.get("outflow_units", ""),
        interaction=dd.get("interaction", ""), interaction_other=dd.get("interaction_other", ""),
        storage_type=dd.get("storage_type", ""),
        storage_cloud=dd.get("storage_cloud", ""), storage_cloud_name=dd.get("storage_cloud_name", ""),
        storage_room=dd.get("storage_room", ""), storage_room_name=dd.get("storage_room_name", ""),
        storage_region=dd.get("storage_region", ""), storage_region_name=dd.get("storage_region_name", ""),
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
    log.setLevel(logging.INFO if DEV_MODE else logging.ERROR)
    print(f"  服务已启动: http://localhost:5000 ({'开发模式' if DEV_MODE else '稳定模式'})")
    app.run(debug=DEV_MODE, use_reloader=DEV_MODE, port=5000)
