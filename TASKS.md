# Project Tasks

## Backlog

### Replace `sys.path` hacks with `PROJECT_ROOT` env var
**Context:** Scripts under `scripts/ocr/` currently use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))` to reach the project root for imports (e.g. `from scripts.ocr.lib.model_version import ...`). Going up 3 directory levels is fragile and will break if scripts move again.

**Approach:** Define a `PROJECT_ROOT` environment variable (via `.env` file, shell profile, or a small bootstrap script) so all scripts can do:
```python
import os
PROJECT_ROOT = os.environ['PROJECT_ROOT']
sys.path.insert(0, PROJECT_ROOT)
```

**Alternatives considered:**
- **Root marker file**: Walk up directories looking for `.git/` or a sentinel file. More automatic but adds boilerplate to every script.
- **Installable package** (`pyproject.toml`): Make `scripts/` a proper Python package. Cleanest long-term but heavier setup.

**Affected files:** All 9 Python scripts under `scripts/ocr/` and `scripts/ocr/lib/model_version.py`.
