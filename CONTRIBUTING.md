# Contributing to StickItToMe

Thanks for your interest in contributing! This document covers the basics.
For anything not covered here, open an issue and ask.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating you agree to uphold it.

## Reporting bugs

Open an issue and include:

- What you did (steps to reproduce)
- What you expected
- What happened instead
- OS, Python version (`python --version`), Pillow version
  (`python -c "import PIL; print(PIL.__version__)"`)
- If relevant, a screenshot and the `.pose.json` you were working on

## Suggesting features

Open an issue with the `enhancement` label. Briefly describe:

- The problem you're trying to solve
- The proposed solution
- Any alternatives you considered

## Development setup

```bash
git clone https://github.com/Jonesie/stickittome.git
cd stickittome

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .            # editable install

python -m stickitto       # launch the app
```

Make sure `import tkinter` works on your platform before opening a PR — see the
README for OS-specific notes.

## Project layout

```
src/stickitto/
    model.py     — pure-data Pose / Head / Segment / Joint (no tkinter, no PIL)
    exporter.py  — Pillow rendering to PNG / JPG
    io_json.py   — Pose <-> JSON
    app.py       — Tkinter GUI; depends on model + exporter + io_json
    __main__.py  — `python -m stickitto` entry point
```

A guiding principle: **`model.py` has zero non-stdlib imports**. Keep it that
way so people can use the data model in scripts, tests, and notebooks without
pulling in tkinter or PIL.

## Coding style

- Python ≥ 3.9 syntax (`from __future__ import annotations` is used in modules
  that benefit from it; otherwise plain modern Python is fine).
- Type hints on public functions.
- 4-space indents, no tabs.
- Prefer small, focused modules.
- New user-facing actions should also have a keyboard shortcut where it makes
  sense, and should be documented in the menu and the README's shortcut table.

We don't run a strict linter in CI yet; please run `python -m py_compile` over
your changes before pushing.

## Testing

This project doesn't have a formal test suite yet. For now:

1. Smoke-test the imports:
   ```bash
   python -c "from stickitto import model, exporter, io_json, app; print('ok')"
   ```
2. Smoke-test the GUI by launching it and drawing a small pose, then saving as
   PNG and JSON.
3. If you added an exporter change, regenerate the samples with
   `python scripts/make_sample_poses.py`.

When the test suite lands, all PRs will be expected to pass it.

## Commit messages

Short imperative subject line (≤ 72 chars), blank line, optional body.
Examples:

```
Add grip handle to head tool for resizing

Allows the user to click and drag the head's edge to resize it,
matching the limb tool's click-and-drag interaction.
```

## Pull requests

- One feature / fix per PR.
- Update the README if you change user-facing behaviour (especially the
  shortcuts table or the tool list).
- Update the CHANGELOG under `[Unreleased]`.
- If you add a new dependency, justify it in the PR description — the goal is
  to stay lightweight.

## Releasing

Releases are cut from `main`. The release process is manual for now:

1. Bump `__version__` in `src/stickitto/__init__.py`.
2. Move the `[Unreleased]` section in `CHANGELOG.md` to a dated
   `[X.Y.Z] - YYYY-MM-DD` section and add a fresh empty `[Unreleased]`.
3. Tag the commit: `git tag -s vX.Y.Z -m "vX.Y.Z"`.
4. Push the tag: `git push origin vX.Y.Z`.
5. Draft a GitHub release from the tag using the CHANGELOG section.