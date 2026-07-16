"""Pure-data model for a stick figure pose.

Kept dependency-free so it can be reused headlessly (CLI, scripts, tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Head:
    """A circular head, drawn as a filled circle."""

    x: float
    y: float
    radius: float = 30.0


@dataclass
class Segment:
    """A straight line segment — torso, limb, etc."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class Joint:
    """A small dot used to mark elbows, knees, hands, etc."""

    x: float
    y: float
    radius: float = 5.0


@dataclass
class Style:
    """Drawing style applied at export time."""

    background: str = "black"
    foreground: str = "white"
    line_width: float = 12.0
    head_radius_default: float = 30.0
    joint_radius_default: float = 5.0


@dataclass
class Pose:
    """A complete stick figure: heads, segments (limbs), and joints."""

    heads: List[Head] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    joints: List[Joint] = field(default_factory=list)
    style: Style = field(default_factory=Style)

    # ----- queries -----------------------------------------------------------

    def is_empty(self) -> bool:
        return not (self.heads or self.segments or self.joints)

    def counts(self) -> Tuple[int, int, int]:
        return (len(self.heads), len(self.segments), len(self.joints))

    # ----- mutation ----------------------------------------------------------

    def clear(self) -> None:
        self.heads.clear()
        self.segments.clear()
        self.joints.clear()

    def add_head(self, x: float, y: float, radius: float | None = None) -> Head:
        head = Head(x=x, y=y, radius=radius or self.style.head_radius_default)
        self.heads.append(head)
        return head

    def add_segment(self, x1: float, y1: float, x2: float, y2: float) -> Segment:
        seg = Segment(x1=x1, y1=y1, x2=x2, y2=y2)
        self.segments.append(seg)
        return seg

    def add_joint(self, x: float, y: float, radius: float | None = None) -> Joint:
        joint = Joint(x=x, y=y, radius=radius or self.style.joint_radius_default)
        self.joints.append(joint)
        return joint

    def remove_head(self, head: Head) -> None:
        if head in self.heads:
            self.heads.remove(head)

    def remove_segment(self, segment: Segment) -> None:
        if segment in self.segments:
            self.segments.remove(segment)

    def remove_joint(self, joint: Joint) -> None:
        if joint in self.joints:
            self.joints.remove(joint)

    # ----- transforms --------------------------------------------------------

    def translate(self, dx: float, dy: float) -> None:
        for h in self.heads:
            h.x += dx
            h.y += dy
        for s in self.segments:
            s.x1 += dx
            s.y1 += dy
            s.x2 += dx
            s.y2 += dy
        for j in self.joints:
            j.x += dx
            j.y += dy

    def mirror_horizontal(self, width: float) -> None:
        """Mirror the pose around the vertical axis at x = width/2.

        Endpoints are *not* swapped: after mirroring, segment endpoints may
        have x1 > x2. That's fine for rendering (a line draws the same either
        way) and keeps ``mirror(mirror(pose))`` an exact round-trip.
        """
        for h in self.heads:
            h.x = width - h.x
        for s in self.segments:
            s.x1, s.x2 = width - s.x1, width - s.x2
        for j in self.joints:
            j.x = width - j.x

    # ----- copy --------------------------------------------------------------

    def copy(self) -> "Pose":
        return Pose(
            heads=[Head(h.x, h.y, h.radius) for h in self.heads],
            segments=[Segment(s.x1, s.y1, s.x2, s.y2) for s in self.segments],
            joints=[Joint(j.x, j.y, j.radius) for j in self.joints],
            style=Style(
                background=self.style.background,
                foreground=self.style.foreground,
                line_width=self.style.line_width,
                head_radius_default=self.style.head_radius_default,
                joint_radius_default=self.style.joint_radius_default,
            ),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def place_stick_figure(
    pose: Pose,
    center_x: float,
    center_y: float,
    *,
    target_height: float,
    head_radius: float | None = None,
) -> None:
    """Add a proportionally-correct standing stick figure to ``pose``.

    The figure is centred on ``(center_x, center_y)`` and sized so its total
    height (head top to feet) equals ``target_height`` units.

    Proportions are anatomical-style (head ≈ 16% of height, hips at 50%,
    knees at 75%, shoulders slightly wider than hips, arms relaxed at sides
    with hands near hip level). Good defaults for OpenPose / DWPose ControlNet
    references.

    Existing elements in ``pose`` are preserved; the new figure is added on
    top. The caller is responsible for history (this function does not push
    any undo state).
    """
    head_radius = float(head_radius if head_radius is not None else pose.style.head_radius_default)
    H = float(target_height)
    top = float(center_y) - H / 2.0

    # Vertical positions measured from the top of the figure.
    head_y     = top + 0.080 * H
    shoulder_y = top + 0.180 * H
    elbow_y    = top + 0.420 * H
    wrist_y    = top + 0.620 * H
    hip_y      = top + 0.500 * H
    knee_y     = top + 0.750 * H
    ankle_y    = top + 1.000 * H

    # Horizontal offsets (positive = right of the centre line).
    shoulder_off = 0.30 * H
    elbow_off    = 0.30 * H
    wrist_off    = 0.20 * H
    knee_off     = 0.13 * H
    ankle_off    = 0.13 * H

    # ---- build the figure --------------------------------------------------
    pose.add_head(center_x, head_y, head_radius)

    # Spine: just below the head (neck) down to the hips.
    spine_top = head_y + head_radius   # == neck / shoulder junction
    pose.add_segment(center_x, spine_top, center_x, hip_y)

    # Arms: branch from the neck/shoulder point (spine_top) so the skeleton
    # is geometrically connected at that node.
    for sign in (-1, 1):
        pose.add_segment(
            center_x, spine_top,
            center_x + sign * elbow_off, elbow_y,
        )
        pose.add_segment(
            center_x + sign * elbow_off, elbow_y,
            center_x + sign * wrist_off, wrist_y,
        )

    # Legs: hip → knee → ankle on each side.
    for sign in (-1, 1):
        pose.add_segment(
            center_x, hip_y,
            center_x + sign * knee_off, knee_y,
        )
        pose.add_segment(
            center_x + sign * knee_off, knee_y,
            center_x + sign * ankle_off, ankle_y,
        )

    # Key joints.
    pose.add_joint(center_x, spine_top)   # shoulder / neck junction
    pose.add_joint(center_x, hip_y)
    for sign in (-1, 1):
        pose.add_joint(center_x + sign * elbow_off, elbow_y)
        pose.add_joint(center_x + sign * knee_off, knee_y)