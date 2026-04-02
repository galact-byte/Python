"""等保项目数据模型"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContactInfo:
    """联系人信息"""
    name: str = ""
    title: str = ""          # 职务/职称
    office_phone: str = ""
    mobile: str = ""
    email: str = ""


@dataclass
class UnitInfo:
    """单位信息（备案表 表2）"""
    unit_name: str = ""                    # 单位名称
    credit_code: str = ""                  # 统一社会信用代码
    province: str = ""                     # 省
    city: str = ""                         # 市
    county: str = ""                       # 县
    address: str = ""                      # 详细地址
    postal_code: str = ""                  # 邮政编码
    admin_code: str = ""                   # 行政区划代码
    leader: ContactInfo = field(default_factory=ContactInfo)          # 单位负责人
    security_dept: str = ""                # 网络安全责任部门
    security_contact: ContactInfo = field(default_factory=ContactInfo)  # 安全责任部门联系人
    data_dept: str = ""                    # 数据安全管理部门
    data_contact: ContactInfo = field(default_factory=ContactInfo)    # 数据安全联系人
    affiliation: str = ""                  # 隶属关系 (1-4,9)
    unit_type: str = ""                    # 单位类型 (1-4,9)
    industry: str = ""                     # 行业类别
    # 本次备案定级对象数量
    current_total: str = ""
    current_level2: str = ""
    current_level3: str = ""
    current_level4: str = ""
    current_level5: str = ""
    # 定级对象总数（含本次）
    all_total: str = ""
    all_level1: str = ""
    all_level2: str = ""
    all_level3: str = ""
    all_level4: str = ""
    all_level5: str = ""


@dataclass
class TargetInfo:
    """定级对象信息（备案表 表3）"""
    name: str = ""                     # 定级对象名称
    code: str = ""                     # 定级对象编号
    target_type: str = ""              # 类型（通信网络设施/信息系统/数据资源）
    tech_type: str = ""                # 采用技术（云计算/移动互联/物联网/工控/大数据）
    biz_type: str = ""                 # 业务类型
    biz_type_other: str = ""           # 业务类型其他说明
    biz_desc: str = ""                 # 业务描述
    service_scope: str = ""            # 服务范围
    service_scope_other: str = ""      # 服务范围其他说明
    service_target: str = ""           # 服务对象
    service_target_other: str = ""     # 服务对象其他说明
    deploy_scope: str = ""             # 部署范围
    deploy_scope_other: str = ""       # 部署范围其他说明
    network_type: str = ""             # 网络性质
    network_type_other: str = ""       # 网络性质其他说明
    source_ip: str = ""                # 源站IP
    domain: str = ""                   # 域名
    protocol_port: str = ""            # 协议/端口
    interconnect: str = ""             # 网络互联情况
    interconnect_other: str = ""       # 网络互联情况其他说明
    run_date: str = ""                 # 投入运行时间
    is_subsystem: str = ""             # 是否分系统
    parent_system: str = ""            # 上级系统名称
    parent_unit: str = ""              # 上级系统所属单位


@dataclass
class GradingInfo:
    """定级等级信息（备案表 表4）"""
    biz_level: str = "第二级"           # 业务信息安全保护等级
    biz_level_items: list = field(default_factory=list)  # 业务信息等级对应勾选项
    service_level: str = "第二级"       # 系统服务安全保护等级
    service_level_items: list = field(default_factory=list)  # 系统服务等级对应勾选项
    final_level: str = "第二级"         # 最终安全保护等级
    grading_date: str = ""             # 定级时间
    has_report: bool = True            # 有定级报告
    report_name: str = ""              # 定级报告附件名称
    has_review: bool = True            # 已评审
    review_name: str = ""              # 评审附件名称
    has_supervisor: bool = False       # 有上级行业主管部门
    supervisor_name: str = ""          # 主管部门名称
    supervisor_reviewed: bool = False  # 主管部门已审核
    supervisor_review_status: str = "未审核"  # 上级主管部门审核状态
    supervisor_doc: str = ""           # 审核附件
    filler: str = ""                   # 填表人
    fill_date: str = ""                # 填表日期


@dataclass
class CloudInfo:
    """云计算应用场景补充"""
    enabled: bool = False
    role: str = ""                     # 云服务商/云服务客户
    service_model: str = ""            # IaaS/PaaS/SaaS
    service_model_other: str = ""      # 服务模式其他说明
    deploy_model: str = ""             # 私有云/公有云/混合云
    deploy_model_other: str = ""       # 部署模式其他说明
    provider_scale: str = ""           # 云服务客户数量
    infra_location: str = ""           # 基础设施地点
    ops_location: str = ""             # 运维地点
    provider_preset: str = ""          # 预置服务商/机房字典键
    provider_kind: str = ""            # 云服务商/第三方托管机房/手动填写
    provider_name: str = ""            # 云服务商名称
    platform_level: str = ""           # 平台安全等级
    platform_name: str = ""            # 平台名称
    platform_code: str = ""            # 平台备案编号
    client_ops_location: str = ""      # 客户运维地点
    platform_cert: str = ""            # 备案证明附件


@dataclass
class MobileInfo:
    """移动互联应用场景补充"""
    enabled: bool = False
    app_name: str = ""
    wireless: str = ""                 # 公共WIFI/专用WIFI/移动通信网
    terminal: str = ""                 # 通用终端/专用终端


@dataclass
class IoTInfo:
    """物联网应用场景补充"""
    enabled: bool = False
    perception: str = ""               # 感知层
    transport: str = ""                # 传输层


@dataclass
class ICSInfo:
    """工业控制系统应用场景补充"""
    enabled: bool = False
    function_layer: str = ""           # 功能层次
    composition: str = ""              # 系统组成


@dataclass
class BigDataInfo:
    """大数据应用场景补充"""
    enabled: bool = False
    composition: str = ""              # 系统组成
    cross_border: str = ""             # 出境情况
    platform_scale: str = ""
    platform_infra: str = ""
    platform_ops: str = ""
    platform_provider: str = ""
    platform_level: str = ""
    platform_name: str = ""
    platform_code: str = ""
    platform_cert: str = ""


@dataclass
class ScenarioInfo:
    """应用场景补充信息（备案表 表5）"""
    cloud: CloudInfo = field(default_factory=CloudInfo)
    mobile: MobileInfo = field(default_factory=MobileInfo)
    iot: IoTInfo = field(default_factory=IoTInfo)
    ics: ICSInfo = field(default_factory=ICSInfo)
    bigdata: BigDataInfo = field(default_factory=BigDataInfo)


@dataclass
class AttachmentItem:
    """附件项"""
    has_file: bool = False
    file_name: str = ""


@dataclass
class AttachmentInfo:
    """附件清单（备案表 表6）"""
    topology: AttachmentItem = field(default_factory=AttachmentItem)      # 网络拓扑结构及说明
    org_policy: AttachmentItem = field(default_factory=AttachmentItem)    # 安全组织架构及管理制度
    design_plan: AttachmentItem = field(default_factory=AttachmentItem)   # 安全建设/整改方案
    product_list: AttachmentItem = field(default_factory=AttachmentItem)  # 安全产品清单及证书
    service_list: AttachmentItem = field(default_factory=AttachmentItem)  # 安全服务清单
    supervisor_doc: AttachmentItem = field(default_factory=AttachmentItem)  # 主管部门定级文件


@dataclass
class DataInfo:
    """数据信息（备案表 表7）"""
    data_name: str = ""                # 数据名称
    data_level: str = ""               # 拟定数据级别
    data_category: str = ""            # 数据类别
    data_dept: str = ""                # 数据安全责任部门
    data_person: str = ""              # 数据安全负责人
    personal_info: str = ""            # 个人信息涉及情况
    total_size: str = ""               # 数据总量
    total_size_unit: str = "GB"        # 数据总量单位
    total_size_tb: str = ""            # 数据总量TB
    total_size_records: str = ""       # 数据总量万条
    monthly_growth: str = ""           # 月增长量
    monthly_growth_unit: str = "GB"    # 月增长量单位
    monthly_growth_tb: str = ""        # 月增长量TB
    data_source: str = ""              # 数据来源
    data_source_other: str = ""        # 数据来源其他说明
    inflow_units: str = ""             # 数据来源单位
    outflow_units: str = ""            # 数据流出单位
    interaction: str = ""              # 与其他处理者交互
    interaction_other: str = ""        # 与其他处理者交互其他说明
    storage_type: str = ""             # 存储位置类型主分类
    storage_cloud: str = ""            # 云存储位置
    storage_cloud_name: str = ""       # 云存储位置名称
    storage_room: str = ""             # 机房存储位置
    storage_room_name: str = ""        # 机房存储位置名称
    storage_region: str = ""           # 境内/境外
    storage_region_name: str = ""      # 区域位置名称


@dataclass
class SubSystem:
    """子系统"""
    index: str = ""
    name: str = ""
    description: str = ""


@dataclass
class ReportInfo:
    """定级报告内容"""
    system_name: str = ""              # 定级对象名称（标题用）
    responsibility: str = ""           # 责任主体描述
    composition: str = ""              # 定级对象构成描述
    topology_image: str = ""           # 网络拓扑图文件路径
    business_desc: str = ""            # 承载业务描述
    security_resp: str = ""            # 安全责任描述
    subsystems: list = field(default_factory=list)  # 子系统列表 [SubSystem]
    # 业务信息安全等级确定
    biz_info_desc: str = ""            # 业务信息描述
    biz_victim: str = ""               # 侵害客体
    biz_degree: str = ""               # 侵害程度
    biz_level: str = "第二级"
    # 系统服务安全等级确定
    svc_desc: str = ""                 # 系统服务描述
    svc_victim: str = ""               # 侵害客体
    svc_degree: str = ""               # 侵害程度
    svc_level: str = "第二级"
    final_level: str = "第二级"


@dataclass
class ProjectData:
    """项目完整数据"""
    project_name: str = ""             # 项目名称
    unit: UnitInfo = field(default_factory=UnitInfo)
    target: TargetInfo = field(default_factory=TargetInfo)
    grading: GradingInfo = field(default_factory=GradingInfo)
    scenario: ScenarioInfo = field(default_factory=ScenarioInfo)
    attachment: AttachmentInfo = field(default_factory=AttachmentInfo)
    data: DataInfo = field(default_factory=DataInfo)
    report: ReportInfo = field(default_factory=ReportInfo)
