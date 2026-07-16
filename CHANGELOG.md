# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **App icon.** Bundled `icon.png` (256×256 RGBA with rounded corners) and a
  multi-size `icon.ico` for Windows. Loaded automatically on launch.
- **`Figure` tool (F).** Click anywhere on the canvas to drop a
  proportionally-correct standing stick figure centred on the click point.
  Sized to 70% of the smaller canvas dimension so it stays clear of the
  edges; pulls current head-radius and line-width from the toolbar so the
  placed figure matches the rest of your style. Refine with Move / Erase /
  Limb / Joint afterwards.
- **Smart joint drag.** Moving a joint with the Move tool now also moves
  any segment endpoints that share the joint's position, so connected
  limbs stay attached when you reposition a joint (elbow, knee, shoulder,
  hip).
- **Smart segment drag.** Dragging a segment (e.g. grabbing a hand or a
  foot) also moves any joint at its endpoints, and rotates the adjacent
  segment around its far endpoint, so the skeleton stays connected
  instead of leaving the joint dot floating.
- **Move-tool selection highlight.** When you start dragging an element
  with the Move tool, a dashed amber/azure outline appears around the
  selected element and follows it as you drag. Cleared on release.
- **Scrollbars for large canvases.** The canvas is now wrapped in a
  scrollable frame with H+V scrollbars, plus mouse-wheel binding for
  vertical scroll. Tall canvases like `512×768` or `832×1216` scroll
  smoothly when the window can't fit them. Resizing to a smaller canvas
  resets the view to the top-left.
- **Canvas click-target fix.** The canvas widget no longer fills the
  window via `expand=True` — it now stays at its native image size, so
  clicks outside the canvas image (in the wrap padding) don't reach the
  canvas. Eliminates the dead zone of clicks that silently did nothing on
  tall canvases.
- **`Figure` tool edge clamp.** Clicking near the edges of any canvas
  now clamps the figure's centre point so the placed figure stays fully
  inside the canvas; previously, clicks near the top-left produced figures
  whose head stuck out above the canvas and were partially or fully
  invisible.
- **Move-tool drag bug fix.** The Move tool was previously applying the
  cumulative drag distance on every motion event, so a 30-pixel cursor
  drag could translate an element by 60+ pixels. Each motion event now
  applies only the incremental delta since the last motion.
- Initial public release.

### Changed
- **Project renamed from `stickfigure-pose-drawer` to `StickItToMe`.**
  - Python package: `stickfigure` → `stickitto`
  - Console script: `stickfigure` → `stickit`
  - Repo / folder name: `stickfigure-pose-drawer` → `stickittome`
  - Existing user data is unaffected — the `.pose.json` format is unchanged.

## [0.1.0] - 2026-07-16

### Added
- Head, Limb, Joint, Erase, Move drawing tools.
- Save as PNG / JPG; save and load pose as `.pose.json`.
- Undo / redo with snapshot history.
- Mirror horizontally.
- Color inversion and custom BG / FG color pickers.
- Preset canvas sizes for SD 1.5 / SDXL.
- Keyboard shortcuts for every common action.
- Cross-platform (Linux, macOS, Windows).

[Unreleased]: https://github.com/Jonesie/stickittome/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Jonesie/stickittome/releases/tag/v0.1.0