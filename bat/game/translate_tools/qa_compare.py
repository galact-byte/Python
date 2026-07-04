"""
QA 对照montage：日文原图(上) vs 汉化图(下) 逐对并排，网格成一张可视 PNG。
用途：肉眼判断 inpaint 擦除是否穿帮（盖痕/色块/超框/色差）。

用法:
  python qa_compare.py <日文原图根目录> <汉化图根目录> <category子目录> [max_w]
例:
  python qa_compare.py 解密/www/img/pictures 汉化/img_chs/pictures UI_Card
透明图垫深灰底(64,64,64)以便看清白字/边缘。
"""
import io, sys, os
from PIL import Image, ImageDraw, ImageFont
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BG = (64, 64, 64)
PAD = 6
LABEL_H = 14


def flat(im, bg=BG):
    im = im.convert("RGBA")
    canvas = Image.new("RGB", im.size, bg)
    canvas.paste(im, (0, 0), im)
    return canvas


def try_font():
    for p in [r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/consola.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, 11)
    return ImageFont.load_default()


def main():
    if len(sys.argv) < 4:
        print(__doc__); return
    jp_root, zh_root, cat = sys.argv[1], sys.argv[2], sys.argv[3]
    max_w = int(sys.argv[4]) if len(sys.argv) > 4 else 320
    zh_dir = os.path.join(zh_root, cat)
    if not os.path.isdir(zh_dir):
        print("汉化目录不存在:", zh_dir); return
    font = try_font()
    cells = []
    for fn in sorted(os.listdir(zh_dir)):
        if not fn.lower().endswith(".png"):
            continue
        zh_p = os.path.join(zh_dir, fn)
        jp_p = os.path.join(jp_root, cat, fn)
        zh = flat(Image.open(zh_p))
        jp = flat(Image.open(jp_p)) if os.path.exists(jp_p) else Image.new("RGB", zh.size, (90, 30, 30))
        w = min(max_w, max(jp.width, zh.width))
        def scale(im):
            if im.width > w:
                return im.resize((w, max(1, round(im.height * w / im.width))))
            return im
        jp, zh = scale(jp), scale(zh)
        cw = max(jp.width, zh.width)
        ch = LABEL_H + jp.height + 2 + zh.height
        cell = Image.new("RGB", (cw, ch), (30, 30, 30))
        d = ImageDraw.Draw(cell)
        d.text((2, 1), fn[:34], font=font, fill=(255, 230, 120))
        cell.paste(jp, (0, LABEL_H))
        cell.paste(zh, (0, LABEL_H + jp.height + 2))
        cells.append(cell)
    if not cells:
        print("无PNG"); return
    cols = max(1, min(4, len(cells)))
    rows = (len(cells) + cols - 1) // cols
    cellw = max(c.width for c in cells) + PAD
    cellh = max(c.height for c in cells) + PAD
    grid = Image.new("RGB", (cols * cellw + PAD, rows * cellh + PAD), (15, 15, 15))
    for i, c in enumerate(cells):
        r, cc = divmod(i, cols)
        grid.paste(c, (PAD + cc * cellw, PAD + r * cellh))
    out = os.path.join(os.path.dirname(__file__), "qa", "cmp_" + cat.replace("/", "_") + ".png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    grid.save(out)
    print("OK ->", out, grid.size, "上=日原 下=汉化")


if __name__ == "__main__":
    main()
