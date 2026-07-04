"""
代码键误译扫描器 —— 揪出机翻把"被JS当switch/==/MetaChecker匹配的日文魔法字符串"译成中文的bug。
原理：
 1. 从所有插件提取「代码键」= 出现在 case "X" / ==/===/!=/!== "X" / MetaChecker(...,'X',...) 里的字符串字面量(含日文)。
 2. 逐数据文件并行遍历 原版 vs 部署译版；凡 原版某叶子值∈代码键集合 且 部署值≠原版 → 该键被误译(=bug)。
用法: python scan_codekeys.py <原版游戏www目录> <部署译版data目录>
  例: python scan_codekeys.py "游戏/www" "译版/data"
"""
import io, json, re, glob, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

jp = re.compile(r'[぀-ヿ぀-ゟ゠-ヿ一-鿿]')


def extract_keys():
    keys = set()
    pats = [
        re.compile(r'case\s+(["\'])(.*?)\1'),
        re.compile(r'[=!]==?\s*(["\'])(.*?)\1'),
        re.compile(r'(["\'])(.*?)\1\s*[=!]==?'),
        re.compile(r'MetaChecker\([^,]+,\s*(["\'])(.*?)\1'),
    ]
    for f in glob.glob(PLUGINS):
        try:
            t = open(f, 'r', encoding='utf-8-sig').read()
        except Exception:
            continue
        for p in pats:
            for m in p.finditer(t):
                s = m.group(2)
                if s and jp.search(s):
                    keys.add(s)
    return keys


def main():
    keys = extract_keys()
    print('提取的日文代码键(switch/==/MetaChecker) 共', len(keys), '个')
    # 子串集合：数据里的值可能是 "X" 整体，也可能值就是键本身
    hits = []  # (file, path, origval, deployval)

    def walk(o, d, path, fn):
        if isinstance(o, dict) and isinstance(d, dict):
            for k in o:
                if k in d:
                    walk(o[k], d[k], path + '/' + str(k), fn)
        elif isinstance(o, list) and isinstance(d, list):
            for i in range(min(len(o), len(d))):
                walk(o[i], d[i], path + '[' + str(i) + ']', fn)
        elif isinstance(o, str) and isinstance(d, str):
            if o != d and o in keys:
                hits.append((fn, path, o, d))

    for of in glob.glob(ORIG + 'data/*.json'):
        fn = os.path.basename(of)
        df = DEPLOY_DATA + fn
        if not os.path.exists(df):
            continue
        try:
            o = json.load(open(of, 'r', encoding='utf-8-sig'))
            d = json.load(open(df, 'r', encoding='utf-8-sig'))
        except Exception as e:
            print('  跳过', fn, e)
            continue
        walk(o, d, '', fn)

    print('\n★被误译的代码键实例 共', len(hits), '处:')
    # 按 (文件,键) 聚合
    from collections import Counter
    agg = Counter()
    for fn, path, o, dv in hits:
        agg[(fn, o, dv)] += 1
    for (fn, o, dv), c in agg.most_common():
        print('  [%s] %r -> %r  ×%d' % (fn, o, dv, c))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('用法: python scan_codekeys.py <原版游戏www目录> <部署译版data目录>')
        sys.exit(0)
    ORIG = sys.argv[1].rstrip('/\\') + '/'
    DEPLOY_DATA = sys.argv[2].rstrip('/\\') + '/'
    PLUGINS = ORIG + 'js/plugins/*.js'
    main()
