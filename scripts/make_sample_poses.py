#!/usr/bin/env python3
"""Generate a handful of sample poses and render them to PNG.

Useful as:
  * a smoke test for the exporter
  * example poses for the README / examples/ folder
  * a starting point if you want to script poses instead of drawing them

Run from the repo root:

    python scripts/make_sample_poses.py

Outputs are written to ``examples/sample_poses/``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make ``import stickitto`` work without installing.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from stickitto import io_json  # noqa: E402
from stickitto.exporter import export_png  # noqa: E402
from stickitto.model import Pose, Style  # noqa: E402


def standing_pose(width: int, height: int) -> Pose:
    """A neutral standing stick figure, centred in the canvas."""
    cx = width // 2
    head_y = int(height * 0.18)
    hip_y = int(height * 0.55)
    knee_y = int(height * 0.78)
    foot_y = int(height * 0.95)
    shoulder_y = int(height * 0.30)
    elbow_y = int(height * 0.42)
    hand_y = int(height * 0.55)
    shoulder_offset = int(width * 0.10)
    hip_offset = int(width * 0.06)

    pose = Pose(style=Style(background="black", foreground="white",
                            line_width=12, head_radius_default=30))
    pose.add_head(cx, head_y)
    pose.add_segment(cx, head_y + 30, cx, hip_y)            # torso
    pose.add_segment(cx, shoulder_y, cx - shoulder_offset, elbow_y)  # L upper arm
    pose.add_segment(cx - shoulder_offset, elbow_y, cx - shoulder_offset - 5, hand_y)  # L forearm
    pose.add_segment(cx, shoulder_y, cx + shoulder_offset, elbow_y)  # R upper arm
    pose.add_segment(cx + shoulder_offset, elbow_y, cx + shoulder_offset + 5, hand_y)  # R forearm
    pose.add_segment(cx, hip_y, cx - hip_offset, knee_y)   # L thigh
    pose.add_segment(cx - hip_offset, knee_y, cx - hip_offset + 5, foot_y)  # L shin
    pose.add_segment(cx, hip_y, cx + hip_offset, knee_y)   # R thigh
    pose.add_segment(cx + hip_offset, knee_y, cx + hip_offset - 5, foot_y)  # R shin

    pose.add_joint(cx, shoulder_y)  # neck
    pose.add_joint(cx, hip_y)       # pelvis
    pose.add_joint(cx - shoulder_offset, elbow_y)
    pose.add_joint(cx + shoulder_offset, elbow_y)
    pose.add_joint(cx - hip_offset, knee_y)
    pose.add_joint(cx + hip_offset, knee_y)
    return pose


def walking_pose(width: int, height: int) -> Pose:
    """A simple walking pose — opposite arm/leg forward."""
    cx = width // 2
    head_y = int(height * 0.18)
    hip_y = int(height * 0.55)
    pose = Pose(style=Style(background="black", foreground="white",
                            line_width=12, head_radius_default=28))
    pose.add_head(cx, head_y)
    # torso leaning slightly forward
    pose.add_segment(cx, head_y + 28, cx + 20, hip_y)
    # left arm forward
    pose.add_segment(cx + 5, int(height * 0.30), cx + 60, int(height * 0.40))
    pose.add_segment(cx + 60, int(height * 0.40), cx + 95, int(height * 0.55))
    # right arm back
    pose.add_segment(cx + 5, int(height * 0.30), cx - 50, int(height * 0.45))
    pose.add_segment(cx - 50, int(height * 0.45), cx - 70, int(height * 0.60))
    # left leg back
    pose.add_segment(cx + 20, hip_y, cx - 30, int(height * 0.78))
    pose.add_segment(cx - 30, int(height * 0.78), cx - 60, int(height * 0.95))
    # right leg forward
    pose.add_segment(cx + 20, hip_y, cx + 70, int(height * 0.78))
    pose.add_segment(cx + 70, int(height * 0.78), cx + 100, int(height * 0.93))
    # joints
    for x, y in [
        (cx + 5, int(height * 0.30)),     # shoulder
        (cx + 20, hip_y),                  # hip
        (cx + 60, int(height * 0.40)),    # L elbow
        (cx - 50, int(height * 0.45)),    # R elbow
        (cx - 30, int(height * 0.78)),    # L knee
        (cx + 70, int(height * 0.78)),    # R knee
    ]:
        pose.add_joint(x, y)
    return pose


def arms_up_pose(width: int, height: int) -> Pose:
    """A celebratory / T-pose-ish figure with arms raised."""
    cx = width // 2
    head_y = int(height * 0.20)
    hip_y = int(height * 0.60)
    pose = Pose(style=Style(background="black", foreground="white",
                            line_width=14, head_radius_default=32))
    pose.add_head(cx, head_y)
    # torso
    pose.add_segment(cx, head_y + 32, cx, hip_y)
    # arms up (out and up to a Y)
    pose.add_segment(cx, head_y + 32, cx - 90, head_y - 30)
    pose.add_segment(cx - 90, head_y - 30, cx - 110, head_y - 110)
    pose.add_segment(cx, head_y + 32, cx + 90, head_y - 30)
    pose.add_segment(cx + 90, head_y - 30, cx + 110, head_y - 110)
    # legs
    pose.add_segment(cx, hip_y, cx - 25, int(height * 0.80))
    pose.add_segment(cx - 25, int(height * 0.80), cx - 30, int(height * 0.97))
    pose.add_segment(cx, hip_y, cx + 25, int(height * 0.80))
    pose.add_segment(cx + 25, int(height * 0.80), cx + 30, int(height * 0.97))
    # joints
    for x, y in [
        (cx, head_y + 32),                 # shoulder
        (cx, hip_y),                       # hip
        (cx - 90, head_y - 30),            # L elbow
        (cx + 90, head_y - 30),            # R elbow
        (cx - 25, int(height * 0.80)),     # L knee
        (cx + 25, int(height * 0.80)),     # R knee
    ]:
        pose.add_joint(x, y)
    return pose


def main() -> int:
    out_dir = ROOT / "examples" / "sample_poses"
    out_dir.mkdir(parents=True, exist_ok=True)

    samples = [
        ("standing", (512, 512), standing_pose),
        ("walking", (512, 768), walking_pose),
        ("arms_up", (512, 512), arms_up_pose),
    ]

    for name, (w, h), builder in samples:
        pose = builder(w, h)
        png_path = out_dir / f"{name}.png"
        json_path = out_dir / f"{name}.pose.json"
        export_png(pose, w, h, str(png_path))
        io_json.save(pose, w, h, str(json_path))
        h_count, s_count, j_count = pose.counts()
        print(
            f"  {name:<8} {w}x{h}  "
            f"{h_count} heads · {s_count} limbs · {j_count} joints  "
            f"→ {png_path.relative_to(ROOT)}  +  {json_path.relative_to(ROOT)}"
        )

    print(f"\nWrote {len(samples)} sample poses to {out_dir.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())