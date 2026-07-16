"""Tkinter GUI for the StickItToMe.

The UI is intentionally small and dependency-light:

* Tools: Head, Limb (line segment), Joint (dot), Erase, Move.
* Adjustable canvas size (presets for SD 1.5 / SDXL), line width, head radius.
* Invert / pick background + foreground colors, mirror horizontally.
* Save as PNG (preferred for ControlNet) or JPG; load/save pose JSON.
* Undo / redo (snapshot-based).

Run via ``python -m stickitto`` or, after install, ``stickit``.
"""

from __future__ import annotations

import math
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

from . import __version__
from . import io_json
from .exporter import export_image, export_jpg, export_png, render_pose
from .model import Head, Joint, Pose, Segment, Style, place_stick_figure

# App-icon locations (bundled with the package, generated programmatically so
# the app has no external image-generation dependency).
_PACKAGE_DIR = Path(__file__).resolve().parent
_ICON_PNG = _PACKAGE_DIR / "icon.png"
_ICON_ICO = _PACKAGE_DIR / "icon.ico"


# ---------------------------------------------------------------------------
# Canvas presets
# ---------------------------------------------------------------------------

CANVAS_PRESETS: List[Tuple[str, int, int]] = [
    ("512 × 512 (SD 1.5)", 512, 512),
    ("512 × 768 (SD portrait)", 512, 768),
    ("768 × 768 (SDXL square)", 768, 768),
    ("832 × 1216 (SDXL portrait)", 832, 1216),
    ("1024 × 1024 (SDXL)", 1024, 1024),
    ("1024 × 1536 (SDXL tall)", 1024, 1536),
]
PRESET_CUSTOM = ("Custom…", 0, 0)

HIT_RADIUS_PX = 12  # click hit slop for segment endpoint snapping


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _distance_point_to_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Perpendicular distance from point to line segment."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - cx, py - cy)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class StickfigureApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"StickItToMe v{__version__}")

        # ---- model state ----------------------------------------------------
        self.pose = Pose()
        self.canvas_size: Tuple[int, int] = (512, 512)
        self.tool: str = "head"

        # ---- drag state -----------------------------------------------------
        # What kind of drag is currently in progress, if any.
        # None | "limb" (drawing new segment) | "move" (dragging existing item)
        self._drag_kind: Optional[str] = None
        self._drag_start: Tuple[float, float] = (0.0, 0.0)
        self._drag_current: Tuple[float, float] = (0.0, 0.0)
        self._drag_rubber_id: Optional[int] = None  # canvas item id for preview
        self._moving_element: Optional[Tuple[str, Any]] = None  # (kind, model_obj)
        self._moving_origin: Optional[Dict[str, float]] = None

        # ---- canvas item -> model mapping ----------------------------------
        # For heads/joints: single canvas item per element.
        # For segments: line + two caps (all tagged with the same seg tag).
        self._heads_by_item: Dict[int, Head] = {}
        self._joints_by_item: Dict[int, Joint] = {}
        self._segments_by_tag: Dict[str, Segment] = {}  # tag -> segment
        self._items_by_segment: Dict[int, List[int]] = {}  # segment id -> canvas ids

        # ---- history --------------------------------------------------------
        self._undo_stack: List[Pose] = []
        self._redo_stack: List[Pose] = []
        self._max_history = 100
        # For drag-based actions (limb, move), we capture the pre-drag pose here
        # and push it to the undo stack only if the drag actually mutated state.
        self._drag_pre_state: Optional[Pose] = None
        self._drag_mutated: bool = False
        # Last cursor position during a move drag. We translate the element by
        # only the incremental delta since the last motion event, never by the
        # cumulative delta from the press — otherwise the element doubles up.
        self._drag_last_x: Optional[float] = None
        self._drag_last_y: Optional[float] = None
        # Single canvas-item id of the highlight outline drawn while dragging,
        # or None when nothing is being dragged. Used by the move tool.
        self._highlight_id: Optional[int] = None

        # ---- tk variables ---------------------------------------------------
        self.tool_var = tk.StringVar(value="head")
        self.size_var = tk.StringVar(value=CANVAS_PRESETS[0][0])
        self.line_width_var = tk.DoubleVar(value=self.pose.style.line_width)
        self.head_radius_var = tk.DoubleVar(value=self.pose.style.head_radius_default)
        self.status_var = tk.StringVar(value="")
        self.coords_var = tk.StringVar(value="")
        self.counts_var = tk.StringVar(value="0 heads · 0 limbs · 0 joints")

        self._build_ui()
        self._bind_events()
        self._set_app_icon()
        self._refresh_bg()
        self._set_status_for_tool()
        self._update_canvas_size(initial=True)
        self._update_counts()
        # Note: we intentionally do NOT seed the undo stack here. Each action
        # that mutates state calls _push_history() *before* the mutation.

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self._build_menu()
        self._build_toolbar()
        self._build_canvas_area()
        self._build_status_bar()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", accelerator="Ctrl+N", command=self.action_new)
        filemenu.add_command(label="Open pose…", accelerator="Ctrl+O", command=self.action_open)
        filemenu.add_separator()
        filemenu.add_command(label="Save PNG…", accelerator="Ctrl+S", command=self.action_save_png)
        filemenu.add_command(label="Save JPG…", accelerator="Ctrl+Shift+S", command=self.action_save_jpg)
        filemenu.add_command(label="Save pose as JSON…", command=self.action_save_pose)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", accelerator="Ctrl+Q", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.action_undo)
        editmenu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.action_redo)
        editmenu.add_separator()
        editmenu.add_command(label="Mirror horizontally", accelerator="Ctrl+M", command=self.action_mirror)
        editmenu.add_command(label="Clear canvas", command=self.action_clear)
        editmenu.add_command(label="Invert colors", command=self.action_invert_colors)
        menubar.add_cascade(label="Edit", menu=editmenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        for label, w, h in CANVAS_PRESETS:
            viewmenu.add_command(
                label=f"Resize to {label}",
                command=lambda w=w, h=h: self._apply_canvas_size(w, h),
            )
        menubar.add_cascade(label="View", menu=viewmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Keyboard shortcuts", command=self._show_shortcuts)
        helpmenu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(6, 4))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # ---- tools ----------------------------------------------------------
        tools = ttk.LabelFrame(toolbar, text="Tool", padding=(6, 2))
        tools.pack(side=tk.LEFT, padx=(0, 6))
        for value, label in [
            ("head", "Head  (H)"),
            ("limb", "Limb  (L)"),
            ("joint", "Joint  (J)"),
            ("figure", "Figure  (F)"),
            ("erase", "Erase  (E)"),
            ("move", "Move  (M)"),
        ]:
            ttk.Radiobutton(
                tools, text=label, value=value, variable=self.tool_var,
                command=self._set_status_for_tool,
            ).pack(side=tk.LEFT, padx=2)

        # ---- settings -------------------------------------------------------
        settings = ttk.LabelFrame(toolbar, text="Settings", padding=(6, 2))
        settings.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Label(settings, text="Size:").pack(side=tk.LEFT, padx=(0, 4))
        size_values = [p[0] for p in CANVAS_PRESETS] + [PRESET_CUSTOM[0]]
        self._size_combo = ttk.Combobox(
            settings, textvariable=self.size_var, values=size_values,
            state="readonly", width=26,
        )
        self._size_combo.pack(side=tk.LEFT)
        self._size_combo.bind("<<ComboboxSelected>>", self._on_size_preset)

        ttk.Separator(settings, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Label(settings, text="Line:").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Scale(
            settings, from_=1, to=30, variable=self.line_width_var,
            orient=tk.HORIZONTAL, length=80,
            command=lambda _v: self._on_style_change(),
        ).pack(side=tk.LEFT)
        ttk.Label(settings, textvariable=self.line_width_var, width=4).pack(side=tk.LEFT)

        ttk.Label(settings, text="Head:").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Scale(
            settings, from_=8, to=80, variable=self.head_radius_var,
            orient=tk.HORIZONTAL, length=80,
            command=lambda _v: self._on_style_change(),
        ).pack(side=tk.LEFT)
        ttk.Label(settings, textvariable=self.head_radius_var, width=4).pack(side=tk.LEFT)

        # ---- colors ---------------------------------------------------------
        colors = ttk.LabelFrame(toolbar, text="Colors", padding=(6, 2))
        colors.pack(side=tk.LEFT, padx=(0, 6))

        self._bg_button = tk.Button(
            colors, text="BG", width=4, command=self._pick_bg_color,
            relief="raised",
        )
        self._bg_button.pack(side=tk.LEFT, padx=2)
        self._fg_button = tk.Button(
            colors, text="FG", width=4, command=self._pick_fg_color,
            relief="raised",
        )
        self._fg_button.pack(side=tk.LEFT, padx=2)
        ttk.Button(colors, text="Invert", command=self.action_invert_colors).pack(side=tk.LEFT, padx=2)
        # quick presets
        for label, bg, fg in [("W/B", "white", "black"), ("B/W", "black", "white")]:
            ttk.Button(
                colors, text=label, width=4,
                command=lambda bg=bg, fg=fg: self._set_colors(bg, fg),
            ).pack(side=tk.LEFT, padx=2)

        # ---- actions --------------------------------------------------------
        actions = ttk.LabelFrame(toolbar, text="Actions", padding=(6, 2))
        actions.pack(side=tk.LEFT)
        ttk.Button(actions, text="Mirror", command=self.action_mirror).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Clear", command=self.action_clear).pack(side=tk.LEFT, padx=2)

    def _build_canvas_area(self) -> None:
        # Outer frame fills all available space.
        wrap = ttk.Frame(self.root, padding=4)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Centre frame: expand=True but no fill, so it floats centred in wrap.
        centre = ttk.Frame(wrap)
        centre.pack(expand=True)  # no fill= — stays at its natural (canvas) size, centred

        self.canvas = tk.Canvas(
            centre,
            bg=self.pose.style.background,
            highlightthickness=1,
            highlightbackground="#888888",
        )
        # Create scrollbars BEFORE we tell the canvas to bind to them.
        vscroll = ttk.Scrollbar(centre, orient=tk.VERTICAL, command=self.canvas.yview)
        hscroll = ttk.Scrollbar(centre, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(
            xscrollcommand=hscroll.set,
            yscrollcommand=vscroll.set,
        )

        # Pack scrollbars first (outside-in), canvas last at native size.
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT)

        # Mouse wheel scrolling. Linux uses Button-4 / Button-5; macOS and
        # Windows deliver a <MouseWheel> event with an integer ``delta``.
        # ``delta // 120`` lines up with the conventional "one notch per
        # 120 units" deltas used by most X11 drivers.
        self.canvas.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"),
        )
        self.canvas.bind(
            "<Button-4>",
            lambda _e: self.canvas.yview_scroll(-1, "units"),
        )
        self.canvas.bind(
            "<Button-5>",
            lambda _e: self.canvas.yview_scroll(1, "units"),
        )

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(6, 2))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(bar, textvariable=self.coords_var).pack(side=tk.LEFT)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(bar, textvariable=self.counts_var).pack(side=tk.LEFT)
        ttk.Label(bar, text=f"v{__version__}").pack(side=tk.RIGHT)

    # ------------------------------------------------------------- events

    def _bind_events(self) -> None:
        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Motion>", self._on_motion)
        c.bind("<Leave>", lambda _e: self.coords_var.set(""))

        # keyboard
        self.root.bind_all("<Control-n>", lambda _e: self.action_new())
        self.root.bind_all("<Control-o>", lambda _e: self.action_open())
        self.root.bind_all("<Control-s>", lambda _e: self.action_save_png())
        self.root.bind_all("<Control-S>", lambda _e: self.action_save_jpg())
        self.root.bind_all("<Control-q>", lambda _e: self.root.destroy())
        self.root.bind_all("<Control-z>", lambda _e: self.action_undo())
        self.root.bind_all("<Control-y>", lambda _e: self.action_redo())
        # Ctrl+Shift+Z (Mac-style redo) and Ctrl+Z (Windows redo) — Windows is Ctrl+Y above.
        self.root.bind_all("<Control-Shift-Z>", lambda _e: self.action_redo())
        self.root.bind_all("<Control-m>", lambda _e: self.action_mirror())

        self.root.bind_all("<Key-h>", lambda _e: self._set_tool("head"))
        self.root.bind_all("<Key-l>", lambda _e: self._set_tool("limb"))
        self.root.bind_all("<Key-j>", lambda _e: self._set_tool("joint"))
        self.root.bind_all("<Key-f>", lambda _e: self._set_tool("figure"))
        self.root.bind_all("<Key-e>", lambda _e: self._set_tool("erase"))
        self.root.bind_all("<Key-m>", lambda _e: self._set_tool("move"))
        self.root.bind_all("<Key-i>", lambda _e: self.action_invert_colors())

        # + / - adjust line width; [ / ] adjust head radius
        self.root.bind_all("<Key-plus>", lambda _e: self._nudge_line_width(+1))
        self.root.bind_all("<Key-equal>", lambda _e: self._nudge_line_width(+1))  # US keyboard: + is shift+=
        self.root.bind_all("<Key-minus>", lambda _e: self._nudge_line_width(-1))
        self.root.bind_all("<Key-bracketleft>", lambda _e: self._nudge_head_radius(-2))
        self.root.bind_all("<Key-bracketright>", lambda _e: self._nudge_head_radius(+2))

    def _set_tool(self, tool: str) -> None:
        self.tool_var.set(tool)
        self.tool = tool
        self._set_status_for_tool()

    def _on_motion(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        if 0 <= x < self.canvas_size[0] and 0 <= y < self.canvas_size[1]:
            self.coords_var.set(f"({x:>4}, {y:>4})")
        else:
            self.coords_var.set("(outside)")
        if self._drag_kind == "limb" and self._drag_rubber_id is not None:
            self.canvas.coords(
                self._drag_rubber_id,
                self._drag_start[0], self._drag_start[1],
                x, y,
            )

    # ---------------------------------------------------------- canvas hit

    def _hit_test(self, x: float, y: float) -> Optional[Tuple[str, Any]]:
        """Return ``(kind, model_obj)`` for the topmost element under (x, y), or None."""
        # First, see what the canvas itself considers overlapping.
        overlapping = self.canvas.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        if overlapping:
            top = overlapping[-1]  # last drawn = topmost
            hit = self._hit_from_item(top)
            if hit is not None:
                return hit

        # Otherwise, fall back to distance-based hit testing for segments
        # (their caps might be off the line and miss a 1px box).
        tol = max(8.0, self.pose.style.line_width / 2.0 + 4.0)
        # Iterate in reverse so later-drawn items win.
        for seg in reversed(self.pose.segments):
            d = _distance_point_to_segment(x, y, seg.x1, seg.y1, seg.x2, seg.y2)
            if d <= tol:
                return ("segment", seg)
        # Joints are small; allow a generous click radius.
        for joint in reversed(self.pose.joints):
            if math.hypot(joint.x - x, joint.y - y) <= max(tol, joint.radius + 4):
                return ("joint", joint)
        # Heads: only consider as hit if click is well inside — they cover a big area
        # and we don't want to constantly grab them while drawing nearby.
        for head in reversed(self.pose.heads):
            if math.hypot(head.x - x, head.y - y) <= head.radius - max(4.0, self.pose.style.line_width / 2.0):
                return ("head", head)
        return None

    def _hit_from_item(self, item_id: int) -> Optional[Tuple[str, Any]]:
        tags = self.canvas.gettags(item_id)
        for tag in tags:
            if tag.startswith("seg-"):
                seg = self._segments_by_tag.get(tag)
                if seg is not None:
                    return ("segment", seg)
        if "head" in tags and item_id in self._heads_by_item:
            return ("head", self._heads_by_item[item_id])
        if "joint" in tags and item_id in self._joints_by_item:
            return ("joint", self._joints_by_item[item_id])
        return None

    # -------------------------------------------------- press / drag / release

    def _on_press(self, event: tk.Event) -> None:
        x, y = float(event.x), float(event.y)
        if not (0 <= x < self.canvas_size[0] and 0 <= y < self.canvas_size[1]):
            return

        tool = self.tool_var.get()
        if tool == "head":
            self._push_history()
            self.pose.add_head(x, y, self.pose.style.head_radius_default)
            self._redraw_all()
        elif tool == "joint":
            self._push_history()
            self.pose.add_joint(x, y)
            self._redraw_all()
        elif tool == "figure":
            # Place a proportionally-correct standing stick figure. The
            # target height is 70% of the smaller canvas dimension. We
            # CLAMP the click point so the figure stays fully within the
            # canvas — without this, clicks near the edges produce figures
            # whose head sticks out above the canvas and the user only sees
            # the lower portion (or nothing at all on tall canvases).
            w, h = self.canvas_size
            target_height = 0.7 * min(w, h)
            half = target_height / 2.0
            cx = max(half, min(w - half, x))
            cy = max(half, min(h - half, y))
            self._push_history()
            place_stick_figure(
                self.pose, cx, cy,
                target_height=target_height,
                head_radius=self.pose.style.head_radius_default,
            )
            self._redraw_all()
        elif tool == "limb":
            self._drag_kind = "limb"
            self._drag_start = (x, y)
            self._drag_current = (x, y)
            self._drag_pre_state = self.pose.copy()
            self._drag_mutated = False
            lw = max(1, int(round(self.pose.style.line_width)))
            self._drag_rubber_id = self.canvas.create_line(
                x, y, x, y, fill=self.pose.style.foreground,
                width=lw, dash=(4, 3),
            )
        elif tool == "erase":
            hit = self._hit_test(x, y)
            if hit is not None:
                kind, obj = hit
                self._push_history()
                if kind == "head":
                    self.pose.remove_head(obj)
                elif kind == "joint":
                    self.pose.remove_joint(obj)
                elif kind == "segment":
                    self.pose.remove_segment(obj)
                self._redraw_all()
        elif tool == "move":
            hit = self._hit_test(x, y)
            if hit is not None:
                kind, obj = hit
                self._drag_kind = "move"
                self._drag_start = (x, y)
                # Anchor the incremental delta here, NOT _drag_start, so each
                # motion only contributes its own delta.
                self._drag_last_x = x
                self._drag_last_y = y
                self._moving_element = (kind, obj)
                self._moving_origin = self._element_position_dict(kind, obj)
                self._drag_pre_state = self.pose.copy()
                self._drag_mutated = False
                self._start_move_highlight(kind, obj)

    def _on_drag(self, event: tk.Event) -> None:
        x, y = float(event.x), float(event.y)
        self._drag_current = (x, y)
        if self._drag_kind == "limb" and self._drag_rubber_id is not None:
            self.canvas.coords(
                self._drag_rubber_id,
                self._drag_start[0], self._drag_start[1], x, y,
            )
        elif self._drag_kind == "move" and self._moving_element is not None:
            kind, obj = self._moving_element
            if self._drag_last_x is None or self._drag_last_y is None:
                self._drag_last_x, self._drag_last_y = self._drag_start
            dx = x - self._drag_last_x
            dy = y - self._drag_last_y
            if dx != 0.0 or dy != 0.0:
                self._drag_mutated = True
                if kind == "joint":
                    # Joints drag any attached segments with them so the
                    # skeleton stays connected.
                    self._apply_joint_translate_with_attachments(obj, dx, dy)
                elif kind == "segment":
                    # Segments drag their endpoints' joints with them, plus
                    # any adjacent segments rotate around their far endpoint.
                    self._apply_segment_translate_with_attachments(obj, dx, dy)
                elif kind == "head":
                    # Heads drag any segment endpoints and joints at their
                    # bottom edge (neck attach point) with them.
                    self._apply_head_translate_with_attachments(obj, dx, dy)
                else:
                    self._apply_translate_to_element(kind, obj, dx, dy)
                # update the anchor for the next motion event
                self._drag_last_x = x
                self._drag_last_y = y
                self._redraw_all()
                # redraw_all() deletes every canvas item including the
                # highlight, so restore it (idempotent if no highlight).
                self._update_move_highlight(kind, obj)

    def _on_release(self, event: tk.Event) -> None:
        x, y = float(event.x), float(event.y)
        if self._drag_kind == "limb":
            if self._drag_rubber_id is not None:
                self.canvas.delete(self._drag_rubber_id)
                self._drag_rubber_id = None
            x1, y1 = self._drag_start
            # ignore zero-length drags
            if math.hypot(x - x1, y - y1) >= 2:
                self._push_pre_state(self._drag_pre_state)
                self.pose.add_segment(x1, y1, x, y)
                self._redraw_all()
            self._drag_kind = None
            self._drag_pre_state = None
        elif self._drag_kind == "move":
            if self._drag_mutated and self._drag_pre_state is not None:
                self._push_pre_state(self._drag_pre_state)
            self._end_move_highlight()
            self._drag_kind = None
            self._moving_element = None
            self._moving_origin = None
            self._drag_pre_state = None
            self._drag_mutated = False
            self._drag_last_x = None
            self._drag_last_y = None

    @staticmethod
    def _element_position_dict(kind: str, obj: Any) -> Dict[str, float]:
        if kind == "head":
            return {"x": obj.x, "y": obj.y}
        if kind == "joint":
            return {"x": obj.x, "y": obj.y}
        if kind == "segment":
            return {"x1": obj.x1, "y1": obj.y1, "x2": obj.x2, "y2": obj.y2}
        return {}

    @staticmethod
    def _apply_translate_to_element(kind: str, obj: Any, dx: float, dy: float) -> None:
        if kind == "head":
            obj.x += dx
            obj.y += dy
        elif kind == "joint":
            obj.x += dx
            obj.y += dy
        elif kind == "segment":
            obj.x1 += dx
            obj.y1 += dy
            obj.x2 += dx
            obj.y2 += dy

    # Tolerance for matching a segment endpoint to a joint's position. Floating
    # point comparison is fine here because joints and segments are usually
    # created from the same expression (e.g. shoulder.x1 == shoulder_joint.x),
    # so the gap is exactly zero in well-formed poses; the tolerance is just
    # insurance against later round-tripping or manual nudges.
    _JOINT_ATTACH_TOL = 0.5

    def _apply_joint_translate_with_attachments(
        self, joint: Joint, dx: float, dy: float,
    ) -> None:
        """Move a joint AND any segment endpoints or head bottoms that share its position.

        A joint is a *connection point* — moving it should keep attached
        limbs and the head attached.  We check:
        - Segment endpoints within tolerance → translate them.
        - Heads whose bottom edge (cx, cy+r) sits within tolerance of the
          joint → translate the head so it stays "resting on" the joint.
        """
        jx, jy = joint.x, joint.y
        tol = self._JOINT_ATTACH_TOL
        for seg in self.pose.segments:
            if abs(seg.x1 - jx) <= tol and abs(seg.y1 - jy) <= tol:
                seg.x1 += dx
                seg.y1 += dy
            if abs(seg.x2 - jx) <= tol and abs(seg.y2 - jy) <= tol:
                seg.x2 += dx
                seg.y2 += dy
        for head in self.pose.heads:
            neck_x = head.x
            neck_y = head.y + head.radius
            if abs(neck_x - jx) <= tol and abs(neck_y - jy) <= tol:
                head.x += dx
                head.y += dy
        joint.x += dx
        joint.y += dy

    def _apply_head_translate_with_attachments(
        self, head: Head, dx: float, dy: float,
    ) -> None:
        """Move a head AND every segment/joint connected to it (the whole figure).

        Flood-fill the segment connectivity graph starting from the head's
        neck point, collecting every segment and joint reachable via shared
        endpoints.  Covers the full skeleton without needing explicit groups.
        """
        tol = self._JOINT_ATTACH_TOL

        def near(ax: float, ay: float, bx: float, by: float) -> bool:
            return abs(ax - bx) <= tol and abs(ay - by) <= tol

        # Collect all segment endpoints reachable from the neck via BFS.
        neck_x = head.x
        neck_y = head.y + head.radius

        # frontier: list of (x, y) points to expand next
        frontier = [(neck_x, neck_y)]
        visited_pts: list = []   # points already expanded
        collected_segs: list = []

        while frontier:
            px, py = frontier.pop()
            # skip if already expanded
            if any(near(px, py, vx, vy) for vx, vy in visited_pts):
                continue
            visited_pts.append((px, py))
            # find every segment that touches this point
            for seg in self.pose.segments:
                if seg in collected_segs:
                    continue
                at1 = near(seg.x1, seg.y1, px, py)
                at2 = near(seg.x2, seg.y2, px, py)
                if at1 or at2:
                    collected_segs.append(seg)
                    # queue the OTHER endpoint for expansion
                    if at1:
                        frontier.append((seg.x2, seg.y2))
                    if at2:
                        frontier.append((seg.x1, seg.y1))

        # Collect joints at any visited point.
        collected_joints = [
            j for j in self.pose.joints
            if any(near(j.x, j.y, vx, vy) for vx, vy in visited_pts)
        ]

        # Translate everything.
        head.x += dx; head.y += dy
        for seg in collected_segs:
            seg.x1 += dx; seg.y1 += dy
            seg.x2 += dx; seg.y2 += dy
        for joint in collected_joints:
            joint.x += dx; joint.y += dy

    def _apply_segment_translate_with_attachments(
        self, segment: Segment, dx: float, dy: float,
    ) -> None:
        """Move a segment AND its connected joints and adjacent segments.

        The hand / foot case: grabbing the end of a forearm (no joint
        there) and dragging it currently leaves the elbow joint dot
        stranded. We translate the dragged segment rigidly, then:

        1. Translate any joint sitting at one of the dragged segment's
           old endpoints — the joint stays attached to the moved end.
        2. For each moved joint, find other segments whose endpoint touches
           the joint's old position and translate just *that* endpoint —
           those segments rotate around their far endpoint so the skeleton
           stays connected (e.g. dragging the forearm ends up moving the
           elbow joint, which then moves the upper arm's elbow end while
           the shoulder end stays put).

        Bounds: this walk is local to the touched joint(s), so it's O(joints + adjacents), not a full graph traversal.
        """
        tol = self._JOINT_ATTACH_TOL
        old_x1, old_y1 = segment.x1, segment.y1
        old_x2, old_y2 = segment.x2, segment.y2

        # 1. Translate the dragged segment rigidly.
        segment.x1 += dx
        segment.y1 += dy
        segment.x2 += dx
        segment.y2 += dy

        # 2. Move joints at the old endpoints.
        moved_joints: list = []
        for joint in self.pose.joints:
            at_e1 = abs(joint.x - old_x1) <= tol and abs(joint.y - old_y1) <= tol
            at_e2 = abs(joint.x - old_x2) <= tol and abs(joint.y - old_y2) <= tol
            if at_e1 or at_e2:
                joint.x += dx
                joint.y += dy
                moved_joints.append(joint)

        # 2b. Move heads whose bottom (neck) sits at one of the old endpoints.
        for head in self.pose.heads:
            neck_x = head.x
            neck_y = head.y + head.radius
            at_e1 = abs(neck_x - old_x1) <= tol and abs(neck_y - old_y1) <= tol
            at_e2 = abs(neck_x - old_x2) <= tol and abs(neck_y - old_y2) <= tol
            if at_e1 or at_e2:
                head.x += dx
                head.y += dy

        # 3. For each moved joint, move adjacent segments' matching endpoint.
        for joint in moved_joints:
            old_jx = joint.x - dx
            old_jy = joint.y - dy
            for seg in self.pose.segments:
                if seg is segment:
                    continue  # already translated
                if abs(seg.x1 - old_jx) <= tol and abs(seg.y1 - old_jy) <= tol:
                    seg.x1 += dx
                    seg.y1 += dy
                if abs(seg.x2 - old_jx) <= tol and abs(seg.y2 - old_jy) <= tol:
                    seg.x2 += dx
                    seg.y2 += dy

    # ------------------------------------------------------------ drawing

    def _redraw_all(self) -> None:
        self.canvas.delete("all")
        self._heads_by_item.clear()
        self._joints_by_item.clear()
        self._segments_by_tag.clear()
        self._items_by_segment.clear()

        fg = self.pose.style.foreground
        lw = max(1, int(round(self.pose.style.line_width)))
        cap_r = self.pose.style.line_width / 2.0

        for seg in self.pose.segments:
            tag = f"seg-{id(seg)}"
            line_id = self.canvas.create_line(
                seg.x1, seg.y1, seg.x2, seg.y2,
                fill=fg, width=lw, tags=("segment", tag),
            )
            cap1 = self.canvas.create_oval(
                seg.x1 - cap_r, seg.y1 - cap_r,
                seg.x1 + cap_r, seg.y1 + cap_r,
                fill=fg, outline=fg, tags=("segment", tag),
            )
            cap2 = self.canvas.create_oval(
                seg.x2 - cap_r, seg.y2 - cap_r,
                seg.x2 + cap_r, seg.y2 + cap_r,
                fill=fg, outline=fg, tags=("segment", tag),
            )
            self._segments_by_tag[tag] = seg
            self._items_by_segment[id(seg)] = [line_id, cap1, cap2]

        for head in self.pose.heads:
            r = head.radius
            item = self.canvas.create_oval(
                head.x - r, head.y - r, head.x + r, head.y + r,
                fill=fg, outline=fg, tags=("head",),
            )
            self._heads_by_item[item] = head

        for joint in self.pose.joints:
            r = joint.radius
            item = self.canvas.create_oval(
                joint.x - r, joint.y - r, joint.x + r, joint.y + r,
                fill=fg, outline=fg, tags=("joint",),
            )
            self._joints_by_item[item] = joint

        self._update_counts()

    def _refresh_bg(self) -> None:
        bg = self.pose.style.background
        fg = self.pose.style.foreground
        self.canvas.configure(bg=bg)
        # color buttons: white text on dark bg, dark text on light bg.
        def fg_text_for(bg_color: str) -> str:
            return "white" if _is_dark(bg_color) else "black"
        self._bg_button.configure(bg=bg, activebackground=bg, fg=fg_text_for(bg))
        self._fg_button.configure(bg=fg, activebackground=fg, fg=fg_text_for(fg))

    def _update_counts(self) -> None:
        h, s, j = self.pose.counts()
        self.counts_var.set(f"{h} heads · {s} limbs · {j} joints")

    def _set_status_for_tool(self) -> None:
        tool = self.tool_var.get()
        self.tool = tool
        hints = {
            "head": "Head — click to place a head.",
            "limb": "Limb — click and drag to draw a segment.",
            "joint": "Joint — click to place a small dot.",
            "figure": "Figure — click to place a proportional stick figure, centred on the click.",
            "erase": "Erase — click an element to remove it.",
            "move": "Move — click and drag to reposition. Dragging a joint also drags any attached limbs.",
        }
        self.status_var.set(hints.get(tool, ""))

    # -------------------------------------------------------- canvas sizing

    def _on_size_preset(self, _event: tk.Event) -> None:
        label = self.size_var.get()
        for name, w, h in CANVAS_PRESETS:
            if name == label:
                self._apply_canvas_size(w, h)
                return
        if label == PRESET_CUSTOM[0]:
            self._prompt_custom_size()

    def _prompt_custom_size(self) -> None:
        dialog = _SizeDialog(self.root)
        self.root.wait_window(dialog.top)
        if dialog.result is not None:
            w, h = dialog.result
            self._apply_canvas_size(w, h)

    def _apply_canvas_size(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if (width, height) == self.canvas_size:
            # just update the label
            for name, w, h in CANVAS_PRESETS:
                if (w, h) == (width, height):
                    self.size_var.set(name)
                    return
            self.size_var.set(f"{width} × {height} (custom)")
            return
        self.canvas_size = (width, height)
        # match combo label
        for name, w, h in CANVAS_PRESETS:
            if (w, h) == (width, height):
                self.size_var.set(name)
                break
        else:
            self.size_var.set(f"{width} × {height} (custom)")
        self._update_canvas_size()
        # if the pose has elements outside the new canvas, warn the user.
        if self._any_outside_canvas():
            if messagebox.askyesno(
                "Pose extends beyond new canvas",
                "Some elements are now outside the new canvas size. "
                "Mirror would not be defined.\n\n"
                "Clear the canvas?",
            ):
                self.pose.clear()
                self._redraw_all()
                self._push_history()

    def _update_canvas_size(self, initial: bool = False) -> None:
        w, h = self.canvas_size
        self.canvas.configure(width=w, height=h)
        # Make the canvas scrollable over its full image extent. Without
        # this the scrollbars are decorative even when the image overflows
        # the window.
        self.canvas.configure(scrollregion=(0, 0, w, h))
        # Reset the view to the top-left after a resize so the user always
        # sees the canvas origin first.
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        if not initial:
            self._redraw_all()

    def _any_outside_canvas(self) -> bool:
        w, h = self.canvas_size
        for head in self.pose.heads:
            if head.x - head.radius < 0 or head.y - head.radius < 0:
                return True
            if head.x + head.radius > w or head.y + head.radius > h:
                return True
        for seg in self.pose.segments:
            if min(seg.x1, seg.x2) < 0 or min(seg.y1, seg.y2) < 0:
                return True
            if max(seg.x1, seg.x2) > w or max(seg.y1, seg.y2) > h:
                return True
        for joint in self.pose.joints:
            if joint.x < 0 or joint.y < 0 or joint.x > w or joint.y > h:
                return True
        return False

    # ---------------------------------------------------------------- actions

    def action_new(self) -> None:
        if not self._confirm_discard_changes():
            return
        self._push_history()
        self.pose.clear()
        self._redraw_all()
        self._redo_stack.clear()

    def action_open(self) -> None:
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            title="Open pose",
            filetypes=[("Pose files", "*.pose.json *.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            pose, w, h = io_json.load(path)
        except Exception as exc:  # noqa: BLE001 — surface any parse error
            messagebox.showerror("Failed to open pose", f"{exc}")
            return
        # Snapshot the existing pose first so the load itself is undoable.
        self._push_history()
        self.pose = pose
        self._apply_canvas_size(w, h)
        # also pull style back from the loaded pose
        self.line_width_var.set(self.pose.style.line_width)
        self.head_radius_var.set(self.pose.style.head_radius_default)
        self._refresh_bg()
        self._redraw_all()
        self._redo_stack.clear()

    def action_save_png(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save PNG",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            initialfile="pose.png",
        )
        if not path:
            return
        try:
            export_png(self.pose, *self.canvas_size, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to save PNG", f"{exc}")
            return
        self.status_var.set(f"Saved {os.path.basename(path)}")

    def action_save_jpg(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save JPG",
            defaultextension=".jpg",
            filetypes=[("JPEG image", "*.jpg *.jpeg")],
            initialfile="pose.jpg",
        )
        if not path:
            return
        try:
            export_jpg(self.pose, *self.canvas_size, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to save JPG", f"{exc}")
            return
        self.status_var.set(f"Saved {os.path.basename(path)}")

    def action_save_pose(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save pose as JSON",
            defaultextension=".pose.json",
            filetypes=[("Pose JSON", "*.pose.json"), ("JSON", "*.json")],
            initialfile="pose.pose.json",
        )
        if not path:
            return
        try:
            io_json.save(self.pose, *self.canvas_size, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to save pose", f"{exc}")
            return
        self.status_var.set(f"Saved {os.path.basename(path)}")

    def action_undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self.pose.copy())
        self.pose = self._undo_stack.pop()
        self._sync_style_vars_from_pose()
        self._refresh_bg()
        self._redraw_all()

    def action_redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self.pose.copy())
        self.pose = self._redo_stack.pop()
        self._sync_style_vars_from_pose()
        self._refresh_bg()
        self._redraw_all()

    def action_mirror(self) -> None:
        w, _ = self.canvas_size
        self._push_history()
        self.pose.mirror_horizontal(w)
        self._redraw_all()

    def action_clear(self) -> None:
        if self.pose.is_empty():
            return
        if not messagebox.askyesno("Clear canvas", "Remove every element?"):
            return
        self._push_history()
        self.pose.clear()
        self._redraw_all()

    def action_invert_colors(self) -> None:
        bg, fg = self.pose.style.foreground, self.pose.style.background
        self._set_colors(bg, fg)

    # -------------------------------------------------------------- style

    def _set_colors(self, bg: str, fg: str) -> None:
        self._push_history()
        self.pose.style.background = bg
        self.pose.style.foreground = fg
        self._refresh_bg()
        self._redraw_all()

    def _pick_bg_color(self) -> None:
        from tkinter import colorchooser
        color = colorchooser.askcolor(
            color=self.pose.style.background,
            title="Choose background color",
        )
        if color and color[1]:
            self._push_history()
            self.pose.style.background = color[1]
            self._refresh_bg()

    def _pick_fg_color(self) -> None:
        from tkinter import colorchooser
        color = colorchooser.askcolor(
            color=self.pose.style.foreground,
            title="Choose figure color",
        )
        if color and color[1]:
            self._push_history()
            self.pose.style.foreground = color[1]
            self._refresh_bg()
            self._redraw_all()

    def _on_style_change(self) -> None:
        # Snapshot before mutating so slider drags are undoable in one step.
        self._push_history()
        self.pose.style.line_width = float(self.line_width_var.get())
        self.pose.style.head_radius_default = float(self.head_radius_var.get())
        # heads created later use the new default radius; existing heads keep theirs.
        self._redraw_all()

    def _sync_style_vars_from_pose(self) -> None:
        self.line_width_var.set(self.pose.style.line_width)
        self.head_radius_var.set(self.pose.style.head_radius_default)

    def _nudge_line_width(self, delta: float) -> None:
        new = max(1.0, min(30.0, float(self.line_width_var.get()) + delta))
        self.line_width_var.set(new)
        self._on_style_change()

    def _nudge_head_radius(self, delta: float) -> None:
        new = max(8.0, min(80.0, float(self.head_radius_var.get()) + delta))
        self.head_radius_var.set(new)
        self._on_style_change()

    # ------------------------------------------------------------- history

    def _push_history(self) -> None:
        """Snapshot the *current* pose to the undo stack.

        Call this *before* mutating ``self.pose``. The convention is:

        1. ``self._push_history()``
        2. mutate ``self.pose``
        3. ``self._redraw_all()``

        Undo will then restore the snapshot we just took.
        """
        self._undo_stack.append(self.pose.copy())
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _push_pre_state(self, snapshot: Pose) -> None:
        """Push a pre-captured snapshot (used by drag-based actions)."""
        self._undo_stack.append(snapshot.copy())
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _confirm_discard_changes(self) -> bool:
        if not self.pose.heads and not self.pose.segments and not self.pose.joints:
            return True
        return messagebox.askyesno("Discard current pose?", "This will replace the current pose.")

    # -------------------------------------------------------------- dialogs

    # ------------------------------------------------------------- icon

    # ----------------------------------------------------------- highlight

    def _highlight_color(self) -> str:
        """Pick a colour contrasting with both foreground and background.

        Used for the dashed outline that shows which element is being
        dragged in the Move tool. Aims for high visibility regardless of
        theme: amber on dark, blue on light. Falls back to a brand-safe
        cyan if luminance detection is inconclusive.
        """
        bg = self.pose.style.background
        if _is_dark(bg):
            return "#FFD400"  # amber on dark
        return "#0078D7"  # azure on light

    def _start_move_highlight(self, kind: str, obj: Any) -> None:
        """Draw a dashed outline around the element being moved."""
        if self._highlight_id is not None:
            # don't double up
            self.canvas.delete(self._highlight_id)
        color = self._highlight_color()
        margin = 4

        if kind == "head":
            r = obj.radius
            bbox = [
                obj.x - r - margin, obj.y - r - margin,
                obj.x + r + margin, obj.y + r + margin,
            ]
            self._highlight_id = self.canvas.create_oval(
                *bbox, outline=color, width=2, dash=(4, 3),
            )
        elif kind == "joint":
            r = obj.radius
            bbox = [
                obj.x - r - margin, obj.y - r - margin,
                obj.x + r + margin, obj.y + r + margin,
            ]
            self._highlight_id = self.canvas.create_oval(
                *bbox, outline=color, width=2, dash=(4, 3),
            )
        elif kind == "segment":
            x1, y1, x2, y2 = obj.x1, obj.y1, obj.x2, obj.y2
            bbox = [
                min(x1, x2) - margin, min(y1, y2) - margin,
                max(x1, x2) + margin, max(y1, y2) + margin,
            ]
            self._highlight_id = self.canvas.create_rectangle(
                *bbox, outline=color, width=2, dash=(4, 3),
            )
        else:
            self._highlight_id = None

    def _update_move_highlight(self, kind: str, obj: Any) -> None:
        """Re-draw the outline to follow the element as it moves."""
        if self._highlight_id is None:
            return
        # Simplest correct behaviour: tear down + redraw. Cheap, and
        # avoids the coordinate-math subtleties of mutating an existing
        # canvas item's bbox under rotation/translation.
        self._end_move_highlight()
        self._start_move_highlight(kind, obj)

    def _end_move_highlight(self) -> None:
        if self._highlight_id is not None:
            self.canvas.delete(self._highlight_id)
            self._highlight_id = None

    # ------------------------------------------------------------- icon

    def _set_app_icon(self) -> None:
        """Load and apply the bundled app icon. Never fatal if it fails."""
        self._app_icon = None
        try:
            if sys.platform.startswith("win") and _ICON_ICO.exists():
                # On Windows, iconbitmap with default= applies to all toplevels.
                self.root.iconbitmap(default=str(_ICON_ICO))
                return
            if _ICON_PNG.exists():
                # Keep a Python reference so Tk's image isn't garbage-collected.
                self._app_icon = tk.PhotoImage(file=str(_ICON_PNG))
                # Schedule iconphoto *after* the window is actually mapped so
                # the compositor sees the hint on the first expose event.
                # Calling it during __init__ (before mainloop) is ignored by
                # some X11/Wayland compositors (Cosmic, GNOME, etc.).
                def _apply_icon() -> None:
                    try:
                        self.root.iconphoto(True, self._app_icon)
                    except Exception:  # noqa: BLE001
                        pass
                self.root.after(50, _apply_icon)
        except Exception as exc:  # noqa: BLE001 — icon is purely cosmetic
            print(f"[stickitto] could not load app icon: {exc}", file=sys.stderr)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About StickItToMe",
            f"StickItToMe v{__version__}\n\n"
            "A lightweight stick-figure drawing tool\n"
            "for creating ComfyUI ControlNet pose images.\n\n"
            f"Python {sys.version.split()[0]} · tkinter {self.root.tk.call('info', 'patchlevel')}",
        )

    def _show_shortcuts(self) -> None:
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Tools:           H head · L limb · J joint · F figure · E erase · M move\n"
            "File:            Ctrl+N new · Ctrl+O open · Ctrl+S save PNG\n"
            "                 Ctrl+Shift+S save JPG · Ctrl+Q quit\n"
            "Edit:            Ctrl+Z undo · Ctrl+Y redo · Ctrl+M mirror\n"
            "                 I invert colors\n"
            "Style:           + / - line width · [ / ] head radius",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_dark(color: str) -> bool:
    """Return True if ``color`` (a CSS-style name or #rrggbb) is roughly dark."""
    color = color.strip().lower()
    table = {
        "black": True, "white": False,
        "red": True, "green": True, "blue": True,
        "yellow": False, "cyan": False, "magenta": True,
        "gray": True, "grey": True,
    }
    if color in table:
        return table[color]
    if color.startswith("#") and len(color) == 7:
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            return luminance < 0.5
        except ValueError:
            return True
    # default to dark
    return True


class _SizeDialog:
    """Tiny modal for entering a custom canvas size."""

    def __init__(self, parent: tk.Misc) -> None:
        self.result: Optional[Tuple[int, int]] = None
        self.top = tk.Toplevel(parent)
        self.top.title("Custom canvas size")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        frm = ttk.Frame(self.top, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Width:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Label(frm, text="Height:").grid(row=1, column=0, sticky="e", padx=4, pady=4)

        self._w = tk.StringVar(value="768")
        self._h = tk.StringVar(value="768")
        ttk.Entry(frm, textvariable=self._w, width=8).grid(row=0, column=1, padx=4, pady=4)
        ttk.Entry(frm, textvariable=self._h, width=8).grid(row=1, column=1, padx=4, pady=4)

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=(8, 0))
        ttk.Button(btns, text="OK", command=self._ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(side=tk.LEFT, padx=4)

        self.top.bind("<Return>", lambda _e: self._ok())
        self.top.bind("<Escape>", lambda _e: self.top.destroy())

    def _ok(self) -> None:
        try:
            w = int(self._w.get())
            h = int(self._h.get())
        except ValueError:
            messagebox.showerror("Invalid size", "Width and height must be integers.", parent=self.top)
            return
        if w <= 0 or h <= 0 or w > 4096 or h > 4096:
            messagebox.showerror(
                "Invalid size", "Width and height must be between 1 and 4096.", parent=self.top,
            )
            return
        self.result = (w, h)
        self.top.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    root = tk.Tk(className="stickittome")
    StickfigureApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()