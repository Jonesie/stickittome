# StickItToMe

> A lightweight, cross-platform stick-figure drawing tool for creating
> [ComfyUI](https://github.com/comfyanonymous/ComfyUI) ControlNet pose images.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Dependencies](https://img.shields.io/badge/dependencies-Pillow-blue)

---

## Why?

When using ComfyUI with ControlNet (OpenPose, DWPose, etc.), you often need a
clean stick-figure pose image as input. Existing options are either heavy (full
image editors), constrained (web-based editors), or don't produce the right
output format.

This tool does one thing well: **let you draw a stick figure and save it as a
clean PNG or JPG ready for ControlNet.**

## Features

- 🖌️ **Simple primitives** — head (circle), limb (line segment), joint (dot), erase, move
- 🧍 **Place Stick Figure tool** — click to drop a proportional standing figure, then refine
- 🧩 **Skeleton-aware move** — dragging a joint or a hand/foot keeps the connected bones attached, not floating
- 🎯 **Selection highlight** — the element being moved is outlined while you drag
- 📐 **Preset canvas sizes** for SD 1.5 / SDXL common resolutions
- 🎨 **Color presets** — quick white-on-black / black-on-white, plus custom color pickers
- ↔️ **Mirror horizontally** — draw one side, mirror the other (huge time-saver for symmetric poses)
- ↩️ **Undo / redo** with deep history
- 💾 **Save as PNG or JPG** — PNG preferred for ControlNet
- 📁 **Save / load pose as JSON** — share poses, re-edit later, script them
- 🪶 **Truly lightweight** — single third-party dependency (`Pillow`); the GUI uses Python's bundled `tkinter`
- 🐧 🍎 🪟 **Cross-platform** — Linux, macOS, Windows

## Installation

### From source (recommended for now)

```bash
git clone https://github.com/Jonesie/stickittome.git
cd stickittome

# editable install (so `stickit` is on your PATH)
pip install -e .
```

Or just install the dependency and run from source:

```bash
pip install -r requirements.txt
python -m stickitto
```

### Tkinter

`tkinter` is part of the Python standard library on most platforms, but it is
sometimes packaged separately:

- **Windows / python.org installer**: bundled. ✓
- **macOS / python.org installer**: bundled. ✓
- **macOS / Homebrew**: `brew install python-tk` (the `python-tk` formula matches your Python version).
- **Debian / Ubuntu**: `sudo apt install python3-tk`
- **Fedora**: `sudo dnf install python3-tkinter`
- **Arch**: `sudo pacman -S tk` (already a dep of `python`)

If `python -c "import tkinter"` works, you're set.

## Usage

### Launch

```bash
stickit               # if installed
python -m stickitto   # from source
```

### Tools

| Tool    | What it does                                            |
| ------- | ------------------------------------------------------- |
| Head    | Click to place a head circle                            |
| Limb    | Click and drag to draw a line segment (torso, arms, legs) |
| Joint   | Click to place a small dot (elbows, knees, etc.)        |
| Figure  | Click to drop a proportional standing stick figure, centred on the click |
| Erase   | Click on any element to remove it                       |
| Move    | Click and drag any element to reposition it. Dragging a joint also drags any connected limbs, so the skeleton stays attached. Dragging a hand or foot (an end of a segment) follows the same rule: the connecting joint follows, and the next limb rotates around its far joint. The selected element is outlined while you drag. |

### Keyboard shortcuts

| Key                | Action                              |
| ------------------ | ----------------------------------- |
| `H` / `L` / `J`    | Head / Limb / Joint tool            |
| `E` / `M`          | Erase / Move tool                   |
| `Ctrl+N`           | New (clear)                         |
| `Ctrl+O`           | Open pose JSON                      |
| `Ctrl+S`           | Save PNG                            |
| `Ctrl+Shift+S`     | Save JPG                            |
| `Ctrl+Z` / `Ctrl+Y`| Undo / Redo                         |
| `Ctrl+M`           | Mirror horizontally                 |
| `I`                | Invert colors (swap BG ↔ FG)        |
| `+` / `-`          | Increase / decrease line width      |
| `[` / `]`          | Decrease / increase head radius     |
| `Ctrl+Q`           | Quit                                |

### Output

- **PNG** — lossless. Preferred for ControlNet.
- **JPG** — smaller files, slight quality loss.
- **Pose JSON (`.pose.json`)** — round-trippable; lets you re-open a pose and
  keep editing.

The exported image is rasterized at the canvas size using rounded line caps
and filled endpoints, so what you save looks clean when fed into OpenPose /
DWPose preprocessing.

## Tips for ControlNet

- **Stick figure isolation matters.** Avoid stray dots or background noise —
  OpenPose / DWPose will sometimes try to detect them as joints.
- **Match the aspect ratio of your generation.** ControlNet resizes internally,
  but extreme aspect-ratio mismatches reduce accuracy. Pick a preset that
  matches your generation resolution.
- **Connect joints.** End of one segment = start of the next. Don't leave
  gaps between shoulder and elbow.
- **White-on-black vs black-on-white.** OpenPose accepts both. White-on-black
  is the historical default; some newer models (DWPose, etc.) handle
  black-on-white equally well. Try both if one fails.
- **Thicker lines, more padding.** A line width of 8–14 with ~10% padding
  around the figure tends to work well. The defaults (line 12, head 30) are a
  good starting point.

## Project structure

```
stickittome/
├── src/stickitto/        # application code
│   ├── __init__.py
│   ├── __main__.py         # `python -m stickitto`
│   ├── app.py              # tkinter GUI
│   ├── model.py            # Pose, Head, Segment, Joint dataclasses
│   ├── exporter.py         # PIL-based PNG / JPG rendering
│   ├── io_json.py          # .pose.json save/load
│   ├── icon.png            # bundled app icon (256×256 RGBA, rounded)
│   └── icon.ico            # bundled Windows icon (multi-size)
├── scripts/                # helper scripts (sample pose generator, …)
├── examples/               # sample pose JSON files + rendered PNGs
├── docs/                   # longer-form documentation (if any)
├── pyproject.toml
├── requirements.txt
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── SECURITY.md
```

## Scripting without the GUI

The core data model is dependency-free, so you can build poses from code:

```python
from stickitto.model import Pose, place_stick_figure
from stickitto.exporter import export_png

pose = Pose()
place_stick_figure(pose, center_x=256, center_y=256, target_height=358)

export_png(pose, 512, 512, "standing.pose.png")
```

See `scripts/make_sample_poses.py` for a runnable example.

## Contributing

Contributions welcome — bug reports, feature requests, PRs. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- Built for the ComfyUI / ControlNet community.
- Inspired by tools like
  [OpenPose Editor](https://github.com/huchenlei/sd-webui-openpose-editor)
  and the various Stable Diffusion pose editors out there.