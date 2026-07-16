"""Save and load Pose objects as JSON files (``.pose.json``).

The on-disk format is intentionally simple and forward-compatible:

    {
      "version": 1,
      "canvas": {"width": 512, "height": 512},
      "style": {
        "background": "black",
        "foreground": "white",
        "line_width": 12.0,
        "head_radius_default": 30.0,
        "joint_radius_default": 5.0
      },
      "heads": [{"x": ..., "y": ..., "radius": ...}, ...],
      "segments": [{"x1": ..., "y1": ..., "x2": ..., "y2": ...}, ...],
      "joints": [{"x": ..., "y": ..., "radius": ...}, ...]
    }
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .model import Pose, Head, Segment, Joint, Style


SCHEMA_VERSION = 1


def to_dict(pose: Pose, canvas_width: int, canvas_height: int) -> Dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "canvas": {"width": int(canvas_width), "height": int(canvas_height)},
        "style": {
            "background": pose.style.background,
            "foreground": pose.style.foreground,
            "line_width": float(pose.style.line_width),
            "head_radius_default": float(pose.style.head_radius_default),
            "joint_radius_default": float(pose.style.joint_radius_default),
        },
        "heads": [{"x": h.x, "y": h.y, "radius": h.radius} for h in pose.heads],
        "segments": [
            {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2} for s in pose.segments
        ],
        "joints": [{"x": j.x, "y": j.y, "radius": j.radius} for j in pose.joints],
    }


def from_dict(data: Dict[str, Any]) -> tuple[Pose, int, int]:
    """Parse a dict produced by :func:`to_dict`.

    Returns ``(pose, canvas_width, canvas_height)``. Unknown top-level keys
    are silently ignored for forward compatibility.
    """
    version = int(data.get("version", SCHEMA_VERSION))
    if version > SCHEMA_VERSION:
        # We can still try to read it; just note it.
        # (Real migrations would go here.)
        pass

    canvas = data.get("canvas", {}) or {}
    width = int(canvas.get("width", 512))
    height = int(canvas.get("height", 512))

    style_data = data.get("style", {}) or {}
    style = Style(
        background=str(style_data.get("background", "black")),
        foreground=str(style_data.get("foreground", "white")),
        line_width=float(style_data.get("line_width", 12.0)),
        head_radius_default=float(style_data.get("head_radius_default", 30.0)),
        joint_radius_default=float(style_data.get("joint_radius_default", 5.0)),
    )

    heads = [Head(h["x"], h["y"], h.get("radius", style.head_radius_default))
             for h in data.get("heads", [])]
    segments = [Segment(s["x1"], s["y1"], s["x2"], s["y2"])
                for s in data.get("segments", [])]
    joints = [Joint(j["x"], j["y"], j.get("radius", style.joint_radius_default))
              for j in data.get("joints", [])]

    pose = Pose(heads=heads, segments=segments, joints=joints, style=style)
    return pose, width, height


def save(pose: Pose, canvas_width: int, canvas_height: int, path: str) -> str:
    """Write the pose to ``path`` as JSON. Returns the absolute path."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_dict(pose, canvas_width, canvas_height), f, indent=2)
        f.write("\n")
    return path


def load(path: str) -> tuple[Pose, int, int]:
    """Read a pose from ``path``. See :func:`from_dict` for the return shape."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return from_dict(data)