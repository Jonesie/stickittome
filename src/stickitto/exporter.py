"""Rasterize a Pose to PNG/JPG via Pillow.

The exporter draws heads, joints, and line segments with rounded end caps so
the output looks clean when fed into ComfyUI ControlNet (OpenPose / DWPose).
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw

from .model import Pose


def render_pose(
    pose: Pose,
    width: int,
    height: int,
    *,
    background: Optional[str] = None,
    foreground: Optional[str] = None,
    line_width: Optional[float] = None,
    head_radius: Optional[float] = None,
    joint_radius: Optional[float] = None,
) -> Image.Image:
    """Render ``pose`` to an RGB ``PIL.Image`` of the given size.

    Any style parameter that is ``None`` falls back to ``pose.style``.
    """
    bg = background or pose.style.background
    fg = foreground or pose.style.foreground
    lw = float(line_width if line_width is not None else pose.style.line_width)
    hr = float(head_radius if head_radius is not None else pose.style.head_radius_default)
    jr = float(joint_radius if joint_radius is not None else pose.style.joint_radius_default)

    img = Image.new("RGB", (int(width), int(height)), bg)
    draw = ImageDraw.Draw(img)

    # Line width of <1 in PIL is treated as 1. Guard against zero/negative.
    pil_lw = max(1, int(round(lw)))

    # Segments: draw line plus round caps so joints look natural.
    cap_r = lw / 2.0
    for seg in pose.segments:
        draw.line([seg.x1, seg.y1, seg.x2, seg.y2], fill=fg, width=pil_lw)
        if cap_r > 0:
            _filled_circle(draw, seg.x1, seg.y1, cap_r, fg)
            _filled_circle(draw, seg.x2, seg.y2, cap_r, fg)

    # Heads: filled circles.
    for head in pose.heads:
        _filled_circle(draw, head.x, head.y, head.radius, fg)

    # Joints: small filled dots.
    for joint in pose.joints:
        _filled_circle(draw, joint.x, joint.y, joint.radius, fg)

    return img


def _filled_circle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color) -> None:
    """Draw an anti-aliased filled circle."""
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, fill=color)


def export_png(
    pose: Pose,
    width: int,
    height: int,
    path: str,
    **kwargs,
) -> str:
    """Render the pose and save it as a PNG. Returns the absolute path."""
    img = render_pose(pose, width, height, **kwargs)
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path, format="PNG", optimize=True)
    return path


def export_jpg(
    pose: Pose,
    width: int,
    height: int,
    path: str,
    quality: int = 95,
    **kwargs,
) -> str:
    """Render the pose and save it as a JPG. Returns the absolute path."""
    img = render_pose(pose, width, height, **kwargs)
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path, format="JPEG", quality=quality, optimize=True)
    return path


def export_image(
    pose: Pose,
    width: int,
    height: int,
    path: str,
    **kwargs,
) -> str:
    """Save the pose, choosing PNG or JPG by file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        return export_jpg(pose, width, height, path, **kwargs)
    return export_png(pose, width, height, path, **kwargs)