# -*- coding: utf-8 -*-
"""v2 二维码生成：用于分享海报

设计稿 5.3 特性 C：
- 二维码载荷为"重测数据摘要 + 版本号"，不包含个人信息
- 用户扫码后会看到"重测入口"提示，而不是下载链接
"""

from __future__ import annotations

import json
import zlib


def build_payload(summary: dict, version: str = "2.0") -> str:
    """构建海报二维码的载荷字符串

    Args:
        summary: {
            "score": int,
            "grade": str,
            "target_count": int,
            "category": str,
        }
        version: NetDiag 版本号

    Returns:
        紧凑的字符串（~50 字符），适合二维码
    """
    payload = {
        "v": version,
        "s": summary.get("score", 0),
        "g": summary.get("grade", "?"),
        "n": summary.get("target_count", 0),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 简单压缩（可选）：base64 编码 zlib 压缩结果
    compressed = zlib.compress(raw.encode("utf-8"))
    return compressed.hex()


def render_qr(payload: str, size: int = 240) -> "PIL.Image.Image | None":
    """渲染二维码到 PIL Image

    Returns:
        PIL.Image.Image 或 None（qrcode 库未安装时）

    失败安全：如果 qrcode 库缺失，返回 None，海报用占位符代替
    """
    try:
        import qrcode
        from qrcode.image.pil import PilImage
    except ImportError:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0A0E1A", back_color="#FFFFFF", image_factory=PilImage)
    # 调整尺寸
    if size and img.size[0] != size:
        img = img.resize((size, size), None)
    return img


def is_available() -> bool:
    """检查 qrcode 库是否可用"""
    try:
        import qrcode  # noqa
        return True
    except ImportError:
        return False