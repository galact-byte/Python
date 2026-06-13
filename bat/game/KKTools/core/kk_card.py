"""恋活 (Koikatu / KK) 与 恋活日光浴 (Koikatu Sunshine / KKS) 角色卡解析内核。

这是整个工具的地基。所有上层模块（编辑、浏览、分享、缺失检测）都依赖这里。

卡片文件本质是一张 PNG 图片，尾部追加了二进制数据块，布局如下::

    [缩略图 PNG]            标准 PNG，到 IEND 块为止，游戏列表里显示的小图
    int32   productNo       产品号 (恋活通常是 100)
    string  marker          标识串，如 "【KoiKatuChara】" / "【KoiKatuCharaSun】"
    string  version         卡片版本，如 "0.0.0"
    int32   faceLength      脸图 PNG 长度
    [脸图 PNG]              角色立绘 / 大图
    int32   lstInfoLength   块索引长度
    [lstInfo]               MessagePack: {"lstInfo": [{name, version, pos, size}, ...]}
    int64   dataLength      数据区总长度
    [data]                  各数据块拼接，block = data[pos : pos+size]，本身也是 MessagePack

其中 string 采用 C# BinaryWriter 的写法：7-bit 变长整数前缀 + UTF-8 字节。

设计原则（与参考工具「低风险字段安全写回」一致）：
- 读取时把每个块的原始字节都留着；
- 写回时只重新序列化被编辑过的 Parameter 块，其余块字节级原样保留；
- 默认另存为新卡，覆盖前自动备份。

格式参考：great-majority/KoikatuCharaLoader 社区文档与游戏存档实现。
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from pathlib import Path

import msgpack

# ---- 已知 marker 与对应游戏 -------------------------------------------------

# marker -> (游戏代号, 友好名)
KNOWN_MARKERS = {
    "【KoiKatuChara】": ("KK", "Koikatu / 恋活"),
    "【KoiKatuCharaSP】": ("KK", "Koikatu Party / 恋活派对"),
    "【KoiKatuCharaSun】": ("KKS", "Koikatu Sunshine / 恋活日光浴"),
    "【EmCretraChara】": ("EC", "Emotion Creators"),
}

# 服装卡（coordinate）标识
COORDINATE_MARKERS = {
    "【KoiKatuClothes】": ("KK", "服装卡"),
    "【KoiKatuClothesSun】": ("KKS", "服装卡"),
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class KKCardError(Exception):
    """卡片解析相关的统一异常。"""


# ---- C# BinaryWriter 风格的二进制读写辅助 ---------------------------------


class _Reader:
    """对外部输入保持不信任：所有读取都做边界检查。"""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _need(self, n: int) -> None:
        if self.pos + n > len(self.data):
            raise KKCardError(
                f"数据越界：位置 {self.pos} 需要 {n} 字节，但只剩 {len(self.data) - self.pos} 字节"
            )

    def read(self, n: int) -> bytes:
        self._need(n)
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def read_int32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_int64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def read_7bit_int(self) -> int:
        """C# BinaryReader.Read7BitEncodedInt 的等价实现。"""
        result = 0
        shift = 0
        while True:
            self._need(1)
            byte = self.data[self.pos]
            self.pos += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
            if shift > 35:
                raise KKCardError("7-bit 变长整数过长，文件可能损坏")
        return result

    def read_cs_string(self) -> str:
        length = self.read_7bit_int()
        return self.read(length).decode("utf-8", errors="replace")


def write_7bit_int(value: int) -> bytes:
    """C# BinaryWriter.Write7BitEncodedInt 的等价实现。"""
    if value < 0:
        raise ValueError("7-bit 编码不支持负数")
    out = bytearray()
    v = value
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)
    return bytes(out)


def write_cs_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return write_7bit_int(len(raw)) + raw


def png_data_length(data: bytes, start: int = 0) -> int:
    """从 start 处开始解析一张 PNG，返回这张 PNG 的总字节长度（含签名到 IEND CRC）。

    通过遍历 PNG chunk 实现，比"搜索 IEND 字节"更可靠——避免脸图数据里
    恰好出现 IEND 字节序列造成误判。
    """
    if data[start : start + 8] != PNG_SIGNATURE:
        raise KKCardError(f"位置 {start} 不是合法的 PNG 签名，文件可能不是角色卡")
    pos = start + 8
    while True:
        if pos + 8 > len(data):
            raise KKCardError("PNG 数据不完整：缺少 chunk 头")
        chunk_len = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        # chunk = 4字节长度 + 4字节类型 + 数据 + 4字节CRC
        pos += 8 + chunk_len + 4
        if chunk_type == b"IEND":
            break
        if pos > len(data):
            raise KKCardError("PNG 数据不完整：chunk 长度越界")
    return pos - start


# ---- 块索引结构 ------------------------------------------------------------


@dataclass
class BlockInfo:
    name: str
    version: str
    pos: int
    size: int


@dataclass
class KoikatuCard:
    """一张已解析的恋活 / 恋活日光浴 角色卡。"""

    path: str | None = None
    thumbnail: bytes = b""          # 列表缩略图 PNG
    face: bytes = b""               # 角色大图 / 立绘 PNG
    product_no: int = 100
    marker: str = "【KoiKatuChara】"
    version: str = "0.0.0"
    blocks: dict[str, bytes] = field(default_factory=dict)   # name -> 原始字节
    block_order: list[BlockInfo] = field(default_factory=list)

    # 原始尾部段，用于"未改动即字节级原样吐回"。一旦有块被改写，_dirty 置真，转入重建路径。
    _lstinfo_raw: bytes = field(default=b"", repr=False)
    _data_blob: bytes = field(default=b"", repr=False)
    _dirty: bool = field(default=False, repr=False)

    # ---- 派生信息 ----

    @property
    def game(self) -> str:
        return KNOWN_MARKERS.get(self.marker, ("?", "未知"))[0]

    @property
    def game_name(self) -> str:
        return KNOWN_MARKERS.get(self.marker, ("?", "未知格式"))[1]

    @property
    def block_names(self) -> list[str]:
        return [b.name for b in self.block_order]

    # ---- 解析 ----

    @classmethod
    def load(cls, path: str | Path) -> "KoikatuCard":
        path = Path(path)
        data = path.read_bytes()
        card = cls.from_bytes(data)
        card.path = str(path)
        return card

    @classmethod
    def from_bytes(cls, data: bytes) -> "KoikatuCard":
        if data[:8] != PNG_SIGNATURE:
            raise KKCardError("文件开头不是 PNG，不是合法的角色卡")

        thumb_len = png_data_length(data, 0)
        thumbnail = data[:thumb_len]

        r = _Reader(data)
        r.pos = thumb_len

        product_no = r.read_int32()
        marker = r.read_cs_string()
        if marker not in KNOWN_MARKERS:
            # 不直接报错——可能是带 mod 的新格式，给出明确提示但仍尝试继续
            if not marker.startswith("【"):
                raise KKCardError(
                    f"未识别的卡片标识 {marker!r}，这可能不是角色卡（也许是场景卡或服装卡）"
                )
        version = r.read_cs_string()

        face_len = r.read_int32()
        if face_len < 0:
            raise KKCardError("脸图长度异常，文件可能损坏")
        face = r.read(face_len)

        lstinfo_len = r.read_int32()
        lstinfo_raw = r.read(lstinfo_len)
        try:
            lstinfo = msgpack.unpackb(lstinfo_raw, raw=False, strict_map_key=False)
        except Exception as exc:  # noqa: BLE001 - 转成统一异常向上抛
            raise KKCardError(f"块索引 (lstInfo) 解析失败：{exc}") from exc

        data_len = r.read_int64()
        data_blob = r.read(data_len)

        block_order: list[BlockInfo] = []
        blocks: dict[str, bytes] = {}
        for info in lstinfo.get("lstInfo", {}).values() if isinstance(
            lstinfo.get("lstInfo"), dict
        ) else lstinfo.get("lstInfo", []):
            bi = BlockInfo(
                name=info["name"],
                version=info.get("version", "0.0.0"),
                pos=int(info["pos"]),
                size=int(info["size"]),
            )
            block_order.append(bi)
            blocks[bi.name] = data_blob[bi.pos : bi.pos + bi.size]

        return cls(
            thumbnail=thumbnail,
            face=face,
            product_no=product_no,
            marker=marker,
            version=version,
            blocks=blocks,
            block_order=block_order,
            _lstinfo_raw=lstinfo_raw,
            _data_blob=data_blob,
            _dirty=False,
        )

    # ---- 块级访问 ----

    def get_block_dict(self, name: str) -> dict | None:
        """把指定块解码成 Python 字典（块本身是 MessagePack）。

        优先按 UTF-8 解码字符串（Parameter/About 等文本块）；遇到像 Custom
        这种内含二进制（嵌套捏脸数据）的块会触发 UnicodeDecodeError，则退回
        raw=True 保留原始字节，保证永不让上层崩溃。
        """
        raw = self.blocks.get(name)
        if raw is None:
            return None

        def _stream_first(raw_mode: bool):
            up = msgpack.Unpacker(raw=raw_mode, strict_map_key=False)
            up.feed(raw)
            return next(iter(up))

        last_exc: Exception | None = None
        # 依次尝试：utf8单段 -> 二进制单段 -> utf8多段 -> 二进制多段。
        # Parameter/About 走第一档；Custom 这类多段二进制走到最后一档。
        for raw_mode in (False, True):
            try:
                return msgpack.unpackb(raw, raw=raw_mode, strict_map_key=False)
            except UnicodeDecodeError as exc:
                last_exc = exc
                continue  # 文本解码不了，换二进制
            except msgpack.exceptions.ExtraData as exc:
                last_exc = exc
                try:
                    return _stream_first(raw_mode)   # 多段：取第一段
                except UnicodeDecodeError:
                    continue
                except Exception as e2:  # noqa: BLE001
                    last_exc = e2
                    continue
            except Exception as exc:  # noqa: BLE001
                raise KKCardError(f"块 {name} 解码失败：{exc}") from exc
        # 兜底：二进制流式取第一段
        try:
            return _stream_first(True)
        except Exception as exc:  # noqa: BLE001
            raise KKCardError(f"块 {name} 解码失败：{last_exc or exc}") from (last_exc or exc)

    def set_block_dict(self, name: str, value: dict) -> None:
        """把字典重新序列化并替换对应块（仅在内存中，save 时落盘）。"""
        if name not in self.blocks:
            raise KKCardError(f"卡片中不存在块 {name}，拒绝写入未知块")
        self.blocks[name] = msgpack.packb(value, use_bin_type=True)
        self._dirty = True

    # 便捷属性：Parameter 块承载了绝大多数人类可读字段
    @property
    def parameter(self) -> dict | None:
        return self.get_block_dict("Parameter")

    def update_parameter(self, updates: dict) -> None:
        """只更新 Parameter 中已存在的字段，未知字段忽略，避免破坏卡片。"""
        param = self.get_block_dict("Parameter")
        if param is None:
            raise KKCardError("该卡片没有 Parameter 块，无法编辑基本信息")
        for key, val in updates.items():
            if key in param:
                param[key] = val
        self.set_block_dict("Parameter", param)

    # ---- 序列化 / 保存 ----

    def to_bytes(self) -> bytes:
        """重建整张卡片。

        未编辑过任何块时（_dirty=False），数据区与块索引**原样字节吐回**，
        保证读进来再存出去与原文件完全一致——这是"安全写回"的底线保证。
        （缩略图/脸图等头部字段即便被换过，也只影响头部，尾部仍原样。）

        编辑过块时，按**物理顺序**（原始 pos 升序）重排数据区，块索引保持原始
        逻辑顺序、仅更新 pos/size。这样既能反映改动，又把布局扰动降到最低。
        """
        if not self._dirty:
            lstinfo_raw = self._lstinfo_raw
            data_blob: bytes = self._data_blob
        else:
            ordered = sorted(self.block_order, key=lambda b: b.pos)
            buf = bytearray()
            new_pos: dict[str, int] = {}
            for bi in ordered:
                new_pos[bi.name] = len(buf)
                buf.extend(self.blocks[bi.name])
            data_blob = bytes(buf)
            lstinfo = {
                "lstInfo": [
                    {
                        "name": bi.name,
                        "version": bi.version,
                        "pos": new_pos[bi.name],
                        "size": len(self.blocks[bi.name]),
                    }
                    for bi in self.block_order
                ]
            }
            lstinfo_raw = msgpack.packb(lstinfo, use_bin_type=True)

        out = io.BytesIO()
        out.write(self.thumbnail)
        out.write(struct.pack("<i", self.product_no))
        out.write(write_cs_string(self.marker))
        out.write(write_cs_string(self.version))
        out.write(struct.pack("<i", len(self.face)))
        out.write(self.face)
        out.write(struct.pack("<i", len(lstinfo_raw)))
        out.write(lstinfo_raw)
        out.write(struct.pack("<q", len(data_blob)))
        out.write(data_blob)
        return out.getvalue()

    def save(self, out_path: str | Path, *, backup: bool = True) -> str:
        """保存卡片。若目标已存在且 backup=True，覆盖前自动备份为 .bak。"""
        out_path = Path(out_path)
        if out_path.exists() and backup:
            bak = out_path.with_suffix(out_path.suffix + ".bak")
            idx = 1
            while bak.exists():
                bak = out_path.with_suffix(out_path.suffix + f".bak{idx}")
                idx += 1
            bak.write_bytes(out_path.read_bytes())
        out_path.write_bytes(self.to_bytes())
        return str(out_path)

    def set_thumbnail_from_png(self, png_bytes: bytes) -> None:
        """更换列表缩略图（要求是合法 PNG）。"""
        if png_bytes[:8] != PNG_SIGNATURE:
            raise KKCardError("提供的预览图不是合法 PNG")
        # 校验能完整解析，避免写入半张图
        png_data_length(png_bytes, 0)
        self.thumbnail = png_bytes


def peek_header(data: bytes) -> tuple[str | None, int | None]:
    """轻量读取卡片头部，返回 (marker, productNo)。非卡片返回 (None, None)。"""
    if data[:8] != PNG_SIGNATURE:
        return None, None
    try:
        thumb_len = png_data_length(data, 0)
    except KKCardError:
        return None, None
    r = _Reader(data)
    r.pos = thumb_len
    try:
        pn = r.read_int32()
        marker = r.read_cs_string()
    except KKCardError:
        return None, None
    return marker, pn


def classify(data: bytes) -> tuple[str, str, str]:
    """判别卡片类型，返回 (类型, 游戏, marker)。

    类型 ∈ {character(角色卡), coordinate(服装卡), scene(场景卡), other(其它)}。
    """
    marker, _ = peek_header(data)
    if marker in KNOWN_MARKERS:
        return ("character", KNOWN_MARKERS[marker][0], marker)
    if marker in COORDINATE_MARKERS:
        return ("coordinate", COORDINATE_MARKERS[marker][0], marker)
    # 场景卡：头部不是卡片布局，但内嵌角色数据或带 Studio 标记
    if data[:8] == PNG_SIGNATURE:
        tail = data[8:] if len(data) > 8 else b""
        if b"KStudio" in data or b"KoiKatuChara" in tail or b"KoiKatuCharaSun" in tail:
            return ("scene", "?", marker or "")
    return ("other", "?", marker or "")


def extract_mod_ids(card: "KoikatuCard") -> dict[str, int]:
    """从角色卡的 Sideloader UAR 扩展数据提取所依赖的 mod ModID（对应 manifest guid）。

    返回 {ModID: 出现次数}。无依赖或非角色卡返回空字典。
    路径：KKEx 块 -> "com.bepis.sideloader.universalautoresolver" -> [ver, {"info": [blob...]}]
    每个 blob 再 msgpack 解出 {"ModID": ...}。
    """
    out: dict[str, int] = {}
    if "KKEx" not in card.blocks:
        return out
    try:
        kkex = card.get_block_dict("KKEx")
    except KKCardError:
        return out
    if not isinstance(kkex, dict):
        return out
    uar = kkex.get("com.bepis.sideloader.universalautoresolver")
    if not isinstance(uar, (list, tuple)) or len(uar) < 2:
        return out
    payload = uar[1]
    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, (list, tuple)):
        return out
    for blob in info:
        if not isinstance(blob, (bytes, bytearray)):
            continue
        try:
            d = msgpack.unpackb(blob, raw=False, strict_map_key=False)
        except Exception:  # noqa: BLE001 - 单条坏数据跳过，不影响整体
            continue
        if isinstance(d, dict):
            mid = d.get("ModID")
            if isinstance(mid, str) and mid:
                out[mid] = out.get(mid, 0) + 1
    return out


def is_character_card(data: bytes) -> bool:
    """快速判断一段字节是否像恋活角色卡（不做完整解析）。"""
    if data[:8] != PNG_SIGNATURE:
        return False
    try:
        thumb_len = png_data_length(data, 0)
    except KKCardError:
        return False
    r = _Reader(data)
    r.pos = thumb_len
    try:
        r.read_int32()  # product_no
        marker = r.read_cs_string()
    except KKCardError:
        return False
    return marker in KNOWN_MARKERS
