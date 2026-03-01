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

### Write Tests for Frontend & Backend

Test not only entire processes, but also very atomic functionality.

#### Backend Tests

- [ ] Write a test verifying the entire v3 pipeline with one or more `data/sample_images/*_original.png`, comparing against expected results
- [ ] Write tests verifying category header functionalities (detection, OCR, classification), comparing against expected results
- [ ] Write tests verifying enchant segment functionalities comparing expected results — especially on every stage we do parsing, regexing, or decorating strings:
  - Enchant header detection (white-mask band detection)
  - Enchant line classification (header/effect/grey)
  - Bullet prefix detection and trimming
  - Effect number extraction (`_parse_effect_number`)
  - FM matching for enchant effects (condition-aware number selection)
  - Enchant structured rebuild (`build_enchant_structured`)
  - Enchant resolution (P1/P2/P3 competition)
  - Templated effect text generation

#### Frontend Tests

- [ ] Write a test comparing expected HTML rendering with a sample API result (ExamineItemResponse)
- [ ] Write a test comparing expected form submit payload for given HTML form data (RegisterListingRequest)
- [ ] Write tests for expected behavior on HTML events:
  - Enchant name selection (editingName flow)
  - Effect level commit (commitLevel)
  - Reforge option editing
  - `abbreviated` flag toggle behavior on effect text rebuilding

#### Suggested Test Libraries

**Backend (Python/FastAPI):**
- `pytest` — standard test runner with fixtures, parametrize, and assertion introspection
- `pytest-asyncio` — for async endpoint testing
- `httpx` + `TestClient` (from FastAPI/Starlette) — for API integration tests without starting a server
- `unittest.mock` / `pytest-mock` — for isolating units (e.g., mock OCR reader, DB session)

**Frontend (React/Vite):**
- `vitest` — Vite-native test runner, fast, compatible with Jest API
- `@testing-library/react` — component rendering and DOM assertion
- `@testing-library/user-event` — simulating user interactions (clicks, typing)
- `jsdom` — DOM environment for vitest (configured via `environment: 'jsdom'`)
- `msw` (Mock Service Worker) — mock API responses for integration tests
