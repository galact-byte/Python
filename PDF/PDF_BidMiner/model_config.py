"""模型配置和运行时下线公告检查。"""

import datetime
import json
import math
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

import requests


DEFAULTS = {
    "text_model": "qwen-flash",
    "vision_model": "qwen3-vl-plus",
    "text_fallbacks": ["qwen-plus"],
    "vision_fallbacks": [],
    "check_interval_days": 15,
}
MODEL_NAME = re.compile(r"[a-z][a-z0-9.-]{0,99}")
NOTICE_URL = re.compile(r"https://www\.aliyun\.com/notice/\d+")
NOTICE_INDEX_URL = "https://help.aliyun.com/zh/model-studio/model-depreciation"
REQUEST_TIMEOUT = (3, 5)


class _NoticeHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.rows, self.blocks, self.text = [], [], [], []
        self.dated_links = []
        self._section_date = None
        self._heading = None
        self._row = self._cell = self._block = None
        self._block_tag = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)
                    self.dated_links.append((value, self._section_date))
        if tag in ("h1", "h2", "h3", "h4"):
            self._heading = []
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in ("p", "li") and self._row is None and self._block is None:
            self._block, self._block_tag = [], tag

    def handle_data(self, data):
        self.text.append(data)
        if self._heading is not None:
            self._heading.append(data)
        if self._cell is not None:
            self._cell.append(data)
        if self._block is not None:
            self._block.append(data)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4") and self._heading is not None:
            match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", "".join(self._heading))
            if match:
                self._section_date = datetime.date(*(int(value) for value in match.groups()))
            self._heading = None
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        if tag == self._block_tag and self._block is not None:
            self.blocks.append(" ".join(self._block).strip())
            self._block, self._block_tag = None, ""


def _download(url: str, **kwargs):
    response = requests.get(
        url, timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BidMiner)", "Referer": "https://www.aliyun.com/notice/"},
        **kwargs,
    )
    response.raise_for_status()
    if len(response.content) > 2_000_000:
        raise ValueError("官方公告响应超出大小限制")
    response.encoding = "utf-8"
    return response


def _read_notice(url: str) -> dict:
    payload = _download(
        "https://t.aliyun.com/abs/bulletin/bulletinDetail",
        params={"id": url.rsplit("/", 1)[1], "language": "zh", "website": "cn"},
    ).json()
    if payload.get("success") is not True or payload.get("data", {}).get("success") is not True:
        raise ValueError("官方公告接口未返回成功结果")
    info = payload["data"]["info"]
    if "下线" not in info["title"]:
        raise ValueError("官方下线公告标题发生变化")
    body = next(detail["contentHtml"] for detail in info["detailList"] if detail.get("language") == "zh")
    parser = _NoticeHTML()
    parser.feed(body)
    notices = {}
    replacement_column = None
    for row in parser.rows:
        for index, cell in enumerate(row):
            if "模型" in cell and ("推荐" in cell or "替换" in cell):
                replacement_column = index
        if row and MODEL_NAME.fullmatch(row[0]):
            replacement = row[replacement_column] if replacement_column is not None and replacement_column < len(row) else ""
            notices[row[0]] = {"replacement": replacement if MODEL_NAME.fullmatch(replacement) else "", "source": url}
    for block in parser.blocks:
        names = block.split()
        if names and all(MODEL_NAME.fullmatch(name) for name in names):
            for name in names:
                notices[name] = {"replacement": "", "source": url}
        for match in re.finditer(
            r"(?<![a-z0-9.-])([a-z][a-z0-9.-]+)模型(?:进行|将)?下线", block
        ):
            notices[match[1]] = {"replacement": "", "source": url}
    if not notices:
        raise ValueError(f"公告格式无法识别：{url}")
    return notices


def _fetch_notices() -> dict:
    parser = _NoticeHTML()
    parser.feed(_download(NOTICE_INDEX_URL).text)
    today = datetime.date.today()
    completed_batches = [date for url, date in parser.dated_links if NOTICE_URL.fullmatch(url) and date is not None and date <= today]
    latest_batch = max(completed_batches, default=today)
    links = list(dict.fromkeys(
        url for url, date in parser.dated_links
        if NOTICE_URL.fullmatch(url) and (date is None or date >= latest_batch)
    ))
    if "下线模型列表" not in "".join(parser.text) or not 1 <= len(links) <= 32:
        raise ValueError("官方下线列表结构发生变化")
    notices = {}
    # 该接口来自官网公告页面；若接口或页面结构变更，整个检查按失败处理。
    with ThreadPoolExecutor(max_workers=4) as executor:
        for result in executor.map(_read_notice, links):
            for name, notice in result.items():
                notices.setdefault(name, notice)
    return notices


def _save_json(path: Path, data: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def configure_models(config_path: Path, cache_path: Path) -> dict:
    settings = dict(DEFAULTS)
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("model_config.json 必须是 JSON 对象")
        settings.update(data)
    for field in ("text_model", "vision_model"):
        if not isinstance(settings[field], str) or not MODEL_NAME.fullmatch(settings[field]):
            raise ValueError(f"model_config.json 中的 {field} 不是有效模型名称")
    for field in ("text_fallbacks", "vision_fallbacks"):
        values = settings[field]
        if not isinstance(values, list) or len(values) > 10 or any(
            not isinstance(value, str) or not MODEL_NAME.fullmatch(value) for value in values
        ):
            raise ValueError(f"model_config.json 中的 {field} 必须是模型名称列表，最多 10 个")
    interval = settings["check_interval_days"]
    if type(interval) is not int or not 1 <= interval <= 365:
        raise ValueError("check_interval_days 必须是 1 到 365 的整数")
    notices = None
    refreshed = False
    previous_notices = {}
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        checked_at = cache["checked_at"]
        age = time.time() - checked_at
        valid_notices = isinstance(cache["notices"], dict) and all(
            isinstance(name, str) and MODEL_NAME.fullmatch(name)
            and isinstance(notice, dict)
            and isinstance(notice.get("replacement"), str)
            and (not notice["replacement"] or MODEL_NAME.fullmatch(notice["replacement"]))
            and isinstance(notice.get("source"), str) and NOTICE_URL.fullmatch(notice["source"])
            for name, notice in cache["notices"].items()
        )
        if cache["version"] == 1 and valid_notices:
            previous_notices = cache["notices"]
        if cache["version"] == 1 and type(checked_at) in (int, float) and math.isfinite(checked_at) and 0 <= age < interval * 86400 and valid_notices:
            print("模型下线公告检查尚未到期，使用本地记录。")
            notices = cache["notices"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if notices is None:
        print("正在检查阿里云当前及未来批次的模型下线公告...")
        try:
            notices = {**previous_notices, **_fetch_notices()}
            refreshed = True
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, StopIteration) as error:
            print(f"[提示] 模型公告检查未完成（{type(error).__name__}），保留已知公告记录，下次启动重试。")
            print(f"  可人工核对：{NOTICE_INDEX_URL}")
            notices = previous_notices
            if not notices:
                return settings
        try:
            if refreshed:
                _save_json(cache_path, {"version": 1, "checked_at": time.time(), "notices": notices})
        except OSError:
            print("[提示] 检查记录无法保存，下次启动会重新检查。")
        if refreshed:
            print(f"模型公告检查完成，下次联网检查间隔 {interval} 天。")
    changed = False
    for field, fallbacks in (("text_model", "text_fallbacks"), ("vision_model", "vision_fallbacks")):
        current = settings[field]
        if current not in notices:
            continue
        notice = notices[current]
        print(f"[提示] {current} 已列入官方下线名单：{notice['source']}")
        allowed = settings[fallbacks]
        candidates = ([notice["replacement"]] if notice["replacement"] in allowed else []) + allowed
        replacement = next((name for name in candidates if name not in notices and name != current), None)
        if replacement:
            settings[field] = replacement
            changed = True
            print(f"  已切换到配置允许的候选模型：{replacement}；请核对本次提取结果。")
        else:
            recommendation = notice["replacement"] or "请查看上述官方公告"
            print(f"  没有可自动替换的候选，保留当前型号。官方替代建议：{recommendation}")
            label = "文本模型（文字型 PDF）" if field == "text_model" else "视觉模型（图片型 PDF）"
            print(f"  请自行更换{label}，操作步骤：")
            print(f"  1. 右键打开配置文件 → 打开方式 → 记事本：{config_path.resolve()}")
            print(f'  2. 找到 "{field}"，只修改它右边双引号内的型号（当前为 "{current}"）。')
            if notice["replacement"]:
                print(f'     官方建议的填写值为 "{notice["replacement"]}"；请先在百炼确认用途、接口、费用和账号是否可用。')
            else:
                print("     打开上方官方公告查看替代建议，再到百炼模型广场选择支持当前用途和接口的型号，复制模型 ID。")
            print("     文字型 PDF 需要文本生成模型；图片型 PDF 需要支持图片输入的视觉模型。")
            print("  3. 保留英文双引号、逗号及其他配置，按 Ctrl+S 保存后关闭记事本。")
            print("  4. 当前运行仍使用原型号；关闭程序窗口，再双击 run.bat，新型号即会生效。")
            print("     详细示例见 README.md 的“自行更换模型”一节；请先用一份 PDF 核对提取结果。")
    if changed:
        try:
            _save_json(config_path, settings)
        except OSError:
            print("[提示] 模型配置无法保存，本次切换仅对当前运行生效。")
    return settings
