# -*- coding: utf-8 -*-
"""RPG Maker MV/MZ .rpgmvp 加/解密(XOR 前 16 字节)。通用·适配任意 MV/MZ 游戏。

原理: [16字节RPGMV头][PNG前16字节 XOR key][PNG剩余原样]。
密钥 = 目标游戏 System.json 的 "encryptionKey"(32位十六进制)。

用法:
  python rpgmvp_tool.py key     <System.json路径>                     # 读出该游戏的 encryptionKey
  python rpgmvp_tool.py encrypt <PNG目录>    <输出rpgmvp目录> <key十六进制>
  python rpgmvp_tool.py decrypt <rpgmvp目录> <输出PNG目录>   <key十六进制>

也可作模块导入: encrypt_png_bytes(png, key) / decrypt_rpgmvp_bytes(data, key)。
"""
import io, sys, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HEADER = bytes([0x52, 0x50, 0x47, 0x4D, 0x56, 0x00, 0x00, 0x00,
                0x00, 0x03, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])


def _key(key_hex):
    return bytes.fromhex(key_hex.strip())


def encrypt_png_bytes(png, key):
    if isinstance(key, str):
        key = _key(key)
    body = bytearray(png)
    for i in range(min(16, len(body))):
        body[i] ^= key[i]
    return HEADER + bytes(body)


def decrypt_rpgmvp_bytes(data, key):
    if isinstance(key, str):
        key = _key(key)
    body = bytearray(data[16:])       # 去掉16字节头
    for i in range(min(16, len(body))):
        body[i] ^= key[i]
    return bytes(body)


def read_key(system_json):
    j = json.load(open(system_json, encoding='utf-8-sig'))
    k = j.get('encryptionKey')
    print('encryptionKey =', k)
    return k


def convert_dir(src_dir, dst_dir, key_hex, mode):
    key = _key(key_hex)
    src_ext = '.png' if mode == 'encrypt' else '.rpgmvp'
    dst_ext = '.rpgmvp' if mode == 'encrypt' else '.png'
    fn_conv = encrypt_png_bytes if mode == 'encrypt' else decrypt_rpgmvp_bytes
    n = 0
    for root, _, files in os.walk(src_dir):
        for fn in files:
            if not fn.lower().endswith(src_ext):
                continue
            rel = os.path.relpath(os.path.join(root, fn), src_dir)
            dst = os.path.join(dst_dir, os.path.splitext(rel)[0] + dst_ext)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            data = open(os.path.join(root, fn), 'rb').read()
            open(dst, 'wb').write(fn_conv(data, key))
            n += 1
    print('%s %d 个文件 → %s' % (mode, n, dst_dir))


def main():
    a = sys.argv
    if len(a) >= 3 and a[1] == 'key':
        read_key(a[2])
    elif len(a) >= 5 and a[1] in ('encrypt', 'decrypt'):
        convert_dir(a[2], a[3], a[4], a[1])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
