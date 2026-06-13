#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频 BGM 配乐合成工具 —— 核心引擎

用途：把一个"短视频"里的 BGM（音乐音轨）干净地循环铺到一个"长视频"上，
      同时保留长视频的人声（音乐为主、人声清晰），输出新视频，原文件不动。

适用场景：长视频 = 短视频基础上增加了些内容（更长、有人声无BGM），
          短视频 = 带高质量 BGM（人声少/无）。

核心技术（从大量实测沉淀）：
  1. 音源取短视频原生音轨（通常比单独下载的 mp3 码率更高），最终编码 256k，不重采样。
  2. 循环接缝只落在歌曲的"真静音"处（段落边界 / 歌曲结尾的大静默），
     绝不在人声句子中间 crossfade —— 否则会出现两段人声重叠的违和感。
  3. 软前奏只在开头播一次，后续循环从"强拍"进入（避免循环回到软弱前奏）。
  4. 可选：在静音里干净跳过安静间奏（bridge），让新增内容也压得住音乐。
  5. 留白区（开场/中段对白）不放 BGM，只留人声。
  6. 人声闪避（sidechaincompress）：人声出现时音乐轻微下压，人声停止恢复。
  7. 两步渲染（先合成小音频，再 copy 复用视频流）—— 快且抗 IO 卡顿。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe 定位
# ---------------------------------------------------------------------------
def find_tool(name):
    """在 PATH 及常见 Windows 安装位置查找 ffmpeg/ffprobe。"""
    p = shutil.which(name)
    if p:
        return p
    candidates = [
        rf"D:\Software\ffmpeg\bin\{name}.exe",
        rf"C:\ffmpeg\bin\{name}.exe",
        rf"C:\Program Files\ffmpeg\bin\{name}.exe",
        rf"D:\ffmpeg\bin\{name}.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def _check_tools():
    if not FFMPEG or not FFPROBE:
        raise RuntimeError(
            "未找到 ffmpeg/ffprobe，请先安装并加入 PATH（或放到 D:\\Software\\ffmpeg\\bin）。"
        )


def run(cmd):
    """执行命令（列表形式，避免中文/空格路径转义问题），返回 (returncode, stdout, stderr)。"""
    proc = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


# ---------------------------------------------------------------------------
# 基础探测
# ---------------------------------------------------------------------------
def probe_duration(path):
    code, out, err = run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path]
    )
    try:
        return float(out.strip())
    except ValueError:
        raise RuntimeError(f"无法读取时长: {path}\n{err}")


def probe_audio_bitrate(path):
    code, out, err = run(
        [FFPROBE, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=bit_rate", "-of", "default=nw=1:nk=1", path]
    )
    try:
        return int(out.strip())
    except ValueError:
        return 0


def detect_silences(audio, noise_db, min_d):
    """返回 [(start, end), ...] —— 低于 noise_db 且持续 >= min_d 的静音段。"""
    code, out, err = run(
        [FFMPEG, "-hide_banner", "-nostats", "-vn", "-i", audio,
         "-af", f"silencedetect=noise={noise_db}dB:d={min_d}", "-f", "null", "-"]
    )
    text = out + "\n" + err
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", text)]
    pairs = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        if e is not None and e > s:
            pairs.append((s, e))
    return pairs


def window_db(audio, start, dur):
    """测某窗口的平均音量 (dB)，用于判断强拍/软前奏。"""
    code, out, err = run(
        [FFMPEG, "-hide_banner", "-nostats", "-ss", str(start), "-t", str(dur),
         "-i", audio, "-af", "volumedetect", "-f", "null", "-"]
    )
    m = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", out + err)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 时间解析
# ---------------------------------------------------------------------------
def parse_time(s):
    """'23' / '4:35' / '1:02:03' / '275.5' -> 秒(float)。"""
    s = str(s).strip()
    if not s:
        raise ValueError("空时间")
    if ":" in s:
        parts = s.split(":")
        sec = 0.0
        for p in parts:
            sec = sec * 60 + float(p)
        return sec
    return float(s)


def parse_zone_list(s):
    """'0-23,4:35-4:54' -> [[0,23],[275,294]]。"""
    zones = []
    s = s.strip()
    if not s:
        return zones
    for chunk in s.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" not in chunk:
            raise ValueError(f"留白段格式错误（应为 起-止）: {chunk}")
        a, b = chunk.split("-", 1)
        zones.append([parse_time(a), parse_time(b)])
    return zones


def r(x):
    return round(float(x), 3)


# ---------------------------------------------------------------------------
# BGM 结构分析
# ---------------------------------------------------------------------------
def analyze_bgm(short_audio):
    """自动探测：时长 / 歌曲起点 / 歌曲结尾(最长静音) / 循环强拍点 / 内部静音列表。"""
    dur = probe_duration(short_audio)
    sil30 = detect_silences(short_audio, -30, 0.3)

    # 歌曲起点：若开头就是真静音则取其结束，否则 0（多数短视频音乐从 0 开始）
    song_start = 0.0
    if sil30 and sil30[0][0] <= 0.5:
        song_start = sil30[0][1]

    # 歌曲结尾：取后半段中最长的静音作为天然循环边界，否则取总时长
    song_end = dur
    best = None
    for s, e in sil30:
        if s > dur * 0.5 and (e - s) >= 1.0:
            if best is None or (e - s) > (best[1] - best[0]):
                best = (s, e)
    if best:
        song_end = best[0]

    # 循环强拍点：用 -16dB 静音检测找开头那段"偏弱"的前奏，其结束即强拍进入点
    loop_start = song_start
    sil16 = detect_silences(short_audio, -16, 0.4)
    for s, e in sil16:
        if e <= song_start + 0.2:
            continue
        if s <= song_start + 0.5 and e <= song_start + 45:
            loop_start = e
        break

    return {
        "duration": round(dur, 3),
        "song_start": round(song_start, 3),
        "song_end": round(song_end, 3),
        "loop_start": round(loop_start, 3),
        "silences": [(round(s, 2), round(e, 2)) for s, e in sil30],
    }


def print_analysis(info, short_audio=None):
    print("\n  ── BGM 结构分析 ──")
    print(f"  音源时长      : {info['duration']}s")
    print(f"  歌曲起点      : {info['song_start']}s  (含软前奏)")
    print(f"  强拍进入点    : {info['loop_start']}s  (循环从这里进)")
    print(f"  歌曲天然结尾  : {info['song_end']}s  (循环边界=此处大静音)")
    if info.get("silences"):
        sl = ", ".join(f"{s}~{e}" for s, e in info["silences"][:12])
        print(f"  内部静音点    : {sl}")
        print("                  (可在这些静音里干净跳过间奏，填 skip_ranges)")
    if short_audio:
        pts = [info["song_start"], info["loop_start"],
               (info["song_start"] + info["loop_start"]) / 2 + 8]
        es = []
        for t in pts:
            db = window_db(short_audio, t, 2)
            es.append(f"{round(t,1)}s={db}dB")
        print(f"  能量采样      : {', '.join(es)}")
    print()


# ---------------------------------------------------------------------------
# 段落 / 拼接规划
# ---------------------------------------------------------------------------
def build_segments(zones, dur):
    """留白区的补集 = BGM 段。返回 [(start,end), ...]。"""
    zs = sorted([[max(0.0, a), min(dur, b)] for a, b in zones])
    segs = []
    cur = 0.0
    for a, b in zs:
        if a > cur + 0.05:
            segs.append((cur, a))
        cur = max(cur, b)
    if cur < dur - 0.05:
        segs.append((cur, dur))
    return segs


def pieces_from(p, song_end, skips):
    """从歌曲位置 p 播到 song_end，跳过 skips（须落在静音里），返回 [(a,b), ...]。"""
    segs = []
    cur = p
    for s, e in sorted(skips):
        if e <= cur:
            continue
        if s <= cur:
            cur = max(cur, e)
            continue
        if s >= song_end:
            break
        segs.append((cur, s))
        cur = e
    if cur < song_end:
        segs.append((cur, song_end))
    return segs


def plan_segment(anchor, L, song_end, loop_start, skips, skip_seam, loop_seam):
    """
    规划一个 BGM 段：从 anchor 起播到歌尾，不够长就从 loop_start 循环续接，
    直到总时长 >= L。返回 (flat_pieces, seam_durs)。
    seam_durs[k] = flat[k] 与 flat[k+1] 之间的 crossfade 时长。
    """
    flat = []
    seams = []
    assembled = 0.0
    first = True
    guard = 0
    while True:
        guard += 1
        if guard > 60:
            break
        p = anchor if first else loop_start
        pcs = pieces_from(p, song_end, skips)
        if not pcs:
            break
        for pi, (a, b) in enumerate(pcs):
            if flat:
                seams.append(loop_seam if pi == 0 else skip_seam)
            flat.append((a, b))
        run_len = sum(b - a for a, b in pcs) - skip_seam * (len(pcs) - 1)
        if not first:
            assembled -= loop_seam
        assembled += run_len
        first = False
        if assembled >= L:
            break
    return flat, seams


def resolve_anchor(idx, ss, params):
    """决定某 BGM 段从歌曲哪个位置起播。"""
    for a in params.get("anchors", []) or []:
        if abs(float(a["long_time"]) - ss) <= 1.5:
            sp = a["song_pos"]
            if sp == "start":
                return params["song_start"]
            if sp in ("strong", "loop"):
                return params["loop_start"]
            return float(sp)
    if idx == 0 and params.get("intro_once", True):
        return params["song_start"]
    return params["loop_start"]


# ---------------------------------------------------------------------------
# filter_complex 生成
# ---------------------------------------------------------------------------
def build_filter(params):
    dur = params["duration"]
    song_end = params["song_end"]
    loop_start = params["loop_start"]
    skips = params.get("skip_ranges", []) or []
    skip_seam = params.get("skip_seam", 0.8)
    loop_seam = params.get("loop_seam", 0.4)
    fade_in = params.get("fade_in", 1.5)
    fade_out = params.get("fade_out", 4.0)

    segs = build_segments(params.get("silence_zones", []) or [], dur)
    if not segs:
        raise RuntimeError("没有可放 BGM 的时间段（留白覆盖了整段？）")

    # pass1: 规划每段、统计总片段数
    seg_plans = []
    total_pieces = 0
    for i, (ss, se) in enumerate(segs):
        L = se - ss
        anchor = resolve_anchor(i, ss, params)
        flat, seams = plan_segment(anchor, L, song_end, loop_start,
                                   skips, skip_seam, loop_seam)
        seg_plans.append({"i": i, "ss": ss, "se": se, "L": L,
                          "flat": flat, "seams": seams})
        total_pieces += len(flat)

    lines = []
    # [0:a] 拆分为 total_pieces 路
    if total_pieces == 1:
        src_labels = ["0:a"]
    else:
        src_labels = [f"sp{k}" for k in range(total_pieces)]
        lines.append("[0:a]asplit=%d%s" %
                     (total_pieces, "".join(f"[{l}]" for l in src_labels)))

    gp = 0
    bgm_labels = []
    for seg in seg_plans:
        labels = []
        for (a, b) in seg["flat"]:
            lbl = f"pc{gp}"
            lines.append(
                f"[{src_labels[gp]}]atrim={r(a)}:{r(b)},"
                f"asetpts=PTS-STARTPTS[{lbl}]"
            )
            labels.append(lbl)
            gp += 1
        # crossfade 链
        if len(labels) == 1:
            cur = labels[0]
        else:
            cur = labels[0]
            for k in range(1, len(labels)):
                nl = f"x{seg['i']}_{k}"
                lines.append(
                    f"[{cur}][{labels[k]}]"
                    f"acrossfade=d={seg['seams'][k-1]}:c1=qsin:c2=qsin[{nl}]"
                )
                cur = nl
        # 裁剪到段长 + 淡入 +（如后接留白）淡出 + 延迟到位
        post = f"atrim=0:{r(seg['L'])},asetpts=PTS-STARTPTS,afade=t=in:d={fade_in}"
        if seg["se"] < dur - 0.01:  # 后面还有留白
            st = max(0.0, seg["L"] - fade_out)
            post += f",afade=t=out:st={r(st)}:d={fade_out}"
        if seg["ss"] > 0.001:
            post += f",adelay={int(round(seg['ss']*1000))}:all=1"
        blab = f"bgm{seg['i']}"
        lines.append(f"[{cur}]{post}[{blab}]")
        bgm_labels.append(blab)

    # 汇总 BGM 轨
    if len(bgm_labels) == 1:
        bgmtrack = bgm_labels[0]
    else:
        bgmtrack = "bgmmix"
        lines.append("%samix=inputs=%d:normalize=0[%s]" %
                     ("".join(f"[{b}]" for b in bgm_labels),
                      len(bgm_labels), bgmtrack))

    bgm_vol = params.get("bgm_volume", 0.85)
    voice_vol = params.get("voice_volume", 0.6)
    dratio = params.get("duck_ratio", 1.8)
    dthr = params.get("duck_threshold", 0.05)

    lines.append(f"[{bgmtrack}]volume={bgm_vol}[bgmlvl]")
    lines.append("[1:a]asplit=2[vmain][vsc]")
    lines.append(f"[vmain]volume={voice_vol}[vmainq]")
    lines.append(
        f"[bgmlvl][vsc]sidechaincompress=threshold={dthr}:ratio={dratio}:"
        f"attack=15:release=500[bgmduck]"
    )
    lines.append("[vmainq][bgmduck]amix=inputs=2:normalize=0:duration=first[mix]")
    lines.append(
        f"[mix]afade=t=out:st={r(max(0, dur-2))}:d=2,alimiter=limit=0.97[aout]"
    )

    return ";".join(lines), segs, seg_plans


# ---------------------------------------------------------------------------
# 抽音轨 / 合成 / 复用
# ---------------------------------------------------------------------------
def extract_audio(video, out_path):
    """优先 copy（无损快），失败则转 aac。"""
    code, o, e = run([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", video,
                      "-vn", "-c:a", "copy", out_path])
    if code != 0 or not os.path.isfile(out_path):
        code, o, e = run([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", video,
                          "-vn", "-c:a", "aac", "-b:a", "256k", out_path])
        if code != 0:
            raise RuntimeError(f"抽取音轨失败: {video}\n{e[-800:]}")
    return out_path


def synth_audio(short_audio, long_audio, filter_complex, out_audio, bitrate):
    code, o, e = run([
        FFMPEG, "-y", "-hide_banner", "-nostats",
        "-i", short_audio, "-i", long_audio,
        "-filter_complex", filter_complex,
        "-map", "[aout]", "-c:a", "aac", "-b:a", bitrate, out_audio,
    ])
    if code != 0 or not os.path.isfile(out_audio):
        raise RuntimeError(f"合成音频失败:\n{e[-1500:]}")
    return out_audio


def mux(long_video, audio, out_video):
    code, o, e = run([
        FFMPEG, "-y", "-hide_banner", "-nostats",
        "-i", long_video, "-i", audio,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "copy", "-shortest", out_video,
    ])
    if code != 0 or not os.path.isfile(out_video):
        raise RuntimeError(f"合成视频失败:\n{e[-1500:]}")
    return out_video


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_build(cfg, audio_only=False, keep_temp=False):
    _check_tools()
    short_video = cfg["short_video"]
    long_video = cfg["long_video"]
    for p in (short_video, long_video):
        if not os.path.isfile(p):
            raise RuntimeError(f"找不到文件: {p}")

    out_dir = cfg.get("output_dir") or os.path.join(
        os.path.dirname(os.path.abspath(long_video)), "配乐合成")
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(long_video))[0]
    tmp_short = os.path.join(out_dir, "_bgmsrc.m4a")
    tmp_long = os.path.join(out_dir, "_voice.m4a")
    tmp_audio = os.path.join(out_dir, f"_audio_{base}.m4a")
    out_video = os.path.join(out_dir, f"{base}_带BGM.mp4")

    print("\n[1/5] 抽取音轨（小文件，IO 安全）...")
    extract_audio(short_video, tmp_short)
    extract_audio(long_video, tmp_long)
    sbr = probe_audio_bitrate(tmp_short)
    print(f"      BGM 音源码率: {sbr//1000 if sbr else '?'}k")

    print("[2/5] 分析 BGM 结构 + 合并配置...")
    info = analyze_bgm(tmp_short)
    params = {
        "duration": probe_duration(tmp_long),  # 时间轴=长视频
        "song_start": info["song_start"],
        "song_end": info["song_end"],
        "loop_start": info["loop_start"],
        "skip_ranges": cfg.get("skip_ranges", []),
        "silence_zones": cfg.get("silence_zones", []),
        "anchors": cfg.get("anchors", []),
        "intro_once": cfg.get("intro_once", True),
        "bgm_volume": cfg.get("bgm_volume", 0.85),
        "voice_volume": cfg.get("voice_volume", 0.6),
        "duck_ratio": cfg.get("duck_ratio", 1.8),
        "duck_threshold": cfg.get("duck_threshold", 0.05),
        "fade_in": cfg.get("fade_in", 1.5),
        "fade_out": cfg.get("fade_out", 4.0),
        "skip_seam": cfg.get("skip_seam", 0.8),
        "loop_seam": cfg.get("loop_seam", 0.4),
    }
    # 允许配置显式覆盖自动探测
    for k in ("song_start", "song_end", "loop_start"):
        if cfg.get(k) is not None:
            params[k] = float(cfg[k])
    print_analysis({**info, "song_start": params["song_start"],
                    "song_end": params["song_end"],
                    "loop_start": params["loop_start"]}, tmp_short)

    print("[3/5] 生成音频滤镜图...")
    filt, segs, plans = build_filter(params)
    print(f"      BGM 段: {[(round(a,1), round(b,1)) for a, b in segs]}")
    if params["silence_zones"]:
        print(f"      留白段: {params['silence_zones']}")

    print("[4/5] 合成混音轨（BGM 循环 + 人声闪避，256k）...")
    bitrate = cfg.get("bitrate", "256k")
    synth_audio(tmp_short, tmp_long, filt, tmp_audio, bitrate)
    print(f"      OK -> {os.path.basename(tmp_audio)}  时长 {probe_duration(tmp_audio):.1f}s")

    if audio_only:
        print("\n[完成] 仅合成音频（测试模式），未生成视频。")
        if not keep_temp:
            for f in (tmp_short, tmp_long):
                if os.path.isfile(f):
                    os.remove(f)
        return tmp_audio

    print("[5/5] 复用视频流合成成品（视频 copy 不重编码）...")
    mux(long_video, tmp_audio, out_video)
    print(f"\n[完成] 成品: {out_video}")

    if not keep_temp:
        for f in (tmp_short, tmp_long, tmp_audio):
            if os.path.isfile(f):
                os.remove(f)
        print("       中间产物已清理。")
    return out_video


# ---------------------------------------------------------------------------
# 交互界面
# ---------------------------------------------------------------------------
def _ask_path(prompt):
    s = input(prompt).strip().strip('"').strip("'")
    return s


def interactive():
    _check_tools()
    print("=" * 56)
    print("  视频 BGM 配乐合成工具")
    print("  把短视频的 BGM 干净循环铺到长视频上，保留人声")
    print("=" * 56)
    while True:
        print("\n  [1] 快速合成（全自动，全程铺 BGM）")
        print("  [2] 自定义合成（设留白 / 音量 / 锚点）")
        print("  [3] 仅分析 BGM 结构")
        print("  [0] 退出")
        choice = input("  选择> ").strip()
        try:
            if choice == "1":
                _flow_quick()
            elif choice == "2":
                _flow_custom()
            elif choice == "3":
                _flow_analyze()
            elif choice == "0":
                print("  再见。")
                return
            else:
                print("  无效选择。")
        except Exception as ex:
            print(f"\n  [出错] {ex}\n")


def _flow_quick():
    short = _ask_path("  短视频(带BGM)路径> ")
    long = _ask_path("  长视频(带人声)路径> ")
    out = _ask_path("  输出目录(留空=长视频旁/配乐合成)> ") or None
    run_build({"short_video": short, "long_video": long, "output_dir": out})


def _flow_custom():
    short = _ask_path("  短视频(带BGM)路径> ")
    long = _ask_path("  长视频(带人声)路径> ")
    out = _ask_path("  输出目录(留空=长视频旁/配乐合成)> ") or None

    print("\n  正在分析 BGM 结构...")
    tmp = os.path.join(os.path.dirname(os.path.abspath(short)), "_analyze_tmp.m4a")
    extract_audio(short, tmp)
    info = analyze_bgm(tmp)
    print_analysis(info, tmp)
    os.remove(tmp)

    zs = parse_zone_list(
        _ask_path("  留白时段(无BGM, 如 0-23,4:35-4:54 ; 留空=全程BGM)> "))
    bv = _ask_path("  BGM音量(默认0.85)> ") or "0.85"
    vv = _ask_path("  人声音量(默认0.6)> ") or "0.6"
    dr = _ask_path("  闪避强度ratio(默认1.8)> ") or "1.8"
    skip = _ask_path("  跳过间奏区(短视频内, 如 163.2-181.9 ; 留空=不跳)> ")
    skip_ranges = parse_zone_list(skip) if skip else []

    anchors = []
    print("  锚点(可选): 让某段BGM从歌曲指定位置起播。直接回车跳过。")
    while True:
        a = _ask_path("    锚点 '长视频时间=歌曲位置'(如 4:54=182 ; 回车结束)> ")
        if not a:
            break
        lt, sp = a.split("=", 1)
        anchors.append({"long_time": parse_time(lt), "song_pos": sp.strip()})

    run_build({
        "short_video": short, "long_video": long, "output_dir": out,
        "silence_zones": zs, "skip_ranges": skip_ranges, "anchors": anchors,
        "bgm_volume": float(bv), "voice_volume": float(vv), "duck_ratio": float(dr),
    })


def _flow_analyze():
    short = _ask_path("  短视频(带BGM)路径> ")
    tmp = os.path.join(os.path.dirname(os.path.abspath(short)), "_analyze_tmp.m4a")
    extract_audio(short, tmp)
    info = analyze_bgm(tmp)
    print_analysis(info, tmp)
    os.remove(tmp)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="视频 BGM 配乐合成工具")
    ap.add_argument("--config", help="JSON 配置文件路径")
    ap.add_argument("--audio-only", action="store_true", help="只合成音频(测试)")
    ap.add_argument("--keep-temp", action="store_true", help="保留中间产物")
    args = ap.parse_args()

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        run_build(cfg, audio_only=args.audio_only, keep_temp=args.keep_temp)
    else:
        interactive()


if __name__ == "__main__":
    main()
