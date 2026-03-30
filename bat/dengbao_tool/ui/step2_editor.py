"""Step 2: 数据编辑页 — 6 个 Tab + 变更追踪"""

import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QFormLayout, QGroupBox,
    QComboBox, QTextEdit, QCheckBox, QScrollArea,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QFrame
)
from PyQt6.QtCore import Qt
from models.project_data import (
    ProjectData, ContactInfo, SubSystem, AttachmentItem
)
from ui.change_tracker import ChangeTracker


def _form_group(title):
    """创建带标题的表单分组"""
    group = QGroupBox(title)
    layout = QFormLayout(group)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    return group, layout


def _line(default="", placeholder="", width=None):
    """创建单行输入"""
    e = QLineEdit(default)
    if placeholder:
        e.setPlaceholderText(placeholder)
    if width:
        e.setFixedWidth(width)
    return e


def _combo(items, current=""):
    """创建下拉框"""
    c = QComboBox()
    c.addItems(items)
    if current:
        idx = c.findText(current)
        if idx >= 0:
            c.setCurrentIndex(idx)
    return c


class Step2EditorPage(QWidget):
    def __init__(self, parent=None, tracker=None):
        super().__init__(parent)
        self.tracker = tracker or ChangeTracker()
        self._tracked_widgets = {}  # field_name → widget
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

        self._build_tab_a()  # 单位信息
        self._build_tab_b()  # 定级对象
        self._build_tab_c()  # 定级等级
        self._build_tab_d()  # 应用场景（表四）
        self._build_tab_e()  # 附件与数据（表五+表六）
        self._build_tab_f()  # 定级报告内容

    # ──────────────── Tab A: 单位信息 ────────────────

    def _build_tab_a(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        # 基本信息
        g1, f1 = _form_group("基本信息")
        self.a_unit_name = _line(placeholder="单位全称")
        self.a_credit_code = _line(placeholder="18位统一社会信用代码")

        # 信用代码行 + 天眼查按钮
        code_row = QWidget()
        code_h = QHBoxLayout(code_row)
        code_h.setContentsMargins(0, 0, 0, 0)
        code_h.addWidget(self.a_credit_code)
        self.btn_tianyancha = QPushButton("天眼查查询")
        self.btn_tianyancha.setFixedWidth(90)
        self.btn_tianyancha.setToolTip("在天眼查搜索该单位信息")
        self.btn_tianyancha.clicked.connect(self._open_tianyancha)
        code_h.addWidget(self.btn_tianyancha)

        self.a_address = _line(placeholder="省 市 县 详细地址")
        self.a_postal = _line(placeholder="邮政编码", width=120)
        self.a_admin_code = _line(placeholder="行政区划代码", width=120)

        f1.addRow("单位名称：", self.a_unit_name)
        f1.addRow("信用代码：", code_row)
        f1.addRow("单位地址：", self.a_address)

        postal_row = QWidget()
        ph = QHBoxLayout(postal_row)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addWidget(QLabel("邮编："))
        ph.addWidget(self.a_postal)
        ph.addWidget(QLabel("行政区划代码："))
        ph.addWidget(self.a_admin_code)
        ph.addStretch()
        f1.addRow("", postal_row)
        main_layout.addWidget(g1)

        # 单位负责人
        g2, f2 = _form_group("单位负责人")
        self.a_leader_name = _line(width=150)
        self.a_leader_title = _line(width=150)
        self.a_leader_phone = _line(width=200)
        self.a_leader_email = _line(width=200)
        f2.addRow("姓名：", self.a_leader_name)
        f2.addRow("职务/职称：", self.a_leader_title)
        f2.addRow("办公电话：", self.a_leader_phone)
        f2.addRow("电子邮件：", self.a_leader_email)
        main_layout.addWidget(g2)

        # 网络安全责任部门
        g3, f3 = _form_group("网络安全责任部门")
        self.a_sec_dept = _line()
        self.a_sec_name = _line(width=150)
        self.a_sec_title = _line(width=150)
        self.a_sec_phone = _line(width=200)
        self.a_sec_mobile = _line(width=200)
        self.a_sec_email = _line(width=200)
        f3.addRow("部门名称：", self.a_sec_dept)
        f3.addRow("联系人姓名：", self.a_sec_name)
        f3.addRow("职务/职称：", self.a_sec_title)
        f3.addRow("办公电话：", self.a_sec_phone)
        f3.addRow("移动电话：", self.a_sec_mobile)
        f3.addRow("电子邮件：", self.a_sec_email)
        main_layout.addWidget(g3)

        # 数据安全管理部门
        g4, f4 = _form_group("数据安全管理部门")
        self.a_data_dept = _line()
        self.a_data_name = _line(width=150)
        self.a_data_title = _line(width=150)
        self.a_data_phone = _line(width=200)
        self.a_data_mobile = _line(width=200)
        self.a_data_email = _line(width=200)

        # 复制按钮
        copy_btn = QPushButton("与安全责任部门相同")
        copy_btn.setFixedWidth(140)
        copy_btn.clicked.connect(self._copy_sec_to_data)

        f4.addRow("", copy_btn)
        f4.addRow("部门名称：", self.a_data_dept)
        f4.addRow("联系人姓名：", self.a_data_name)
        f4.addRow("职务/职称：", self.a_data_title)
        f4.addRow("办公电话：", self.a_data_phone)
        f4.addRow("移动电话：", self.a_data_mobile)
        f4.addRow("电子邮件：", self.a_data_email)
        main_layout.addWidget(g4)

        # 隶属关系等
        g5, f5 = _form_group("单位属性")
        self.a_affiliation = _combo([
            "", "1-中央", "2-省(自治区、直辖市)", "3-地(市、州、盟)", "4-县(区、市、旗)", "9-其他"])
        self.a_unit_type = _combo(["", "1-党委机关", "2-政府机关", "3-事业单位", "4-企业", "9-其他"])
        self.a_industry = _combo([
            "", "1-海关", "2-税务", "3-市场监督管理", "4-广播电视", "5-体育",
            "6-统计", "7-国际发展合作", "8-医疗保障", "9-参事", "10-机关事务管理",
            "11-外交", "12-国防科技工业", "13-发展和改革", "14-教育", "15-科学技术",
            "16-工业和信息化", "17-民族事务", "18-公安", "19-安全", "20-民政",
            "21-司法", "22-财政", "23-人力资源和社会保障", "24-自然资源", "25-生态环境",
            "26-住房和城乡建设", "27-交通运输", "28-水利", "29-农业农村", "30-商务",
            "31-文化和旅游", "32-卫生健康", "33-退役军人事务", "34-应急管理", "35-银行",
            "36-审计", "37-铁路", "38-电信", "39-经营性公众互联网", "40-保险",
            "41-证券", "42-气象", "43-民航", "44-电力", "45-能源",
            "46-邮政", "47-数据管理", "48-电子政务", "99-其他"])
        f5.addRow("隶属关系：", self.a_affiliation)
        f5.addRow("单位类型：", self.a_unit_type)
        f5.addRow("行业类别：", self.a_industry)
        main_layout.addWidget(g5)

        # 定级对象数量
        g6, f6 = _form_group("定级对象数量统计")
        self.a_cur_total = _line("1", width=60)
        self.a_cur_l2 = _line("1", width=60)
        self.a_cur_l3 = _line("0", width=60)
        self.a_cur_l4 = _line("0", width=60)
        self.a_cur_l5 = _line("0", width=60)

        cur_row = QWidget()
        ch = QHBoxLayout(cur_row)
        ch.setContentsMargins(0, 0, 0, 0)
        for label, w in [("总数:", self.a_cur_total), ("二级:", self.a_cur_l2),
                         ("三级:", self.a_cur_l3), ("四级:", self.a_cur_l4), ("五级:", self.a_cur_l5)]:
            ch.addWidget(QLabel(label))
            ch.addWidget(w)
        ch.addStretch()
        f6.addRow("本次备案：", cur_row)

        self.a_all_total = _line("1", width=60)
        self.a_all_l1 = _line("0", width=60)
        self.a_all_l2 = _line("1", width=60)
        self.a_all_l3 = _line("0", width=60)
        self.a_all_l4 = _line("0", width=60)
        self.a_all_l5 = _line("0", width=60)

        all_row = QWidget()
        ah = QHBoxLayout(all_row)
        ah.setContentsMargins(0, 0, 0, 0)
        for label, w in [("总数:", self.a_all_total), ("一级:", self.a_all_l1),
                         ("二级:", self.a_all_l2), ("三级:", self.a_all_l3),
                         ("四级:", self.a_all_l4), ("五级:", self.a_all_l5)]:
            ah.addWidget(QLabel(label))
            ah.addWidget(w)
        ah.addStretch()
        f6.addRow("总数(含本次)：", all_row)
        main_layout.addWidget(g6)

        main_layout.addStretch()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, "单位信息")

    def _open_tianyancha(self):
        name = self.a_unit_name.text().strip()
        if name:
            webbrowser.open(f"https://www.tianyancha.com/search?key={name}")

    def _copy_sec_to_data(self):
        self.a_data_dept.setText(self.a_sec_dept.text())
        self.a_data_name.setText(self.a_sec_name.text())
        self.a_data_title.setText(self.a_sec_title.text())
        self.a_data_phone.setText(self.a_sec_phone.text())
        self.a_data_mobile.setText(self.a_sec_mobile.text())
        self.a_data_email.setText(self.a_sec_email.text())

    # ──────────────── 变更追踪辅助 ────────────────

    def _track(self, field_name, widget):
        """注册控件的编辑追踪"""
        self._tracked_widgets[field_name] = widget
        if isinstance(widget, QLineEdit):
            widget._prev_val = widget.text()
            widget.editingFinished.connect(
                lambda w=widget, fn=field_name: self._on_edit_finished(fn, w))
        elif isinstance(widget, QTextEdit):
            widget._prev_val = widget.toPlainText()
            widget.textChanged.connect(
                lambda fn=field_name, w=widget: self._on_textedit_changed(fn, w))

    def _on_edit_finished(self, field_name, widget):
        new_val = widget.text()
        old_val = getattr(widget, '_prev_val', '')
        if new_val != old_val:
            self.tracker.record_edit(field_name, old_val, new_val)
            widget._prev_val = new_val
            widget.setProperty("fieldState", "modified")
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _on_textedit_changed(self, field_name, widget):
        new_val = widget.toPlainText()
        old_val = getattr(widget, '_prev_val', '')
        if new_val != old_val and not self.tracker._suppressed:
            self.tracker.record_edit(field_name, old_val, new_val)
            widget._prev_val = new_val
            widget.setProperty("fieldState", "modified")
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _set_tracked(self, widget, field_name, value):
        """设置控件值并记录自动填充"""
        if not value or not str(value).strip():
            return
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
            widget._prev_val = str(value)
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(str(value))
            widget._prev_val = str(value)
        self.tracker.record_load(field_name, str(value))
        widget.setProperty("fieldState", "auto")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ──────────────── Tab B: 定级对象 ────────────────

    def _build_tab_b(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        g1, f1 = _form_group("定级对象基本信息")
        self.b_name = _line(placeholder="定级对象名称")
        self.b_code = _line(placeholder="编号（如 26003）", width=150)
        self.b_type = _combo(["信息系统", "通信网络设施", "数据资源"])
        self.b_biz_type = _combo([
            "", "1-生产作业", "2-指挥调度", "3-内部办公", "4-公众服务", "9-其他"])
        self.b_biz_desc = QTextEdit()
        self.b_biz_desc.setMaximumHeight(80)
        self.b_biz_desc.setPlaceholderText("描述系统承载的业务...")

        f1.addRow("对象名称：", self.b_name)
        f1.addRow("编号：", self.b_code)
        f1.addRow("对象类型：", self.b_type)
        f1.addRow("业务类型：", self.b_biz_type)
        f1.addRow("业务描述：", self.b_biz_desc)
        main_layout.addWidget(g1)

        g2, f2 = _form_group("网络与服务")
        self.b_svc_scope = _combo([
            "", "30-地(市、区)内", "20-全省(区、市)", "21-跨地(市、区)",
            "10-全国", "11-跨省(区、市)", "99-其他"])
        self.b_svc_target = _combo([
            "", "1-单位内部人员", "2-社会公众人员", "3-两者均包括", "9-其他"])
        self.b_deploy = _combo(["", "1-局域网", "2-城域网", "3-广域网", "9-其他"])
        self.b_net_type = _combo(["", "1-业务专网", "2-互联网", "9-其他"])
        self.b_interconnect = _line(placeholder="网络互联情况")
        self.b_run_date = _line(placeholder="如: 2022 年 12 月 01 日")

        f2.addRow("服务范围：", self.b_svc_scope)
        f2.addRow("服务对象：", self.b_svc_target)
        f2.addRow("部署范围：", self.b_deploy)
        f2.addRow("网络性质：", self.b_net_type)
        f2.addRow("互联情况：", self.b_interconnect)
        f2.addRow("运行时间：", self.b_run_date)
        main_layout.addWidget(g2)

        g3, f3 = _form_group("上级系统（如有）")
        self.b_is_sub = _combo(["否", "是"])
        self.b_parent_sys = _line()
        self.b_parent_unit = _line()
        f3.addRow("是否分系统：", self.b_is_sub)
        f3.addRow("上级系统名称：", self.b_parent_sys)
        f3.addRow("上级系统单位：", self.b_parent_unit)
        main_layout.addWidget(g3)

        main_layout.addStretch()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, "定级对象")

    # ──────────────── Tab C: 定级等级 ────────────────

    def _build_tab_c(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        levels = ["第一级", "第二级", "第三级", "第四级", "第五级"]

        # 业务信息安全等级
        g1, f1 = _form_group("业务信息安全保护等级")
        self.c_biz_level = _combo(levels, "第二级")
        f1.addRow("等级：", self.c_biz_level)
        main_layout.addWidget(g1)

        # 系统服务安全等级
        g2, f2 = _form_group("系统服务安全保护等级")
        self.c_svc_level = _combo(levels, "第二级")
        f2.addRow("等级：", self.c_svc_level)
        main_layout.addWidget(g2)

        # 最终等级（自动计算）
        g3, f3 = _form_group("最终安全保护等级")
        self.c_final_level = QLabel("第二级")
        self.c_final_level.setStyleSheet("font-size: 16px; font-weight: bold; color: #1890ff;")
        f3.addRow("等级：", self.c_final_level)
        main_layout.addWidget(g3)

        # 联动
        self.c_biz_level.currentTextChanged.connect(self._update_final_level)
        self.c_svc_level.currentTextChanged.connect(self._update_final_level)

        # 定级附属信息
        g4, f4 = _form_group("定级信息")
        self.c_grading_date = _line(placeholder="如: 2024 年 12 月 14 日")
        self.c_has_report = QCheckBox("有定级报告")
        self.c_has_report.setChecked(True)
        self.c_report_name = _line(placeholder="如: 《定级报告_XX》")
        self.c_has_review = QCheckBox("已专家评审")
        self.c_has_review.setChecked(True)
        self.c_review_name = _line(placeholder="如: 《专家评审意见表_XX》")
        self.c_has_supervisor = QCheckBox("有上级行业主管部门")
        self.c_supervisor_name = _line()
        self.c_filler = _line(placeholder="填表人姓名")
        self.c_fill_date = _line(placeholder="如: 2024 年 12 月 04 日")

        f4.addRow("定级时间：", self.c_grading_date)
        f4.addRow("", self.c_has_report)
        f4.addRow("报告附件名：", self.c_report_name)
        f4.addRow("", self.c_has_review)
        f4.addRow("评审附件名：", self.c_review_name)
        f4.addRow("", self.c_has_supervisor)
        f4.addRow("主管部门名称：", self.c_supervisor_name)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        f4.addRow(sep)
        f4.addRow("填表人：", self.c_filler)
        f4.addRow("填表日期：", self.c_fill_date)
        main_layout.addWidget(g4)

        main_layout.addStretch()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, "定级等级")

    def _update_final_level(self):
        levels = {"第一级": 1, "第二级": 2, "第三级": 3, "第四级": 4, "第五级": 5}
        biz = levels.get(self.c_biz_level.currentText(), 2)
        svc = levels.get(self.c_svc_level.currentText(), 2)
        final = max(biz, svc)
        level_names = {v: k for k, v in levels.items()}
        self.c_final_level.setText(level_names[final])

    # ──────────────── Tab D: 应用场景（表四） ────────────────

    def _build_tab_d(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        hint = QLabel("传统系统全部选\"否\"即可跳过。")
        hint.setProperty("class", "hint")
        main_layout.addWidget(hint)

        # 云计算
        g1, f1 = _form_group("云计算")
        self.d_cloud_enabled = QCheckBox("是否采用云计算技术")
        self.d_cloud_role = _combo(["", "云服务商", "云服务客户", "二者均勾选"])
        self.d_cloud_service = _combo(["", "IaaS", "PaaS", "SaaS", "其他"])
        self.d_cloud_deploy = _combo(["", "私有云", "公有云", "混合云", "其他"])
        self.d_cloud_provider = _line(placeholder="云服务商名称")
        self.d_cloud_plat_level = _line(placeholder="平台安全等级")
        self.d_cloud_plat_name = _line(placeholder="平台名称")
        self.d_cloud_plat_code = _line(placeholder="平台备案编号")
        self.d_cloud_ops = _line(placeholder="客户运维地点")

        f1.addRow("", self.d_cloud_enabled)
        f1.addRow("责任主体：", self.d_cloud_role)
        f1.addRow("服务模式：", self.d_cloud_service)
        f1.addRow("部署模式：", self.d_cloud_deploy)
        f1.addRow("云服务商：", self.d_cloud_provider)
        f1.addRow("平台等级：", self.d_cloud_plat_level)
        f1.addRow("平台名称：", self.d_cloud_plat_name)
        f1.addRow("备案编号：", self.d_cloud_plat_code)
        f1.addRow("运维地点：", self.d_cloud_ops)

        # 存储需要联动隐藏的控件
        self._cloud_fields = [
            self.d_cloud_role, self.d_cloud_service, self.d_cloud_deploy,
            self.d_cloud_provider, self.d_cloud_plat_level, self.d_cloud_plat_name,
            self.d_cloud_plat_code, self.d_cloud_ops
        ]
        self.d_cloud_enabled.toggled.connect(
            lambda on: [w.setEnabled(on) for w in self._cloud_fields])
        for w in self._cloud_fields:
            w.setEnabled(False)
        main_layout.addWidget(g1)

        # 移动互联
        g2, f2 = _form_group("移动互联")
        self.d_mobile_enabled = QCheckBox("是否采用移动互联技术")
        self.d_mobile_app = _line(placeholder="应用/小程序名称")
        self.d_mobile_wireless = _combo(["", "公共WIFI", "专用WIFI", "移动通信网"])
        self.d_mobile_terminal = _combo(["", "通用终端", "专用终端"])
        f2.addRow("", self.d_mobile_enabled)
        f2.addRow("应用名称：", self.d_mobile_app)
        f2.addRow("无线通道：", self.d_mobile_wireless)
        f2.addRow("终端类型：", self.d_mobile_terminal)

        self._mobile_fields = [self.d_mobile_app, self.d_mobile_wireless, self.d_mobile_terminal]
        self.d_mobile_enabled.toggled.connect(
            lambda on: [w.setEnabled(on) for w in self._mobile_fields])
        for w in self._mobile_fields:
            w.setEnabled(False)
        main_layout.addWidget(g2)

        # 物联网
        g3, f3 = _form_group("物联网")
        self.d_iot_enabled = QCheckBox("是否为物联网系统")
        self.d_iot_perception = _line(placeholder="感知层（多选填写）")
        self.d_iot_transport = _line(placeholder="传输层（多选填写）")
        f3.addRow("", self.d_iot_enabled)
        f3.addRow("感知层：", self.d_iot_perception)
        f3.addRow("传输层：", self.d_iot_transport)

        self._iot_fields = [self.d_iot_perception, self.d_iot_transport]
        self.d_iot_enabled.toggled.connect(
            lambda on: [w.setEnabled(on) for w in self._iot_fields])
        for w in self._iot_fields:
            w.setEnabled(False)
        main_layout.addWidget(g3)

        # 工业控制
        g4, f4 = _form_group("工业控制系统")
        self.d_ics_enabled = QCheckBox("是否为工业控制系统")
        self.d_ics_layer = _line(placeholder="功能层次（多选填写）")
        self.d_ics_comp = _line(placeholder="系统组成（多选填写）")
        f4.addRow("", self.d_ics_enabled)
        f4.addRow("功能层次：", self.d_ics_layer)
        f4.addRow("系统组成：", self.d_ics_comp)

        self._ics_fields = [self.d_ics_layer, self.d_ics_comp]
        self.d_ics_enabled.toggled.connect(
            lambda on: [w.setEnabled(on) for w in self._ics_fields])
        for w in self._ics_fields:
            w.setEnabled(False)
        main_layout.addWidget(g4)

        # 大数据
        g5, f5 = _form_group("大数据")
        self.d_bigdata_enabled = QCheckBox("是否采用大数据技术")
        self.d_bigdata_comp = _line(placeholder="系统组成（多选填写）")
        self.d_bigdata_cross = _combo(["无出境需求", "有出境需求"])
        f5.addRow("", self.d_bigdata_enabled)
        f5.addRow("系统组成：", self.d_bigdata_comp)
        f5.addRow("出境情况：", self.d_bigdata_cross)

        self._bigdata_fields = [self.d_bigdata_comp, self.d_bigdata_cross]
        self.d_bigdata_enabled.toggled.connect(
            lambda on: [w.setEnabled(on) for w in self._bigdata_fields])
        for w in self._bigdata_fields:
            w.setEnabled(False)
        main_layout.addWidget(g5)

        main_layout.addStretch()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, "表四-应用场景")

    # ──────────────── Tab E: 附件与数据（表五+表六） ────────────────

    def _build_tab_e(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        # 表五：附件清单
        g1, f1 = _form_group("表五 — 定级对象提交材料情况")
        hint = QLabel("一般前两项选\"有\"，其余选\"无\"")
        hint.setStyleSheet("color: #999;")
        f1.addRow("", hint)

        self.e_attachments = {}
        att_items = [
            ("topology", "网络拓扑结构及说明", True),
            ("org_policy", "安全组织架构及管理制度清单", True),
            ("design_plan", "安全建设/整改设计方案", False),
            ("product_list", "安全专用产品清单及证书", False),
            ("service_list", "安全服务清单", False),
            ("supervisor_doc", "主管部门指导定级文件", False),
        ]
        for key, label, default_has in att_items:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox("有")
            cb.setChecked(default_has)
            name_edit = _line(placeholder="附件名称")
            h.addWidget(cb)
            h.addWidget(name_edit)
            f1.addRow(f"{label}：", row)
            self.e_attachments[key] = {"check": cb, "name": name_edit}
        main_layout.addWidget(g1)

        # 表六：数据信息
        g2, f2 = _form_group("表六 — 数据信息")
        self.e_data_name = _line(placeholder="如: 物资采购数据")
        self.e_data_level = _combo(["1-一般数据", "2-重要及以上数据"])
        self.e_data_category = _line(placeholder="如: 业务数据")
        self.e_data_dept = _line()
        self.e_data_person = _line()
        self.e_personal_info = _combo([
            "", "1-涉及敏感个人信息", "2-涉及未成年人个人信息",
            "3-涉及一般个人信息", "4-不涉及"])
        self.e_total_size = _line(placeholder="如: 30 GB")
        self.e_monthly_growth = _line(placeholder="如: 1 GB")

        f2.addRow("数据名称：", self.e_data_name)
        f2.addRow("数据级别：", self.e_data_level)
        f2.addRow("数据类别：", self.e_data_category)
        f2.addRow("安全责任部门：", self.e_data_dept)
        f2.addRow("安全负责人：", self.e_data_person)
        f2.addRow("个人信息：", self.e_personal_info)
        f2.addRow("数据总量：", self.e_total_size)
        f2.addRow("月增长量：", self.e_monthly_growth)
        main_layout.addWidget(g2)

        main_layout.addStretch()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, "表五六-附件数据")

    # ──────────────── Tab F: 定级报告内容 ────────────────

    def _build_tab_f(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        # 责任主体
        g1, f1 = _form_group("一、定级对象描述")
        self.f_responsibility = QTextEdit()
        self.f_responsibility.setMaximumHeight(80)
        self.f_responsibility.setPlaceholderText("描述责任主体、安全责任部门...")
        f1.addRow("(一) 责任主体：", self.f_responsibility)

        self.f_composition = QTextEdit()
        self.f_composition.setMaximumHeight(80)
        self.f_composition.setPlaceholderText("描述定级对象构成、网络结构、边界设备...")
        f1.addRow("(二) 对象构成：", self.f_composition)

        # 网络拓扑图
        topo_row = QWidget()
        th = QHBoxLayout(topo_row)
        th.setContentsMargins(0, 0, 0, 0)
        self.f_topology_path = _line(placeholder="选择拓扑图文件 (.png/.jpg)")
        topo_btn = QPushButton("选择图片...")
        topo_btn.setFixedWidth(80)
        topo_btn.clicked.connect(self._browse_topology)
        th.addWidget(self.f_topology_path)
        th.addWidget(topo_btn)
        f1.addRow("网络拓扑图：", topo_row)

        self.f_business = QTextEdit()
        self.f_business.setMaximumHeight(80)
        self.f_business.setPlaceholderText("描述承载的业务...")
        f1.addRow("(三) 承载业务：", self.f_business)

        self.f_security = QTextEdit()
        self.f_security.setMaximumHeight(80)
        self.f_security.setPlaceholderText("描述安全责任落实...")
        f1.addRow("(四) 安全责任：", self.f_security)
        main_layout.addWidget(g1)

        # 子系统表
        g2 = QGroupBox("子系统列表")
        g2_layout = QVBoxLayout(g2)
        self.f_subsystems = QTableWidget(0, 3)
        self.f_subsystems.setHorizontalHeaderLabels(["序号", "子系统名称", "业务功能描述"])
        self.f_subsystems.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.f_subsystems.setColumnWidth(0, 50)
        self.f_subsystems.setColumnWidth(1, 150)
        self.f_subsystems.setMaximumHeight(150)
        g2_layout.addWidget(self.f_subsystems)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加行")
        add_btn.clicked.connect(self._add_subsystem_row)
        del_btn = QPushButton("删除行")
        del_btn.clicked.connect(self._del_subsystem_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        g2_layout.addLayout(btn_row)
        main_layout.addWidget(g2)

        # 等级确定描述
        g3, f3 = _form_group("二、安全保护等级确定")
        self.f_biz_info = QTextEdit()
        self.f_biz_info.setMaximumHeight(60)
        self.f_biz_info.setPlaceholderText("业务信息描述...")
        self.f_biz_victim = QTextEdit()
        self.f_biz_victim.setMaximumHeight(60)
        self.f_biz_victim.setPlaceholderText("侵害客体...")
        self.f_biz_degree = QTextEdit()
        self.f_biz_degree.setMaximumHeight(60)
        self.f_biz_degree.setPlaceholderText("侵害程度...")

        f3.addRow("业务信息描述：", self.f_biz_info)
        f3.addRow("侵害客体：", self.f_biz_victim)
        f3.addRow("侵害程度：", self.f_biz_degree)

        self.f_svc_desc = QTextEdit()
        self.f_svc_desc.setMaximumHeight(60)
        self.f_svc_desc.setPlaceholderText("系统服务描述...")
        self.f_svc_victim = QTextEdit()
        self.f_svc_victim.setMaximumHeight(60)
        self.f_svc_victim.setPlaceholderText("侵害客体...")
        self.f_svc_degree = QTextEdit()
        self.f_svc_degree.setMaximumHeight(60)
        self.f_svc_degree.setPlaceholderText("侵害程度...")

        f3.addRow("系统服务描述：", self.f_svc_desc)
        f3.addRow("侵害客体：", self.f_svc_victim)
        f3.addRow("侵害程度：", self.f_svc_degree)
        main_layout.addWidget(g3)

        main_layout.addStretch()
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, "定级报告")

    def _browse_topology(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择拓扑图", "", "图片 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)")
        if path:
            self.f_topology_path.setText(path)

    def _add_subsystem_row(self):
        row = self.f_subsystems.rowCount()
        self.f_subsystems.insertRow(row)
        self.f_subsystems.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def _del_subsystem_row(self):
        row = self.f_subsystems.currentRow()
        if row >= 0:
            self.f_subsystems.removeRow(row)

    # ──────────────── 数据填充 / 收集 ────────────────

    def load_data(self, data: ProjectData):
        """从 ProjectData 填充到 GUI，记录自动填充"""
        self.tracker.suppress(True)
        t = self._set_tracked  # shorthand

        u = data.unit
        t(self.a_unit_name, "单位名称", u.unit_name)
        t(self.a_credit_code, "信用代码", u.credit_code)
        t(self.a_address, "单位地址", u.address)
        t(self.a_postal, "邮编", u.postal_code)
        t(self.a_admin_code, "行政区划代码", u.admin_code)
        t(self.a_leader_name, "负责人姓名", u.leader.name)
        t(self.a_leader_title, "负责人职务", u.leader.title)
        t(self.a_leader_phone, "负责人电话", u.leader.office_phone)
        t(self.a_leader_email, "负责人邮件", u.leader.email)
        t(self.a_sec_dept, "安全责任部门", u.security_dept)
        t(self.a_sec_name, "安全联系人", u.security_contact.name)
        t(self.a_sec_title, "安全联系人职务", u.security_contact.title)
        t(self.a_sec_phone, "安全联系人电话", u.security_contact.office_phone)
        t(self.a_sec_mobile, "安全联系人手机", u.security_contact.mobile)
        t(self.a_sec_email, "安全联系人邮件", u.security_contact.email)
        t(self.a_data_dept, "数据安全部门", u.data_dept)
        t(self.a_data_name, "数据联系人", u.data_contact.name)
        t(self.a_data_title, "数据联系人职务", u.data_contact.title)
        t(self.a_data_phone, "数据联系人电话", u.data_contact.office_phone)
        t(self.a_data_mobile, "数据联系人手机", u.data_contact.mobile)
        t(self.a_data_email, "数据联系人邮件", u.data_contact.email)
        t(self.a_cur_total, "本次备案总数", u.current_total)
        t(self.a_cur_l2, "本次二级数", u.current_level2)
        t(self.a_cur_l3, "本次三级数", u.current_level3)
        t(self.a_cur_l4, "本次四级数", u.current_level4)
        t(self.a_cur_l5, "本次五级数", u.current_level5)
        t(self.a_all_total, "总数", u.all_total)
        t(self.a_all_l1, "一级总数", u.all_level1)
        t(self.a_all_l2, "二级总数", u.all_level2)
        t(self.a_all_l3, "三级总数", u.all_level3)
        t(self.a_all_l4, "四级总数", u.all_level4)
        t(self.a_all_l5, "五级总数", u.all_level5)

        tgt = data.target
        t(self.b_name, "定级对象名称", tgt.name)
        t(self.b_code, "定级对象编号", tgt.code)
        t(self.b_biz_desc, "业务描述", tgt.biz_desc)
        t(self.b_run_date, "运行时间", tgt.run_date)
        t(self.b_interconnect, "互联情况", tgt.interconnect)
        t(self.b_parent_sys, "上级系统", tgt.parent_system)
        t(self.b_parent_unit, "上级单位", tgt.parent_unit)

        g = data.grading
        t(self.c_grading_date, "定级时间", g.grading_date)
        self.c_has_report.setChecked(g.has_report)
        t(self.c_report_name, "报告附件名", g.report_name)
        self.c_has_review.setChecked(g.has_review)
        t(self.c_review_name, "评审附件名", g.review_name)
        t(self.c_filler, "填表人", g.filler)
        t(self.c_fill_date, "填表日期", g.fill_date)

        sc = data.scenario
        self.d_cloud_enabled.setChecked(sc.cloud.enabled)
        if sc.cloud.provider_name:
            t(self.d_cloud_provider, "云服务商", sc.cloud.provider_name)
        if sc.cloud.client_ops_location:
            t(self.d_cloud_ops, "云运维地点", sc.cloud.client_ops_location)

        d = data.data
        t(self.e_data_name, "数据名称", d.data_name)
        t(self.e_data_category, "数据类别", d.data_category)
        t(self.e_data_dept, "数据责任部门", d.data_dept)
        t(self.e_data_person, "数据负责人", d.data_person)
        t(self.e_total_size, "数据总量", d.total_size)
        t(self.e_monthly_growth, "月增长量", d.monthly_growth)

        self.tracker.suppress(False)

        # 注册关键字段的编辑追踪
        tracked_fields = {
            "单位名称": self.a_unit_name, "信用代码": self.a_credit_code,
            "单位地址": self.a_address, "负责人姓名": self.a_leader_name,
            "安全责任部门": self.a_sec_dept, "安全联系人": self.a_sec_name,
            "数据安全部门": self.a_data_dept, "数据联系人": self.a_data_name,
            "定级对象名称": self.b_name, "定级对象编号": self.b_code,
            "业务描述": self.b_biz_desc, "运行时间": self.b_run_date,
            "定级时间": self.c_grading_date, "填表人": self.c_filler,
            "数据名称": self.e_data_name, "数据类别": self.e_data_category,
        }
        for fn, w in tracked_fields.items():
            self._track(fn, w)

    def load_report(self, report):
        """从 ReportInfo 填充定级报告 Tab"""
        self.tracker.suppress(True)
        t = self._set_tracked

        t(self.f_responsibility, "责任主体", report.responsibility)
        t(self.f_composition, "对象构成", report.composition)
        t(self.f_business, "承载业务", report.business_desc)
        t(self.f_security, "安全责任", report.security_resp)
        t(self.f_topology_path, "拓扑图路径", report.topology_image)
        t(self.f_biz_info, "业务信息描述", report.biz_info_desc)
        t(self.f_biz_victim, "业务侵害客体", report.biz_victim)
        t(self.f_biz_degree, "业务侵害程度", report.biz_degree)
        t(self.f_svc_desc, "服务描述", report.svc_desc)
        t(self.f_svc_victim, "服务侵害客体", report.svc_victim)
        t(self.f_svc_degree, "服务侵害程度", report.svc_degree)

        if report.biz_level:
            self.c_biz_level.setCurrentText(report.biz_level)
        if report.svc_level:
            self.c_svc_level.setCurrentText(report.svc_level)

        for sub in report.subsystems:
            row = self.f_subsystems.rowCount()
            self.f_subsystems.insertRow(row)
            self.f_subsystems.setItem(row, 0, QTableWidgetItem(sub.index))
            self.f_subsystems.setItem(row, 1, QTableWidgetItem(sub.name))
            self.f_subsystems.setItem(row, 2, QTableWidgetItem(sub.description))

        self.tracker.suppress(False)

        # 注册报告字段追踪
        report_fields = {
            "责任主体": self.f_responsibility, "对象构成": self.f_composition,
            "承载业务": self.f_business, "安全责任": self.f_security,
            "业务信息描述": self.f_biz_info, "业务侵害客体": self.f_biz_victim,
            "业务侵害程度": self.f_biz_degree, "服务描述": self.f_svc_desc,
        }
        for fn, w in report_fields.items():
            self._track(fn, w)

    def collect_data(self) -> ProjectData:
        """从 GUI 收集数据到 ProjectData"""
        data = ProjectData()
        u = data.unit
        u.unit_name = self.a_unit_name.text()
        u.credit_code = self.a_credit_code.text()
        u.address = self.a_address.text()
        u.postal_code = self.a_postal.text()
        u.admin_code = self.a_admin_code.text()
        u.leader = ContactInfo(
            self.a_leader_name.text(), self.a_leader_title.text(),
            self.a_leader_phone.text(), "", self.a_leader_email.text())
        u.security_dept = self.a_sec_dept.text()
        u.security_contact = ContactInfo(
            self.a_sec_name.text(), self.a_sec_title.text(),
            self.a_sec_phone.text(), self.a_sec_mobile.text(), self.a_sec_email.text())
        u.data_dept = self.a_data_dept.text()
        u.data_contact = ContactInfo(
            self.a_data_name.text(), self.a_data_title.text(),
            self.a_data_phone.text(), self.a_data_mobile.text(), self.a_data_email.text())
        u.current_total = self.a_cur_total.text()
        u.current_level2 = self.a_cur_l2.text()
        u.current_level3 = self.a_cur_l3.text()
        u.current_level4 = self.a_cur_l4.text()
        u.current_level5 = self.a_cur_l5.text()
        u.all_total = self.a_all_total.text()
        u.all_level1 = self.a_all_l1.text()
        u.all_level2 = self.a_all_l2.text()
        u.all_level3 = self.a_all_l3.text()
        u.all_level4 = self.a_all_l4.text()
        u.all_level5 = self.a_all_l5.text()

        tgt = data.target
        tgt.name = self.b_name.text()
        tgt.code = self.b_code.text()
        tgt.target_type = self.b_type.currentText()
        tgt.biz_type = self.b_biz_type.currentText()
        tgt.biz_desc = self.b_biz_desc.toPlainText()
        tgt.service_scope = self.b_svc_scope.currentText()
        tgt.service_target = self.b_svc_target.currentText()
        tgt.deploy_scope = self.b_deploy.currentText()
        tgt.network_type = self.b_net_type.currentText()
        tgt.interconnect = self.b_interconnect.text()
        tgt.run_date = self.b_run_date.text()
        tgt.is_subsystem = self.b_is_sub.currentText()
        tgt.parent_system = self.b_parent_sys.text()
        tgt.parent_unit = self.b_parent_unit.text()

        g = data.grading
        g.biz_level = self.c_biz_level.currentText()
        g.service_level = self.c_svc_level.currentText()
        g.final_level = self.c_final_level.text()
        g.grading_date = self.c_grading_date.text()
        g.has_report = self.c_has_report.isChecked()
        g.report_name = self.c_report_name.text()
        g.has_review = self.c_has_review.isChecked()
        g.review_name = self.c_review_name.text()
        g.has_supervisor = self.c_has_supervisor.isChecked()
        g.supervisor_name = self.c_supervisor_name.text()
        g.filler = self.c_filler.text()
        g.fill_date = self.c_fill_date.text()

        sc = data.scenario
        sc.cloud.enabled = self.d_cloud_enabled.isChecked()
        sc.cloud.role = self.d_cloud_role.currentText()
        sc.cloud.service_model = self.d_cloud_service.currentText()
        sc.cloud.deploy_model = self.d_cloud_deploy.currentText()
        sc.cloud.provider_name = self.d_cloud_provider.text()
        sc.cloud.platform_level = self.d_cloud_plat_level.text()
        sc.cloud.platform_name = self.d_cloud_plat_name.text()
        sc.cloud.platform_code = self.d_cloud_plat_code.text()
        sc.cloud.client_ops_location = self.d_cloud_ops.text()
        sc.mobile.enabled = self.d_mobile_enabled.isChecked()
        sc.mobile.app_name = self.d_mobile_app.text()
        sc.mobile.wireless = self.d_mobile_wireless.currentText()
        sc.mobile.terminal = self.d_mobile_terminal.currentText()
        sc.iot.enabled = self.d_iot_enabled.isChecked()
        sc.iot.perception = self.d_iot_perception.text()
        sc.iot.transport = self.d_iot_transport.text()
        sc.ics.enabled = self.d_ics_enabled.isChecked()
        sc.ics.function_layer = self.d_ics_layer.text()
        sc.ics.composition = self.d_ics_comp.text()
        sc.bigdata.enabled = self.d_bigdata_enabled.isChecked()
        sc.bigdata.composition = self.d_bigdata_comp.text()
        sc.bigdata.cross_border = self.d_bigdata_cross.currentText()

        att = data.attachment
        for key, widgets in self.e_attachments.items():
            item = getattr(att, key)
            item.has_file = widgets["check"].isChecked()
            item.file_name = widgets["name"].text()

        d = data.data
        d.data_name = self.e_data_name.text()
        d.data_level = self.e_data_level.currentText()
        d.data_category = self.e_data_category.text()
        d.data_dept = self.e_data_dept.text()
        d.data_person = self.e_data_person.text()
        d.personal_info = self.e_personal_info.currentText()
        d.total_size = self.e_total_size.text()
        d.monthly_growth = self.e_monthly_growth.text()

        data.project_name = tgt.name or u.unit_name
        return data

    def collect_report(self):
        """从 GUI 收集定级报告数据"""
        from models.project_data import ReportInfo, SubSystem
        r = ReportInfo()
        r.responsibility = self.f_responsibility.toPlainText()
        r.composition = self.f_composition.toPlainText()
        r.topology_image = self.f_topology_path.text()
        r.business_desc = self.f_business.toPlainText()
        r.security_resp = self.f_security.toPlainText()
        r.biz_info_desc = self.f_biz_info.toPlainText()
        r.biz_victim = self.f_biz_victim.toPlainText()
        r.biz_degree = self.f_biz_degree.toPlainText()
        r.svc_desc = self.f_svc_desc.toPlainText()
        r.svc_victim = self.f_svc_victim.toPlainText()
        r.svc_degree = self.f_svc_degree.toPlainText()
        r.biz_level = self.c_biz_level.currentText()
        r.svc_level = self.c_svc_level.currentText()
        r.final_level = self.c_final_level.text()

        for row in range(self.f_subsystems.rowCount()):
            idx_item = self.f_subsystems.item(row, 0)
            name_item = self.f_subsystems.item(row, 1)
            desc_item = self.f_subsystems.item(row, 2)
            sub = SubSystem(
                index=idx_item.text() if idx_item else str(row + 1),
                name=name_item.text() if name_item else "",
                description=desc_item.text() if desc_item else ""
            )
            if sub.name:
                r.subsystems.append(sub)

        return r
