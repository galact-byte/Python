"""解包 / 打包 / 隐写伪装 / 分卷。

伪装原理（经典手法）：把 zip 压缩包**追加在一个真实载体文件（视频/图片）之后**。
得到的文件既能被播放器/看图器当作正常媒体打开，又能被解压软件识别为 zip——因为
zip 的目录信息在文件末尾，解压器从尾部定位，能容忍前面的"垃圾"前缀。

Python 的 zipfile 本身就支持带前缀的 zip（自解压 exe 同理），故解包时直接用
zipfile 打开伪装文件即可，无需手动剥离载体。
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Callable, Iterable

try:
    import pyzipper
    HAVE_PYZIPPER = True
except ImportError:  # 未装则仅支持不加密打包/解包
    HAVE_PYZIPPER = False

ProgressCb = Callable[[int, int, str], None]  # (当前, 总数, 描述)


def pack_folder(
    folder: str | Path,
    out_zip: str | Path,
    *,
    compress: bool = True,
    password: str | None = None,
    progress: ProgressCb | None = None,
) -> str:
    """把文件夹打包成 zip。给 password 则用 AES-256 加密（需 pyzipper）。返回输出路径。"""
    folder = Path(folder)
    out_zip = Path(out_zip)
    files = [p for p in folder.rglob("*") if p.is_file()]
    total = len(files)
    if password:
        if not HAVE_PYZIPPER:
            raise RuntimeError("加密打包需要 pyzipper，请先安装：pip install pyzipper")
        with pyzipper.AESZipFile(
            out_zip, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as zf:
            zf.setpassword(password.encode("utf-8"))
            for i, p in enumerate(files, 1):
                zf.write(p, p.relative_to(folder).as_posix())
                if progress:
                    progress(i, total, p.name)
    else:
        mode = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
        with zipfile.ZipFile(out_zip, "w", mode) as zf:
            for i, p in enumerate(files, 1):
                zf.write(p, p.relative_to(folder).as_posix())
                if progress:
                    progress(i, total, p.name)
    return str(out_zip)


def disguise(carrier: str | Path, payload_zip: str | Path, out_path: str | Path) -> str:
    """把 payload_zip 追加到 carrier 之后，生成伪装文件。"""
    carrier = Path(carrier)
    payload_zip = Path(payload_zip)
    out_path = Path(out_path)
    with open(out_path, "wb") as out:
        out.write(carrier.read_bytes())
        out.write(payload_zip.read_bytes())
    return str(out_path)


def pack_and_disguise(
    folder: str | Path,
    carrier: str | Path,
    out_path: str | Path,
    *,
    password: str | None = None,
    progress: ProgressCb | None = None,
) -> str:
    """打包文件夹并伪装成载体文件，一步到位。给 password 则 AES 加密。"""
    out_path = Path(out_path)
    tmp_zip = out_path.with_suffix(out_path.suffix + ".tmp.zip")
    try:
        pack_folder(folder, tmp_zip, password=password, progress=progress)
        disguise(carrier, tmp_zip, out_path)
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()
    return str(out_path)


def looks_like_zip(path: str | Path) -> bool:
    """文件能否被当作 zip 打开（含伪装在载体之后的 zip）。

    只校验目录结构是否可读（轻量），不做 testzip 全量 CRC 校验——后者会读完
    整个文件，伪装视频可能上 GB，会非常慢。
    """
    try:
        with zipfile.ZipFile(path) as zf:
            zf.namelist()
        return True
    except (zipfile.BadZipFile, OSError):
        return False


def extract_archive(
    path: str | Path,
    out_dir: str | Path,
    *,
    passwords: list[str] | None = None,
    progress: ProgressCb | None = None,
) -> list[str]:
    """解包 zip（含伪装在载体后的 zip，含 AES 加密）。

    passwords 给定时依次尝试解密（先尝试无密码=未加密包）。返回解出的文件相对路径列表。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    zf_cls = pyzipper.AESZipFile if HAVE_PYZIPPER else zipfile.ZipFile
    candidates: list[str | None] = [None] + [p for p in (passwords or []) if p]
    last_err: Exception | None = None
    for pw in candidates:
        try:
            with zf_cls(path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                if pw:
                    zf.setpassword(pw.encode("utf-8"))
                # 先试读第一个文件验证密码，避免错误密码下产生半套文件
                if names:
                    with zf.open(names[0]) as f:
                        f.read(1)
                extracted: list[str] = []
                total = len(names)
                for i, name in enumerate(names, 1):
                    zf.extract(name, out_dir)
                    extracted.append(name)
                    if progress:
                        progress(i, total, name)
                return extracted
        except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
            last_err = exc
            continue
    raise last_err or RuntimeError("解压失败：可能需要正确的密码")



def split_file(
    path: str | Path,
    chunk_size_mb: float,
    out_dir: str | Path | None = None,
) -> list[str]:
    """把文件分卷为 name.001 / name.002 ...，返回分卷路径列表。"""
    path = Path(path)
    out_dir = Path(out_dir) if out_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    chunk = int(chunk_size_mb * 1024 * 1024)
    if chunk <= 0:
        raise ValueError("分卷大小必须大于 0")
    parts: list[str] = []
    with open(path, "rb") as f:
        idx = 1
        while True:
            data = f.read(chunk)
            if not data:
                break
            part = out_dir / f"{path.name}.{idx:03d}"
            part.write_bytes(data)
            parts.append(str(part))
            idx += 1
    return parts


def join_parts(first_part: str | Path, out_path: str | Path) -> str:
    """把 name.001 / name.002 ... 合并回原文件。传入 .001 分卷路径。"""
    first_part = Path(first_part)
    stem = first_part.with_suffix("")  # 去掉 .001
    out_path = Path(out_path)
    parts = sorted(stem.parent.glob(stem.name + ".[0-9][0-9][0-9]"))
    if not parts:
        raise FileNotFoundError("未找到分卷文件")
    with open(out_path, "wb") as out:
        for p in parts:
            out.write(p.read_bytes())
    return str(out_path)
