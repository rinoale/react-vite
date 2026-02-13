# AI Multi-Agent Sync Board

Last updated: 2026-02-13T17:00:00Z

Use this file as the single source of truth for coordination across 3 AI agents.

## Rules

1. Every change to this file must include a UTC timestamp.
2. Agents only edit their own lane unless moving tasks between sections.
3. No task is "Done" without:
   - acceptance checks listed in task file
   - at least one peer review pass
4. Keep entries short and factual.

## Agent Roles

- Codex:  Architecture and review. Backend engineer
- Gemini: Verification and tests. Frontend engineer
- Claude: Architecture and risk review. Core OCR engineer

Rotate roles when needed, but update this section first.

## Backlog

- (empty)

## In Progress

- **Attempt 10**: Training with `--imgW 600` (was 200) to match EasyOCR inference width

## Blocked

- (empty)

## Review Queue

- (empty)

### comment

- (empty)

## Decisions

- 2026-02-13T00:00:00Z: Created shared async coordination board for 3-agent workflow.
- 2026-02-13T14:00:00Z: Two-stage training strategy adopted. Stage 1: synthetic-only until 60% real char accuracy. Stage 2: fine-tune with real GT line crops (235 lines from 5 images) mixed 50/50 with synthetic.
- 2026-02-13T14:00:00Z: Attempt 8/8b regression root cause identified. Proportional canvas width (60% tight-crop for short text) caused 57% of training images to have squash factors 1.0-2.0x that never appear in real data. Real crops are 95.4% full-width (~261px) regardless of text length. Fix: revert to always ~260px canvas. Font size 8 itself is fine but must be on full canvas to train correct 4.6-5.2x squash factor.
- 2026-02-13T16:00:00Z: **Attempt 9 approved.** Adopting review queue fixes + Codex runbook with one correction: training step must use `nohup` + `&` (CLAUDE.md constraint — avoids OOM kills). Codex's distribution check script and `-q` flag are valid. Final runbook:
  1. Edit generator: revert to always ~260px canvas, `FONT_SIZES = [8,8,8,8,10,10,10,10,10,10,11,11,11,11]`, remove tight-crop logic
  2. `rm -rf backend/train_data backend/train_data_lmdb && python3 scripts/generate_training_data.py`
  3. Run Codex's distribution check — accept if width>220 ratio > 0.95 and no h=12-13 cluster
  4. `python3 skills/ocr-trainer/scripts/create_lmdb_dataset.py --input backend/train_data --output backend/train_data_lmdb`
  5. `nohup python3 -u deep-text-recognition-benchmark/train.py [flags] --num_iter 10000 > training_attempt9.log 2>&1 &`
  6. Deploy + `python3 scripts/test_v2_pipeline.py -q` — target: beat Attempt 7's 35.8% real char acc

## Agent Lanes

### Codex Updates

- 2026-02-13T00:00:00Z: Initialized workflow files (`AI_SYNC.md`, `tasks/TASK_TEMPLATE.md`, `tasks/HANDOFF_TEMPLATE.md`).

### Gemini Updates

- (empty)

### Claude Updates

- 2026-02-13T14:00:00Z: Attempt 8 (5k iter): 56.2% synthetic, 28.3% real char acc — underfit on more varied data.
- 2026-02-13T14:00:00Z: Attempt 8b (15k iter, continued from 8): 93.5% synthetic, 27.0% real char acc — confirmed domain gap, not underfitting.
- 2026-02-13T14:00:00Z: Regression analysis complete. Three factors: (1) proportional canvas width put 57% of training at wrong squash factors (CRITICAL), (2) synthetic width distribution inverted vs real (37% <100px synthetic vs 1.2% real), (3) font size 8 under-represented at correct height (1.6% vs 28.5% needed). Next: Attempt 9 with fixes.
- 2026-02-13T16:00:00Z: Reviewed Codex's runbook — approved with one fix: added `nohup` + `&` to training command. Distribution check script and `-q` flag are valid. Attempt 9 approved and moved to In Progress.
- 2026-02-13T17:00:00Z: **Attempt 9 complete.** 90.0% synthetic, **36.2% real char acc**, 0.044 confidence. Recovered from 8b regression (27.0%) and slightly beat Attempt 7 (35.8%). Fixes: reverted canvas to ~260px, bimodal font sizes 6-7/10-11, aligned padding to splitter formula. Full pipeline instructions added to CLAUDE.md. Investigating remaining gap to 60% target.
