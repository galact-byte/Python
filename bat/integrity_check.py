#!/usr/bin/env python3
"""
开源代码完整性校验工具（支持 GitHub & Gitee）
对比本地文件夹与远程官方源码，检测文件篡改、缺失、新增情况。

使用方法：
    # GitHub 仓库
    python integrity_check.py --local D:/senta --repo PaddlePaddle/Senta --tag v1.0 --source github

    # Gitee 仓库
    python integrity_check.py --local D:/senta --repo paddlepaddle/senta --tag master --source gitee

    # Gitee 带 Token（提升限速）
    python integrity_check.py --local D:/senta --repo paddlepaddle/senta --source gitee --token 你的token

参数说明：
    --local    本地项目文件夹路径（必填）
    --repo     仓库，格式 owner/repo（必填）
    --source   来源平台: github 或 gitee（默认 github）
    --tag      版本 tag 或 branch（默认 master）
    --output   输出报告路径（默认 integrity_report.txt）
    --token    平台 Personal Access Token（可选，提升API限速上限）
    --ext      只检查指定扩展名，逗号分隔，如 .java,.xml,.yml（默认全部）
    --ignore   忽略的路径前缀，逗号分隔（默认忽略 .git,target,node_modules 等）
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib import request, error


# ── 颜色输出 ───────────────────────────────────────────────
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def green(s):  return f"\033[92m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"


# ── HTTP 工具 ──────────────────────────────────────────────
def http_get(url, headers, retries=3):
    req = request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with request.urlopen(req, timeout=30) as r:
                return json.loads(r.read()), dict(r.headers)
        except error.HTTPError as e:
            if e.code in (429, 403) and attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(yellow(f"  ⚠ API 限速，等待 {wait} 秒后重试 ({attempt+1}/{retries})..."))
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"请求失败: {url}")


# ── GitHub API ─────────────────────────────────────────────
class GitHubAPI:
    BASE = "https://api.github.com"

    def __init__(self, token=None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "integrity-checker/1.0",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get_tree(self, owner, repo, ref):
        url = f"{self.BASE}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
        print(f"  → 拉取 GitHub 文件树: {owner}/{repo}@{ref}")
        data, hdrs = http_get(url, self.headers)
        remaining = hdrs.get("X-Ratelimit-Remaining", "?")
        if data.get("truncated"):
            print(yellow("  ⚠ 文件树被截断（仓库过大），部分文件可能未被比对"))
        print(f"  → GitHub API 剩余请求次数: {remaining}")
        # 返回 {path: sha} 只含 blob
        return {
            item["path"]: item["sha"]
            for item in data.get("tree", [])
            if item["type"] == "blob"
        }

    def get_blob_content(self, owner, repo, file_sha):
        """通过 blob SHA 下载文件原始内容（用于差异原因分析）"""
        import base64
        url = f"{self.BASE}/repos/{owner}/{repo}/git/blobs/{file_sha}"
        data, _ = http_get(url, self.headers)
        return base64.b64decode(data["content"])


# ── Gitee API ──────────────────────────────────────────────
class GiteeAPI:
    BASE = "https://gitee.com/api/v5"

    def __init__(self, token=None):
        self.token = token
        self.headers = {"User-Agent": "integrity-checker/1.0"}

    def _list_dir(self, owner, repo, ref, path=""):
        """递归列出目录下所有文件，返回 {path: sha}"""
        token_param = f"&access_token={self.token}" if self.token else ""
        url = f"{self.BASE}/repos/{owner}/{repo}/contents/{path}?ref={ref}{token_param}"
        data, _ = http_get(url, self.headers)

        result = {}
        for item in data:
            if item["type"] == "file":
                result[item["path"]] = item["sha"]
            elif item["type"] == "dir":
                sub = self._list_dir(owner, repo, ref, item["path"])
                result.update(sub)
        return result

    def get_tree(self, owner, repo, ref):
        """
        Gitee 没有递归 tree API，用递归目录列举代替。
        注意：Gitee SHA 是文件内容的 git blob sha1，与 GitHub 一致。
        """
        print(f"  → 拉取 Gitee 文件树: {owner}/{repo}@{ref}")
        print(f"  → Gitee 采用递归目录遍历，文件较多时耗时较长，请耐心等待...")
        files = self._list_dir(owner, repo, ref)
        print(f"  → Gitee 共获取到 {len(files)} 个文件")
        return files  # {path: sha}

    def get_blob_content(self, owner, repo, file_sha):
        """通过 blob SHA 下载文件原始内容（用于差异原因分析）"""
        import base64
        token_param = f"?access_token={self.token}" if self.token else ""
        url = f"{self.BASE}/repos/{owner}/{repo}/git/blobs/{file_sha}{token_param}"
        data, _ = http_get(url, self.headers)
        return base64.b64decode(data["content"])


# ── Git Blob SHA1 计算 ─────────────────────────────────────
def git_blob_sha1(path: Path) -> str:
    """
    与 GitHub/Gitee tree API 中的 sha 字段完全一致。
    Git blob = sha1("blob {size}\0{content}")
    """
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    h = hashlib.sha1()
    h.update(header + data)
    return h.hexdigest()


# ── 本地文件扫描 ───────────────────────────────────────────
def scan_local(local_root: Path, ignore_prefixes: list, ext_filter: list) -> tuple:
    """返回 (sha_dict, size_dict, path_map)
       sha_dict:  {rel_path: git_blob_sha1}
       size_dict: {rel_path: file_size_bytes}
       path_map:  {rel_path: absolute_Path}
    """
    sha_dict  = {}
    size_dict = {}
    path_map  = {}
    for fpath in local_root.rglob("*"):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(local_root)
        rel_str = str(rel).replace(os.sep, "/")

        if any(rel_str == ig or rel_str.startswith(ig + "/") or rel.parts[0] == ig
               for ig in ignore_prefixes):
            continue

        if ext_filter and fpath.suffix.lower() not in ext_filter:
            continue

        try:
            sha_dict[rel_str]  = git_blob_sha1(fpath)
            size_dict[rel_str] = fpath.stat().st_size
            path_map[rel_str]  = fpath
        except (PermissionError, OSError):
            print(yellow(f"  ⚠ 无法读取: {rel_str}"))

    print(f"  → 本地共扫描到 {len(sha_dict)} 个文件")
    return sha_dict, size_dict, path_map


def _detect_diff_cause(local_path: Path, remote_content: bytes) -> str:
    """分析本地文件与远程内容差异的可能原因"""
    try:
        local_bytes = local_path.read_bytes()
    except OSError:
        return "无法读取本地文件"

    if len(local_bytes) != len(remote_content):
        size_diff = len(local_bytes) - len(remote_content)
        direction = "多" if size_diff > 0 else "少"
        hint = f"文件大小不同（本地比远程{direction} {abs(size_diff)} 字节）"
    else:
        hint = "文件大小相同但内容不同"

    # 检测行尾符差异：把 CRLF 统一成 LF 后再比
    local_norm   = local_bytes.replace(b"\r\n", b"\n")
    remote_norm  = remote_content.replace(b"\r\n", b"\n")
    if local_norm == remote_norm:
        return hint + " → 仅行尾符差异（CRLF↔LF），内容实质相同"

    # 检测编码差异：尝试 UTF-8 BOM
    local_strip  = local_bytes.lstrip(b"\xef\xbb\xbf")
    remote_strip = remote_content.lstrip(b"\xef\xbb\xbf")
    if local_strip.replace(b"\r\n", b"\n") == remote_strip.replace(b"\r\n", b"\n"):
        return hint + " → 仅 UTF-8 BOM / 行尾符差异，内容实质相同"

    return hint + " → 内容确实不同，建议手动比对"


# ── 比对逻辑 ───────────────────────────────────────────────
def compare(local_files: dict, local_sizes: dict, remote_files: dict, ext_filter: list) -> dict:
    if ext_filter:
        remote_files = {p: s for p, s in remote_files.items()
                        if Path(p).suffix.lower() in ext_filter}

    local_set  = set(local_files)
    remote_set = set(remote_files)
    common     = local_set & remote_set

    modified = sorted(p for p in common if local_files[p] != remote_files[p])
    modified_detail = {}
    for p in modified:
        modified_detail[p] = {
            "local":       local_files[p],
            "remote":      remote_files[p],
            "local_size":  local_sizes.get(p, -1),
        }

    return {
        "missing":         sorted(remote_set - local_set),
        "extra":           sorted(local_set  - remote_set),
        "modified":        modified,
        "modified_detail": modified_detail,
        "matched":         sorted(p for p in common if local_files[p] == remote_files[p]),
        "remote_total":    len(remote_files),
        "local_total":     len(local_files),
    }


# ── 报告输出 ───────────────────────────────────────────────
def print_report(result, repo, ref, source, local_path, output_file):
    lines = []

    def w(s=""):
        lines.append(s)
        print(s)

    platform = "GitHub" if source == "github" else "Gitee"
    w(bold("=" * 65))
    w(bold(f"  开源代码完整性校验报告（{platform}）"))
    w(bold("=" * 65))
    w(f"  平台         : {platform}")
    w(f"  仓库         : {repo}")
    w(f"  对比版本     : {ref}")
    w(f"  本地路径     : {local_path}")
    w(f"  {platform} 文件数: {result['remote_total']}")
    w(f"  本地文件数   : {result['local_total']}")
    w()

    total_issues = len(result["missing"]) + len(result["extra"]) + len(result["modified"])
    if total_issues == 0:
        risk = green("✅ 无异常 — 与官方源码完全一致")
    elif result["modified"]:
        risk = red(f"🔴 高风险 — 发现 {len(result['modified'])} 个文件内容被修改")
    elif result["extra"]:
        risk = yellow(f"🟡 中风险 — 发现 {len(result['extra'])} 个本地多余文件")
    else:
        risk = yellow(f"🟡 低风险 — 仅有文件缺失（{len(result['missing'])} 个）")

    w(bold("【综合风险判断】"))
    w(f"  {risk}")
    w()

    w(bold("【差异统计】"))
    w(f"  内容被修改  : {red(str(len(result['modified'])))} 个  ← 最高风险，重点审查")
    w(f"  本地多余文件: {yellow(str(len(result['extra'])))} 个  ← 可能注入或构建产物")
    w(f"  本地缺失文件: {yellow(str(len(result['missing'])))} 个  ← 可能被删除")
    w(f"  完全一致    : {green(str(len(result['matched'])))} 个")
    w()

    def section(title, items, color_fn, note=""):
        if not items:
            return
        w(bold(f"【{title}】") + (f"  {note}" if note else ""))
        for p in items:
            w(f"  {color_fn('●')} {p}")
        w()

    # 修改文件：展示 SHA 详情 + 大小 + 原因分析
    if result["modified"]:
        w(bold("【内容被修改的文件（SHA 不一致）】") + "  ← 可能存在后门或恶意代码")
        for p in result["modified"]:
            detail     = result["modified_detail"][p]
            local_sha  = detail["local"]
            remote_sha = detail["remote"]
            local_size = detail["local_size"]
            cause      = detail.get("cause", "—")
            w(f"  {red('●')} {p}")
            w(f"      本地 SHA1  : {local_sha}  (本地大小: {local_size} 字节)")
            w(f"      远程 SHA1  : {remote_sha}")
            w(f"      差异原因   : {cause}")
        w()
    section("本地多余文件（远程仓库中不存在）", result["extra"], yellow,
            "← 检查是否为构建产物或注入文件")
    section("本地缺失文件（远程仓库存在但本地没有）", result["missing"], yellow,
            "← 检查是否被删除")

    w(bold("=" * 65))
    w(f"  报告已保存至: {output_file}")
    w(bold("=" * 65))

    ansi_escape = re.compile(r"\033\[[0-9;]*m")
    plain = [ansi_escape.sub("", l) for l in lines]
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(plain))


# ── CLI ────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="开源代码完整性校验工具（支持 GitHub & Gitee）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--local",   required=True, help="本地项目文件夹路径")
    p.add_argument("--repo",    required=True, help="仓库，格式 owner/repo")
    p.add_argument("--source",  default="github", choices=["github", "gitee"],
                   help="平台: github 或 gitee（默认 github）")
    p.add_argument("--tag",     default="master", help="版本 tag 或 branch（默认 master）")
    p.add_argument("--output",  default="integrity_report.txt", help="报告输出路径")
    p.add_argument("--token",   default=None, help="平台 Personal Access Token（可选）")
    p.add_argument("--ext",     default=None, help="只检查指定扩展名，如 .java,.xml")
    p.add_argument("--ignore",  default=".git,target,node_modules,.idea,dist,logs,__pycache__",
                   help="忽略的路径前缀（逗号分隔）")
    p.add_argument("--analyze-diff", action="store_true",
                   help="对修改文件下载远程内容，分析具体差异原因（CRLF/BOM/真实篡改）")
    args = p.parse_args()

    local_path = Path(args.local).resolve()
    if not local_path.is_dir():
        print(red(f"错误: 本地路径不存在或不是文件夹: {local_path}"))
        sys.exit(1)

    # --repo 支持带 URL 的写法，自动提取 owner/repo
    repo_raw = args.repo
    m = re.search(r'(?:github\.com|gitee\.com)/([^/]+/[^/\s]+?)(?:\.git)?$', repo_raw)
    if m:
        repo_raw = m.group(1)
    owner, repo_name = repo_raw.split("/", 1)

    ext_filter      = [e.strip() for e in args.ext.split(",")]    if args.ext    else []
    ignore_prefixes = [i.strip() for i in args.ignore.split(",")]

    print()
    print(bold(cyan(f"=== 开源代码完整性校验工具（{args.source.upper()}）===")))
    print(f"  本地路径 : {local_path}")
    print(f"  仓库     : {owner}/{repo_name}@{args.tag}")
    print(f"  平台     : {args.source}")
    if ext_filter:
        print(f"  扩展名过滤: {ext_filter}")
    print(f"  忽略前缀 : {ignore_prefixes}")
    print()

    print(bold("[ Step 1/3 ] 扫描本地文件..."))
    local_files, local_sizes, path_map = scan_local(local_path, ignore_prefixes, ext_filter)
    print()

    print(bold("[ Step 2/3 ] 从远程仓库获取文件树..."))
    try:
        if args.source == "github":
            api = GitHubAPI(token=args.token)
        else:
            api = GiteeAPI(token=args.token)
        remote_files = api.get_tree(owner, repo_name, args.tag)
    except error.HTTPError as e:
        if e.code == 404:
            print(red(f"错误: 仓库或 tag 不存在 ({owner}/{repo_name}@{args.tag})"))
            print(yellow("提示: --repo 只需填 owner/repo，不要带 URL 前缀"))
        elif e.code in (401, 403):
            print(red("错误: 认证失败或 API 限速，请用 --token 传入 Access Token"))
        else:
            print(red(f"HTTP 错误: {e.code}"))
        sys.exit(1)
    print()

    print(bold("[ Step 3/3 ] 比对中..."))
    result = compare(local_files, local_sizes, remote_files, ext_filter)

    # 可选：下载远程内容分析差异原因
    if args.analyze_diff and result["modified"]:
        print(f"  → 分析 {len(result['modified'])} 个修改文件的差异原因...")
        for i, file_path in enumerate(result["modified"], 1):
            print(f"    ({i}/{len(result['modified'])}) {file_path}")
            try:
                remote_content = api.get_blob_content(owner, repo_name,
                                                       remote_files[file_path])
                cause = _detect_diff_cause(path_map[file_path], remote_content)
            except Exception as ex:
                cause = f"分析失败: {ex}"
            result["modified_detail"][file_path]["cause"] = cause
        print()
    else:
        # 没有 --analyze-diff 时给通用提示
        for file_path in result["modified"]:
            result["modified_detail"][file_path]["cause"] = \
                "未分析（加 --analyze-diff 参数可自动判断 CRLF/BOM/真实篡改）"
    print()

    print_report(result, f"{owner}/{repo_name}", args.tag, args.source,
                 str(local_path), args.output)


if __name__ == "__main__":
    main()
