# -*- coding: utf-8 -*-
"""v2 分享海报生成：Pillow 绘制

设计稿 5.3 特性 C：
- 1080×1920 竖版（朋友圈/抖音）+ 1080×1080 方版（微信群）
- 顶部 Logo + 综合评分大数字
- 中部 雷达图 + 分类明细
- 底部 测试时间 + 二维码
- 海报不包含本机 IP/MAC/机器名、运营商账号信息
"""

from __future__ import annotations

import os
from datetime import datetime

from .qrcode import render_qr, build_payload


def _font(size: int):
    """加载中文字体（按优先级查找）"""
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"/System/Library/Fonts/PingFang.ttc",
        r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    try:
        from PIL import ImageFont
        for p in font_paths:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()
    except Exception:
        return None


# 配色（与 src/ui/web/style.css 保持一致）
COLORS = {
    "bg": (10, 14, 26),          # #0A0E1A
    "bg_elevated": (19, 26, 44), # #131A2C
    "line": (37, 47, 74),        # #252F4A
    "accent_cyan": (0, 229, 255),   # #00E5FF
    "accent_violet": (139, 92, 246), # #8B5CF6
    "accent_magenta": (255, 61, 154), # #FF3D9A
    "text_primary": (232, 236, 244), # #E8ECF4
    "text_secondary": (139, 149, 181), # #8B95B5
    "status_good": (0, 255, 159),  # #00FF9F
    "status_warn": (255, 184, 0),  # #FFB800
    "status_bad": (255, 61, 90),   # #FF3D5A
}


def generate_poster(
    overall: dict,
    targets: list,
    template: str = "square",
    output_path: str = None,
) -> str:
    """生成分享海报

    Args:
        overall: score_overall 的结果
        targets: [{"name": ..., "score": ..., "grade": ..., "metrics": ...}, ...]
        template: "square"(1080×1080) / "vertical"(1080×1920)
        output_path: 输出 PNG 路径，None 则用系统临时目录

    Returns:
        生成的 PNG 文件路径
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise RuntimeError("Pillow 未安装，无法生成海报")

    # 画布尺寸
    if template == "vertical":
        width, height = 1080, 1920
    else:
        width, height = 1080, 1080

    img = Image.new("RGB", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    # 字体
    f_huge = _font(120)     # 综合评分大数字
    f_title = _font(56)     # 标题
    f_subtitle = _font(36)  # 副标题
    f_body = _font(32)      # 正文
    f_small = _font(24)     # 辅助
    f_tiny = _font(20)      # 最小

    # 顶部渐变条（简化：用一个矩形代替）
    for i in range(8):
        alpha = int(255 * (1 - i / 8))
        y_start = i * 6
        y_end = (i + 1) * 6
        draw.rectangle([(0, y_start), (width, y_end)], fill=COLORS["accent_cyan"])

    # 顶部 Logo + 标题
    draw.text((60, 80), "NetDiag", fill=COLORS["accent_cyan"], font=f_title)
    draw.text((60, 150), "网络自检报告", fill=COLORS["text_primary"], font=f_subtitle)

    # 综合评分（中央大数字）
    score = overall.get("score", 0)
    grade = overall.get("grade", "—")
    label = overall.get("label", "")

    cx = width // 2
    # 评分数字
    score_text = f"{int(score)}"
    bbox = draw.textbbox((0, 0), score_text, font=f_huge)
    text_width = bbox[2] - bbox[0]
    draw.text(((cx - text_width // 2), 280), score_text, fill=COLORS["status_good"], font=f_huge)

    # 评分等级
    grade_text = f"分 · {grade}"
    bbox = draw.textbbox((0, 0), grade_text, font=f_subtitle)
    text_width = bbox[2] - bbox[0]
    draw.text(((cx - text_width // 2), 440), grade_text, fill=COLORS["text_primary"], font=f_subtitle)

    # 评语
    if label:
        bbox = draw.textbbox((0, 0), label, font=f_body)
        text_width = bbox[2] - bbox[0]
        draw.text(((cx - text_width // 2), 510), label, fill=COLORS["accent_violet"], font=f_body)

    # 分割线
    draw.line([(80, 580), (width - 80, 580)], fill=COLORS["line"], width=2)

    # 目标明细（前 6 个）
    draw.text((60, 620), "测试明细", fill=COLORS["text_secondary"], font=f_small)

    y = 680
    for i, t in enumerate(targets[:6]):
        if y > height - 240:
            break
        # 名称
        name = t.get("name", "")
        draw.text((60, y), name, fill=COLORS["text_primary"], font=f_body)

        # 状态色块
        score_v = t.get("score", 0)
        if score_v >= 80:
            status_color = COLORS["status_good"]
        elif score_v >= 60:
            status_color = COLORS["status_warn"]
        else:
            status_color = COLORS["status_bad"]

        # 评分（右对齐）
        score_text = f"{int(score_v)} {t.get('grade', '')}"
        bbox = draw.textbbox((0, 0), score_text, font=f_body)
        text_width = bbox[2] - bbox[0]
        draw.text((width - 80 - text_width, y), score_text, fill=status_color, font=f_body)

        # 状态条
        bar_x = 60
        bar_y = y + 50
        bar_w = width - 120
        # 背景条
        draw.rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], fill=COLORS["bg_elevated"])
        # 进度条
        progress_w = int(bar_w * min(100, max(0, score_v)) / 100)
        draw.rectangle([(bar_x, bar_y), (bar_x + progress_w, bar_y + 8)], fill=status_color)

        y += 90

    # 二维码（右下角）
    qr_payload = build_payload({
        "score": int(score),
        "grade": grade,
        "target_count": len(targets),
    })
    qr_img = render_qr(qr_payload, size=180)
    if qr_img is not None:
        qr_x = width - 240
        qr_y = height - 240
        img.paste(qr_img, (qr_x, qr_y))
        # 二维码说明
        draw.text((60, qr_y + 60), "扫码重测", fill=COLORS["text_secondary"], font=f_small)
    else:
        draw.text((60, height - 180), "扫码重测 (二维码需要 qrcode 库)",
                  fill=COLORS["text_secondary"], font=f_small)

    # 底部时间戳 + 签名
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.text((60, height - 80), timestamp, fill=COLORS["text_secondary"], font=f_tiny)
    draw.text((60, height - 50), "NetDiag v2.0 · 浅木·先生", fill=COLORS["text_secondary"], font=f_tiny)

    # 保存
    if not output_path:
        os.makedirs(os.path.join(os.path.expanduser("~"), "NetDiagPosters"), exist_ok=True)
        output_path = os.path.join(
            os.path.expanduser("~"),
            "NetDiagPosters",
            f"netdiag-poster-{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
        )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    return output_path


def generate_summary_text(overall: dict, targets: list) -> str:
    """生成纯文本结果（用于微信复制）"""
    lines = []
    lines.append("┏━━━━━━━━━━━━━━━━━━━━━━━━┓")
    lines.append("┃  📊 NetDiag 网络体检     ┃")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━┛")
    lines.append("")
    lines.append(f"综合评分：{int(overall.get('score', 0))} 分 · {overall.get('grade', '—')}")
    lines.append(f"状态：{overall.get('label', '')}")
    lines.append("")
    lines.append("【测试明细】")
    for t in targets[:6]:
        name = t.get("name", "")
        score = t.get("score", 0)
        grade = t.get("grade", "")
        metrics = t.get("metrics", {})
        latency = metrics.get("avg_latency_ms")
        loss = metrics.get("loss_pct")
        extra = ""
        if latency is not None:
            extra += f" {int(latency)}ms"
        if loss:
            extra += f" 丢包{loss:.1f}%"
        lines.append(f"  • {name}：{int(score)}{grade}{extra}")
    lines.append("")
    lines.append(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("NetDiag v2.0 · 浅木·先生")
    return "\n".join(lines)