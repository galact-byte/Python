# -*- coding: utf-8 -*-
"""RPG Maker MV/MZ 隐藏水印工具(通用·复用于任意游戏汉化)。

把自定义签名埋进 data:
  · System.json 自定义键 gxWatermark
  · 分散多个数据库(Actors/States/Weapons/Armors/Skills/Enemies/Items/Classes)
    的 note 字段末尾 <gxsig:base64> —— 玩家不可见·插件不误读(meta无人读)·
    分散冗余难全删·note 经 RPG Maker 编辑器重导出仍保留。

用法:
  python watermark_tool.py embed <www/data目录> "你的签名文字"
  python watermark_tool.py check <www/data目录>       # 检测并解码水印(证明归属)

示例签名: "galact-游戏名-机翻润色-2026"
"""
import io, sys, json, os, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_FILES = ['Actors.json', 'States.json', 'Weapons.json', 'Armors.json',
            'Skills.json', 'Enemies.json', 'Items.json', 'Classes.json']
# 每个数据库埋的下标(首个有效+末尾·尽量分散·index超范围自动跳过)
DB_INDEXES = {'Actors.json': [1, -1]}
DEFAULT_INDEXES = [-1]


def load(p):
    return json.load(open(p, encoding='utf-8-sig'))


def save(p, o):
    json.dump(o, open(p, 'w', encoding='utf-8'), ensure_ascii=False)


def _tag(sig_b64):
    return '<gxsig:%s>' % sig_b64


def embed(data_dir, plain):
    sig = base64.b64encode(plain.encode('utf-8')).decode()
    tag = _tag(sig)
    locs = []
    sp = os.path.join(data_dir, 'System.json')
    if os.path.exists(sp):
        s = load(sp); s['gxWatermark'] = sig; save(sp, s)
        locs.append('System.json → 键 gxWatermark')
    for fn in DB_FILES:
        p = os.path.join(data_dir, fn)
        if not os.path.exists(p):
            continue
        arr = load(p)
        if not isinstance(arr, list):
            continue
        done = []
        for i in DB_INDEXES.get(fn, DEFAULT_INDEXES):
            idx = len(arr) + i if i < 0 else i
            if 0 <= idx < len(arr) and isinstance(arr[idx], dict):
                e = arr[idx]; note = e.get('note', '') or ''
                if 'gxsig' not in note:
                    e['note'] = (note + '\n' + tag) if note else tag
                    done.append(idx)
        if done:
            save(p, arr); locs.append('%s → note index %s' % (fn, done))
    print('水印明文:', plain)
    print('base64  :', sig)
    print('note tag:', tag)
    print('已埋入 %d 处:' % len(locs))
    for x in locs:
        print('  ·', x)
    return sig


def check(data_dir):
    """扫描 data 找 gxsig / gxWatermark·解码报告(证明归属)。"""
    found = []
    sp = os.path.join(data_dir, 'System.json')
    if os.path.exists(sp):
        s = load(sp)
        if s.get('gxWatermark'):
            found.append(('System.json:gxWatermark', s['gxWatermark']))
    for fn in os.listdir(data_dir):
        if not fn.endswith('.json'):
            continue
        try:
            arr = load(os.path.join(data_dir, fn))
        except Exception:
            continue
        if isinstance(arr, list):
            for i, e in enumerate(arr):
                if isinstance(e, dict):
                    note = e.get('note', '') or ''
                    if 'gxsig:' in note:
                        b = note.split('gxsig:')[1].split('>')[0]
                        found.append(('%s[%d].note' % (fn, i), b))
    if not found:
        print('未检测到水印。')
        return
    print('检测到 %d 处水印:' % len(found))
    for loc, b in found:
        try:
            plain = base64.b64decode(b).decode('utf-8')
        except Exception:
            plain = '(解码失败)'
        print('  · %-28s → %s' % (loc, plain))


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == 'embed':
        embed(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == 'check':
        check(sys.argv[2])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
