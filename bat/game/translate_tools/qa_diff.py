"""
框保护差异QA：对一个目录(或文件列表)输出「原图 | 现状汉化 | 差异热图」三联，
红=大改(>25)/黄=轻改。用于核查擦除有没有动到框(框区出现红=越界改框)。
用法: python qa_diff.py <日文原图根目录> <汉化图根目录> <category子目录> [max_w]
  例: python qa_diff.py 解密/www/img/pictures 汉化/img_chs/pictures UI_Card
"""
import io, sys, os
import numpy as np
from PIL import Image
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BG = (64, 64, 64)


def flat(p):
    im = Image.open(p).convert("RGBA")
    c = Image.new("RGB", im.size, BG)
    c.paste(im, (0, 0), im)
    return np.array(c)


def main():
    if len(sys.argv) < 4:
        print(__doc__); return
    jp_root, zh_root, cat = sys.argv[1], sys.argv[2], sys.argv[3]
    max_w = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    zh_dir = os.path.join(zh_root, cat)
    if not os.path.isdir(zh_dir):
        print("无:", zh_dir); return
    rows = []
    for fn in sorted(os.listdir(zh_dir)):
        if not fn.lower().endswith(".png"):
            continue
        zp = os.path.join(zh_dir, fn); jp = os.path.join(jp_root, cat, fn)
        if not os.path.exists(jp):
            continue
        z = flat(zp); j = flat(jp)
        if z.shape != j.shape:
            continue
        d = np.abs(j.astype(int) - z.astype(int)).sum(2)
        heat = j.copy(); heat[d > 25] = [255, 40, 40]; heat[(d > 8) & (d <= 25)] = [255, 240, 0]
        gap = np.full((j.shape[0], 5, 3), 25, np.uint8)
        row = np.concatenate([j, gap, z, gap, heat], axis=1)
        # 文件名标签条
        lbl = np.full((13, row.shape[1], 3), 30, np.uint8)
        rows.append((fn, lbl, row))
    if not rows:
        print("无可对比PNG"); return
    from PIL import ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 11)
    except Exception:
        font = ImageFont.load_default()
    W = max(r[2].shape[1] for r in rows)
    parts = []
    for fn, lbl, row in rows:
        li = Image.fromarray(lbl); ImageDraw.Draw(li).text((2, 0), fn, font=font, fill=(255, 230, 120))
        parts.append(np.array(li)); parts.append(row)
        parts.append(np.full((4, row.shape[1], 3), 0, np.uint8))
    canvas = np.zeros((sum(p.shape[0] for p in parts), W, 3), np.uint8)
    y = 0
    for p in parts:
        canvas[y:y + p.shape[0], :p.shape[1]] = p; y += p.shape[0]
    out = Image.fromarray(canvas)
    if max_w and out.width > max_w:
        out = out.resize((max_w, round(out.height * max_w / out.width)))
    op = os.path.join(os.path.dirname(__file__), "qa", "diff_" + cat.replace("/", "_") + ".png")
    os.makedirs(os.path.dirname(op), exist_ok=True)
    out.save(op)
    print("OK ->", op, out.size, "列:原|现|热图(红=改·看框区有无红)")


if __name__ == "__main__":
    main()
