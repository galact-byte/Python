"""
PNG 汉化脚本 (通用·v2·cv2.inpaint 修复式擦除)
依据 translation.json 批量生成中文版 PNG(适配任意游戏·配置驱动)。

v2 核心改进（解决"平涂矩形"违和感）：
  旧版用 draw.rectangle 采一个底色平涂整框 → 渐变/斜纹/波纹被抹平、采样偏色、矩形超框。
  新版用 **cv2.inpaint 修复式擦除**：
    1. 在覆盖框(+边距)内，按"文字色"检测原文笔画像素(颜色距离阈值)
    2. 连通域过滤：只保留与框相交/相邻的笔画块 → 不误抹两侧箭头/图标
    3. cv2.inpaint(TELEA) 用周围像素重建文字下的底纹(渐变/斜纹/波纹都续上)
    4. 再写中文
  → 只动文字像素、保留原底样式、不超框。

兼容：
  - 透明发光层(auto_bg:False + background_color 第4位=0)→清透明(沿旧法)
  - 个别需要平涂的可在 layer 设 "erase":"solid"
  - layer 仍用 zh/box_pct/font_size_pct/align/valign/text_color/stroke_*

使用：python translate_pngs.py [translation.json 路径]
依赖：pip install Pillow opencv-python numpy
"""

import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    import cv2
except ImportError as e:
    print(f"[X] 缺少依赖({e})，请运行: pip install Pillow opencv-python numpy")
    sys.exit(1)

try:
    from scipy.interpolate import griddata as _griddata
except ImportError:
    _griddata = None


def hex_or_rgb(color):
    if isinstance(color, str):
        c = color.lstrip("#")
        if len(c) == 6:
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        if len(c) == 8:
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4, 6))
    if isinstance(color, (list, tuple)):
        return tuple(color)
    return color


def load_font(font_path, size, variation_axes=None):
    font = ImageFont.truetype(font_path, size)
    if not variation_axes:
        return font
    name = variation_axes.get("name") if isinstance(variation_axes, dict) else None
    if name:
        try:
            font.set_variation_by_name(name)
            return font
        except (OSError, AttributeError):
            pass
    try:
        axes_info = font.get_variation_axes()
    except (OSError, AttributeError):
        return font
    if not axes_info:
        return font
    values = []
    for axis in axes_info:
        ax_name = axis.get("name", b"")
        if isinstance(ax_name, bytes):
            ax_name = ax_name.decode("utf-8", errors="ignore")
        matched = None
        for k, v in variation_axes.items():
            if k == "name":
                continue
            if k.lower() == ax_name.lower() or k.lower() in ax_name.lower():
                matched = v
                break
        if matched is None:
            matched = axis.get("default")
        else:
            lo, hi = axis.get("minimum"), axis.get("maximum")
            if lo is not None and matched < lo:
                matched = lo
            if hi is not None and matched > hi:
                matched = hi
        values.append(matched)
    try:
        font.set_variation_by_axes(values)
    except (OSError, AttributeError):
        pass
    return font


def build_text_mask(rgb, box, tcolor=None, exp=0.12, thresh=78, dil=5,
                    margin=16, bg_method="ring"):
    """**偏离按钮底色**检测笔画(连白芯带深描边/辉光一起抓·解长字残影)→连通域过滤
    (只留与 box±margin 相交的块·排除两侧箭头/图标)→膨胀。返回整图 uint8 mask。
    bg_method:
      "ring"(默认)  底色取框上下外侧几行(文字行外的干净按钮底)的中位——适合
                   粗大渐变文字(每行被文字占满·边缘环才是干净底)。
      "rowmedian"  逐行中位作底色——适合"亮边框+较均匀底+稀疏白字"的按钮
                   (如 UI_FastTra)，边缘环会被亮边框污染导致整框误擦时改用。"""
    h, w = rgb.shape[:2]
    x1, y1, x2, y2 = box
    mx = int((x2 - x1) * exp) + 4
    my = int((y2 - y1) * exp) + 3
    ex1, ey1 = max(0, x1 - mx), max(0, y1 - my)
    ex2, ey2 = min(w, x2 + mx), min(h, y2 + my)
    if ex2 <= ex1 or ey2 <= ey1:
        return np.zeros((h, w), np.uint8)
    region = rgb[ey1:ey2, ex1:ex2].astype(np.int32)
    if bg_method == "rowmedian":
        # 逐行底色：文字/高光在行内稀疏→行中位≈该行底色，随纵向渐变自适应，
        # 且不受框外亮边框污染(边框只占少数行·其余行仍取到真底色)。
        bg = np.median(region, axis=1, keepdims=True)   # (H,1,3)
        dist = np.sqrt(((region - bg) ** 2).sum(2))
    else:
        # 底色：框上/下外侧各 5 行(文字外的按钮底)；不足则退而取框内边
        top = rgb[max(0, y1 - 3):y1 + 2, x1:x2].reshape(-1, 3)
        bot = rgb[max(0, y2 - 2):min(h, y2 + 3), x1:x2].reshape(-1, 3)
        ring = np.vstack([top, bot]).astype(np.int32)
        if len(ring) < 8:
            ring = np.vstack([rgb[y1:y1 + 3, x1:x2].reshape(-1, 3),
                              rgb[max(0, y2 - 3):y2, x1:x2].reshape(-1, 3)]).astype(np.int32)
        bg = np.median(ring, axis=0) if len(ring) else np.array([0, 0, 0])
        dist = np.sqrt(((region - bg) ** 2).sum(2))
    cand = (dist > thresh).astype(np.uint8)
    n, lbl = cv2.connectedComponents(cand)
    bx1, by1 = x1 - ex1, y1 - ey1
    bx2, by2 = x2 - ex1, y2 - ey1
    boxsel = np.zeros_like(cand)
    boxsel[max(0, by1 - margin):by2 + margin, max(0, bx1 - margin):bx2 + margin] = 1
    keep = np.zeros_like(cand)
    for c in range(1, n):
        comp = (lbl == c)
        if (comp & boxsel).any():
            keep |= comp.astype(np.uint8)
    mask = np.zeros((h, w), np.uint8)
    mask[ey1:ey2, ex1:ex2] = keep * 255
    if dil > 0:
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=dil)
    return mask


def inpaint_erase(arr, box, tcolor, layer):
    """cv2.inpaint 修复式擦除文字、保留 alpha；底纹(渐变/斜纹/波纹)由周围像素重建。"""
    rgb = arr[:, :, :3].copy()
    al = arr[:, :, 3]
    exp = layer.get("erase_exp", 0.18)
    thresh = layer.get("erase_thresh", 78)
    margin = layer.get("erase_margin", 16)
    dil = layer.get("erase_dil", 4)
    rad = layer.get("erase_radius", 6)
    bg_method = layer.get("bg_method", "ring")
    mask = build_text_mask(rgb, box, exp=exp, thresh=thresh, dil=dil,
                           margin=margin, bg_method=bg_method)
    inp = cv2.inpaint(rgb, mask, rad, cv2.INPAINT_TELEA)
    arr[:, :, :3] = inp
    return arr


def layer_box(box_pct, w, h):
    return (int(box_pct[0] * w), int(box_pct[1] * h),
            int(box_pct[2] * w), int(box_pct[3] * h))


def draw_text(draw, layer, defaults, w, h):
    """把中文写到框中（定位/对齐/描边沿旧逻辑）。"""
    box = layer_box(layer["box_pct"], w, h)
    fg = hex_or_rgb(layer.get("text_color", defaults["text_color"]))
    stroke_color = layer.get("stroke_color", defaults.get("stroke_color"))
    stroke_width = layer.get("stroke_width", defaults.get("stroke_width", 0))

    font_size = max(8, int(layer["font_size_pct"] * h))
    font_path = layer.get("font_path", defaults["font_path"])
    variation = layer.get("font_variation", defaults.get("font_variation"))
    font = load_font(font_path, font_size, variation_axes=variation)

    text = layer["zh"]
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w, box_h = box[2] - box[0], box[3] - box[1]

    align = layer.get("align", "center")
    if align == "left":
        x = box[0] - bbox[0]
    elif align == "right":
        x = box[2] - tw - bbox[0]
    else:
        x = box[0] + (box_w - tw) // 2 - bbox[0]

    valign = layer.get("valign", "middle")
    if valign == "top":
        y = box[1] - bbox[1]
    elif valign == "bottom":
        y = box[3] - th - bbox[1]
    else:
        y = box[1] + (box_h - th) // 2 - bbox[1]

    if stroke_color and stroke_width > 0:
        draw.text((x, y), text, font=font, fill=fg,
                  stroke_fill=hex_or_rgb(stroke_color), stroke_width=stroke_width)
    else:
        draw.text((x, y), text, font=font, fill=fg)


def erase_mode_of(layer, defaults):
    """决定擦除方式：透明发光层→transparent；显式 erase 字段优先；否则 inpaint。"""
    if "erase" in layer:
        return layer["erase"]
    auto_bg = layer.get("auto_bg", defaults.get("auto_bg", True))
    bgc = layer.get("background_color", defaults.get("background_color"))
    if (not auto_bg) and isinstance(bgc, (list, tuple)) and len(bgc) == 4 and bgc[3] == 0:
        return "transparent"
    return "inpaint"


def process_image(entry, defaults):
    src = entry["input_path"]
    dst = entry["output_path"]
    name = entry.get("filename", Path(src).name)
    if not os.path.exists(src):
        print(f"[X] 源文件不存在: {src}")
        return False
    print(f"  [..] {name}")

    img = Image.open(src).convert("RGBA")
    w, h = img.size
    arr = np.array(img)

    # PASS 1：逐层擦除（inpaint / 透明清除 / 平涂）
    for layer in entry["layers"]:
        box = layer_box(layer["box_pct"], w, h)
        tcolor = hex_or_rgb(layer.get("text_color", defaults["text_color"]))
        mode = erase_mode_of(layer, defaults)
        if mode == "transparent":
            x1, y1, x2, y2 = box
            arr[max(0, y1):y2, max(0, x1):x2] = 0
        elif mode == "solid":
            bgc = hex_or_rgb(layer.get("background_color", defaults["background_color"]))
            if len(bgc) == 3:
                bgc = bgc + (255,)
            x1, y1, x2, y2 = box
            arr[max(0, y1):y2, max(0, x1):x2] = bgc
        elif mode == "flatten":
            # 把框内「不透明」像素整体(含 alpha)归一为面板 RGBA → 彻底抹平文字。
            # 关键：必须连 alpha 一起统一,否则文字芯(a高)/边(a低)与面板 alpha 不同,
            # 叠到游戏背景时透出不同程度的底色 → 画出文字轮廓 ghost。透明区(a低)不动。
            bgc = hex_or_rgb(layer.get("background_color", defaults["background_color"]))
            if len(bgc) == 3:
                bgc = bgc + (209,)
            x1, y1, x2, y2 = box
            x1, y1 = max(0, x1), max(0, y1)
            reg = arr[y1:y2, x1:x2]
            a_thr = layer.get("flatten_alpha", 150)
            m = reg[:, :, 3] > a_thr
            reg[m] = bgc
            arr[y1:y2, x1:x2] = reg
        elif mode == "glyph2panel":
            # 半透明衬底上的亮字：只把「亮且不透明」的字形像素替换为衬底色，
            # 透明像素(alpha<阈)一律不碰——杜绝把面板外透明区填成黑条。
            bgc = hex_or_rgb(layer.get("background_color", defaults["background_color"]))
            if len(bgc) == 3:
                bgc = bgc + (255,)
            x1, y1, x2, y2 = box
            x1, y1 = max(0, x1), max(0, y1)
            reg = arr[y1:y2, x1:x2]
            lum = reg[:, :, :3].mean(axis=2)
            a = reg[:, :, 3]
            lum_thr = layer.get("glyph_lum", 30)
            a_thr = layer.get("glyph_alpha", 120)
            if layer.get("glyph_white"):
                # 白字(含辉光halo)：min(R,G,B)高 → 与彩色底(蓝/青,某通道≈0)区分,
                # 可用更低阈值兜住halo而不误伤彩底
                mn = reg[:, :, :3].min(axis=2)
                glyph = (a > a_thr) & (mn > lum_thr)
            elif layer.get("glyph_red"):
                # 红字(警告语)：R 高、G/B 低 → 与暗底/白高光都能区分。
                rr = reg[:, :, 0]; gg = reg[:, :, 1]; bb = reg[:, :, 2]
                r_thr = layer.get("glyph_red_r", 110)
                gb_thr = layer.get("glyph_red_gb", 95)
                glyph = (a > a_thr) & (rr > r_thr) & (gg < gb_thr) & (bb < gb_thr)
            elif layer.get("glyph_cyan"):
                # 青字(科技风标题)：G 高、B 高 → 与深蓝底(G 偏低)区分。
                # glyph_white 对青字失效(青色 min(R,G,B)=R≈0),必须用此分支。
                gg = reg[:, :, 1]; bb = reg[:, :, 2]
                gthr = layer.get("glyph_cyan_g", 120)
                bthr = layer.get("glyph_cyan_b", 120)
                glyph = (a > a_thr) & (gg > gthr) & (bb > bthr)
            else:
                glyph = (a > a_thr) & (lum > lum_thr)
            if layer.get("glyph_fill") == "inpaint":
                # 精确字形 mask → 膨胀裹住抗锯齿halo → cv2.inpaint 从周围底重建
                # (深色面板上白/彩字最佳·alpha不动·透明角自动保留)
                gm = (glyph.astype(np.uint8)) * 255
                dl = layer.get("glyph_dilate", 3)
                gm = cv2.dilate(gm, np.ones((dl, dl), np.uint8), iterations=1)
                rgb = reg[:, :, :3].copy()
                rad = layer.get("inpaint_radius", 4)
                rep = cv2.inpaint(rgb, gm, rad, cv2.INPAINT_TELEA)
                reg[:, :, :3] = rep
                # glyph_fix_alpha: 字芯 alpha(248~252) 高于面板底(218~225),只改 RGB 会
                # 残留 alpha 轮廓 ghost(叠到游戏背景透出)。同 mask inpaint alpha 通道,
                # 把字形区 alpha 也重建为周围面板 alpha → 彻底消除轮廓。
                if layer.get("glyph_fix_alpha"):
                    ach = reg[:, :, 3].copy()
                    arep = cv2.inpaint(ach, gm, rad, cv2.INPAINT_TELEA)
                    reg[:, :, 3] = arep
            elif layer.get("glyph_fill") == "transparent":
                # 按钮内部本就透明、只有白字+黑描边是不透明内容(如 BJ RstBtn)：
                # 精确检测白芯(+可选黑描边)→膨胀→清成透明·恢复透明内部·绝不动框。
                gmask = glyph.copy()
                if layer.get("glyph_dark"):
                    opq = a > a_thr
                    op_lum = reg[:, :, :3].mean(2)[opq]
                    if len(op_lum) >= 8:
                        lo, hi = np.percentile(op_lum, [30, 70])
                        base = float(np.median(op_lum[(op_lum >= lo) & (op_lum <= hi)]))
                    else:
                        base = float(op_lum.mean()) if len(op_lum) else 0.0
                    dmar = layer.get("glyph_dark_margin", 40)
                    dark = opq & (reg[:, :, :3].mean(2) < base - dmar)
                    gmask = gmask | dark
                gm = (gmask.astype(np.uint8)) * 255
                dl = layer.get("glyph_dilate", 3)
                if dl > 0:
                    gm = cv2.dilate(gm, np.ones((3, 3), np.uint8), iterations=dl)
                reg[gm > 0] = (0, 0, 0, 0)
            elif layer.get("glyph_fill") == "interp2d":
                # 2D 立体渐变面板(dpPnl 卡片·横+纵双向层次)：rowclean 逐行平填丢横向层次→
                # 两边原文处留平块。此模式对 RGBA 各通道用 griddata 2D 插值·从周围面板
                # 平滑续上双向渐变·无平块·无椭圆。检测白字+黑边膨胀为待插值区。
                gmask = glyph.copy()
                if layer.get("glyph_dark"):
                    # 渐变/扫描线面板上慎用：暗扫描线会被当"字"全宽捕获→插值出全宽带。
                    opq = a > a_thr
                    op_lum = reg[:, :, :3].mean(2)[opq]
                    if len(op_lum) >= 8:
                        lo, hi = np.percentile(op_lum, [30, 70])
                        base = float(np.median(op_lum[(op_lum >= lo) & (op_lum <= hi)]))
                    else:
                        base = float(op_lum.mean()) if len(op_lum) else 0.0
                    dmar = layer.get("glyph_dark_margin", 36)
                    dark = opq & (reg[:, :, :3].mean(2) < base - dmar)
                    gmask = gmask | dark
                gm = (gmask.astype(np.uint8)) * 255
                dl = layer.get("glyph_dilate", 3)
                if dl > 0:
                    gm = cv2.dilate(gm, np.ones((3, 3), np.uint8), iterations=dl)
                gmb = gm > 0
                Hh, Ww = reg.shape[:2]
                known = (~gmb) & (a > 120)
                if layer.get("glyph_exclude_cyan"):
                    rr = reg[:, :, 0].astype(np.int32)
                    gg = reg[:, :, 1].astype(np.int32)
                    bb = reg[:, :, 2].astype(np.int32)
                    known = known & ~((gg > rr + 25) & (bb > rr + 10))
                if _griddata is not None and gmb.any() and known.sum() >= 8:
                    yy, xx = np.mgrid[0:Hh, 0:Ww]
                    kpts = np.column_stack([xx[known], yy[known]])
                    qpts = np.column_stack([xx[gmb], yy[gmb]])
                    for c in range(4):
                        vals = reg[:, :, c][known].astype(np.float32)
                        out = _griddata(kpts, vals, qpts, method="linear")
                        nan = np.isnan(out)
                        if nan.any():
                            out[nan] = _griddata(kpts, vals, qpts[nan], method="nearest")
                        reg[:, :, c][gmb] = np.clip(out, 0, 255).astype(reg.dtype)
                else:
                    # 兜底：无 scipy 时退化为逐行中位
                    for ri in range(Hh):
                        grow = gmb[ri]
                        if not grow.any():
                            continue
                        src = reg[ri][(~gmb[ri]) & (a[ri] > 120)]
                        if len(src) >= 3:
                            reg[ri][grow] = np.median(src, axis=0).astype(reg.dtype)
            elif layer.get("glyph_fill") == "glassfix":
                # 半透玻璃对话框上的角标签：玻璃 alpha 有起伏·固定色填会留淡矩形。
                # 此模式对 RGB 与 alpha 都 cv2.inpaint·从周围玻璃续上(色+透明度皆无缝)·
                # 边框(青/不在 glyph mask)零改动。最干净·根治矩形痕迹。
                gmask = glyph.copy()
                if layer.get("glyph_dark"):
                    opq = a > a_thr
                    op_lum = reg[:, :, :3].mean(2)[opq]
                    if len(op_lum) >= 8:
                        lo, hi = np.percentile(op_lum, [30, 70])
                        base = float(np.median(op_lum[(op_lum >= lo) & (op_lum <= hi)]))
                    else:
                        base = float(op_lum.mean()) if len(op_lum) else 0.0
                    dmar = layer.get("glyph_dark_margin", 40)
                    dark = opq & (reg[:, :, :3].mean(2) < base - dmar)
                    gmask = gmask | dark
                gm = (gmask.astype(np.uint8)) * 255
                dl = layer.get("glyph_dilate", 2)
                if dl > 0:
                    gm = cv2.dilate(gm, np.ones((3, 3), np.uint8), iterations=dl)
                rad = layer.get("inpaint_radius", 4)
                rgbp = np.ascontiguousarray(reg[:, :, :3])
                reg[:, :, :3] = cv2.inpaint(rgbp, gm, rad, cv2.INPAINT_TELEA)
                ap = np.ascontiguousarray(reg[:, :, 3])
                reg[:, :, 3] = cv2.inpaint(ap, gm, rad, cv2.INPAINT_TELEA)
            elif layer.get("glyph_fill") == "panelfix":
                # 玻璃/半透对话框上的角标签：box 贴近边框时 rowclean 逐行中位会被
                # 边框污染→填出错色矩形。此模式用「固定面板 RGBA」填字形(白字+黑边膨胀)，
                # 与玻璃完全一致·无矩形·边框(青色 min RGB≈0 不被 glyph_white 捕获)零改动。
                gmask = glyph.copy()
                if layer.get("glyph_dark"):
                    opq = a > a_thr
                    op_lum = reg[:, :, :3].mean(2)[opq]
                    if len(op_lum) >= 8:
                        lo, hi = np.percentile(op_lum, [30, 70])
                        base = float(np.median(op_lum[(op_lum >= lo) & (op_lum <= hi)]))
                    else:
                        base = float(op_lum.mean()) if len(op_lum) else 0.0
                    dmar = layer.get("glyph_dark_margin", 40)
                    dark = opq & (reg[:, :, :3].mean(2) < base - dmar)
                    gmask = gmask | dark
                gm = (gmask.astype(np.uint8)) * 255
                dl = layer.get("glyph_dilate", 2)
                if dl > 0:
                    gm = cv2.dilate(gm, np.ones((3, 3), np.uint8), iterations=dl)
                reg[gm > 0] = bgc
            elif layer.get("glyph_fill") == "rowclean":
                # 白字带深色描边/阴影·底为均匀或纵向渐变(BJ 金框按钮)：
                #   ①白芯 mask 膨胀 glyph_dilate 盖住外侧暗阴影(否则残留黑鬼影)
                #   ②逐行用「排除膨胀字区后·去极值(25-75 百分位)」中位填充
                #     →既排亮字又排暗影·保留每行真实底色(纵向渐变自适应)·绝不 inpaint 涂糊。
                gmask = glyph.copy()
                if layer.get("glyph_dark"):
                    # 同时捕获「比面板底色暗 margin」的黑色描边/阴影像素(白字外缘)。
                    opq = a > a_thr
                    op_lum = reg[:, :, :3].mean(2)[opq]
                    if len(op_lum) >= 8:
                        lo, hi = np.percentile(op_lum, [30, 70])
                        base = float(np.median(op_lum[(op_lum >= lo) & (op_lum <= hi)]))
                    else:
                        base = float(op_lum.mean()) if len(op_lum) else 0.0
                    dmar = layer.get("glyph_dark_margin", 40)
                    dark = opq & (reg[:, :, :3].mean(2) < base - dmar)
                    gmask = gmask | dark
                gm = (gmask.astype(np.uint8)) * 255
                dl = layer.get("glyph_dilate", 3)
                if dl > 0:
                    gm = cv2.dilate(gm, np.ones((3, 3), np.uint8), iterations=dl)
                gmb = gm > 0
                arow = a
                # 两遍法(根治密集字行回退全局暗色→黑环/暗块)：
                #   ①每行用「非字形·不透明」像素去极值中位求 rowfill·不足则标 None
                #   ②None 行借用**最近有效行**的 rowfill(垂直连续·跟随辉光/渐变)
                H0 = reg.shape[0]
                ex_cyan = layer.get("glyph_exclude_cyan", False)
                rowfill = [None] * H0
                for ri in range(H0):
                    clean = (arow[ri] > 120) & (~gmb[ri])
                    if ex_cyan:
                        rr = reg[ri, :, 0].astype(np.int32)
                        gg = reg[ri, :, 1].astype(np.int32)
                        bb = reg[ri, :, 2].astype(np.int32)
                        clean = clean & ~((gg > rr + 25) & (bb > rr + 10))
                    src = reg[ri][clean]
                    if len(src) >= 5:
                        lums = src[:, :3].mean(1)
                        lo, hi = np.percentile(lums, [25, 75])
                        band = src[(lums >= lo) & (lums <= hi)]
                        rowfill[ri] = np.median(band if len(band) >= 3 else src,
                                                axis=0).astype(reg.dtype)
                valid = [i for i in range(H0) if rowfill[i] is not None]
                for ri in range(H0):
                    if rowfill[ri] is None:
                        rowfill[ri] = (rowfill[min(valid, key=lambda v: abs(v - ri))]
                                       if valid else np.array(bgc, reg.dtype))
                for ri in range(H0):
                    if gmb[ri].any():
                        reg[ri][gmb[ri]] = rowfill[ri]
            elif layer.get("glyph_fill") == "rowmedian":
                # 逐行用「非字形·不透明」像素中位填充字形 → 保留纵向渐变。
                # 关键：排除 alpha<120 的透明白像素([255,255,255,0]面板外区),
                # 否则中位被透明白污染 → 文字区被填白(残留)。
                arow = a  # (H,W) within region
                for ri in range(reg.shape[0]):
                    grow = glyph[ri]
                    if not grow.any():
                        continue
                    keep = reg[ri][(~grow) & (arow[ri] > 120)]
                    if len(keep) >= 3:
                        fillpx = np.median(keep, axis=0).astype(reg.dtype)
                        reg[ri][grow] = fillpx
                    else:
                        reg[ri][grow] = bgc
            else:
                reg[glyph] = bgc
            arr[y1:y2, x1:x2] = reg
        else:  # inpaint（默认）
            arr = inpaint_erase(arr, box, tcolor, layer)

    # PASS 2：逐层写中文
    img = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(img)
    for layer in entry["layers"]:
        draw_text(draw, layer, defaults, w, h)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst)
    print(f"  [OK] -> {dst}")
    return True


def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else \
        str(Path(__file__).parent / "translation.json")
    if not os.path.exists(cfg_path):
        print(f"[X] 配置文件不存在: {cfg_path}")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    defaults = cfg["default"]
    if not os.path.exists(defaults["font_path"]):
        print(f"[X] 字体文件不存在: {defaults['font_path']}")
        sys.exit(1)

    images = cfg["images"]
    # 可选过滤：--only=子串  仅处理 filename/input_path 含该子串的图（按目录迭代用）
    only = None
    for a in sys.argv[2:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
    if only:
        images = [e for e in images
                  if only in e.get("filename", "") or only in e.get("input_path", "")]
        print(f"[过滤 --only={only}] 命中 {len(images)} 张")
    print(f"开始处理 {len(images)} 张图 (cv2.inpaint 引擎)...")
    print("=" * 50)
    ok = 0
    for entry in images:
        if process_image(entry, defaults):
            ok += 1
    print("=" * 50)
    print(f"完成: {ok}/{len(images)} 张")


if __name__ == "__main__":
    main()
