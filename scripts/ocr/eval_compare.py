#!/usr/bin/env python3
"""A/B model comparison gate.

Switches between current and candidate model versions, runs test_v3_pipeline.py
with --json on each, compares exact matches and character accuracy.

Usage:
    python3 scripts/ocr/eval_compare.py \
        --model general_mabinogi_classic \
        --current-version a19 --candidate-version a19.1

Gate: candidate must be >= current on BOTH exact matches AND char accuracy.
"""

import argparse
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEST_IMAGES = os.path.join(PROJECT_ROOT, 'data', 'sample_images', '*_original.png')
TEST_SCRIPT = os.path.join(PROJECT_ROOT, 'scripts', 'v3', 'test_v3_pipeline.py')
SWITCH_SCRIPT = os.path.join(PROJECT_ROOT, 'scripts', 'ocr', 'switch_model.sh')


def switch_model(model_type, version):
    """Switch active model to the given version."""
    result = subprocess.run(
        ['bash', SWITCH_SCRIPT, model_type, version],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(f"ERROR switching to {model_type} {version}:")
        print(result.stderr)
        sys.exit(1)


def run_test():
    """Run v3 pipeline test and return JSON metrics."""
    result = subprocess.run(
        [sys.executable, TEST_SCRIPT, TEST_IMAGES, '-q', '--json'],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(f"ERROR running test:")
        print(result.stderr)
        sys.exit(1)

    # Find the JSON line in output (last non-empty line)
    for line in reversed(result.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith('{'):
            return json.loads(line)

    print("ERROR: no JSON output from test script")
    print(result.stdout)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='A/B model comparison gate')
    parser.add_argument('--model', required=True,
                        choices=['general_mabinogi_classic', 'general_nanum_gothic_bold', 'general'])
    parser.add_argument('--current-version', required=True)
    parser.add_argument('--candidate-version', required=True)
    args = parser.parse_args()

    print(f"=== Evaluating current: {args.model} {args.current_version} ===")
    switch_model(args.model, args.current_version)
    current_metrics = run_test()

    print(f"\n=== Evaluating candidate: {args.model} {args.candidate_version} ===")
    switch_model(args.model, args.candidate_version)
    candidate_metrics = run_test()

    # Switch back to current regardless of result
    print(f"\n=== Switching back to current: {args.current_version} ===")
    switch_model(args.model, args.current_version)

    # Comparison table
    print(f"\n{'='*60}")
    print(f"  COMPARISON: {args.current_version} vs {args.candidate_version}")
    print(f"{'='*60}")
    print(f"  {'Metric':<25s}  {'Current':>10s}  {'Candidate':>10s}  {'Delta':>8s}")
    print(f"  {'─'*25}  {'─'*10}  {'─'*10}  {'─'*8}")

    c_exact = current_metrics.get('total_exact', 0)
    c_total = current_metrics.get('total_compared', 1)
    c_acc = current_metrics.get('total_char_accuracy', 0)

    d_exact = candidate_metrics.get('total_exact', 0)
    d_total = candidate_metrics.get('total_compared', 1)
    d_acc = candidate_metrics.get('total_char_accuracy', 0)

    print(f"  {'Exact matches':<25s}  {c_exact:>7d}/{c_total:<3d}  {d_exact:>7d}/{d_total:<3d}  {d_exact - c_exact:>+8d}")
    print(f"  {'Char accuracy':<25s}  {c_acc:>9.1%}  {d_acc:>9.1%}  {d_acc - c_acc:>+7.1%}")

    # Gate
    passed = d_exact >= c_exact and d_acc >= c_acc
    print(f"\n  Gate: {'PASS' if passed else 'FAIL'}")
    if passed:
        print(f"  Candidate is safe to deploy.")
        print(f"  Run: bash scripts/ocr/{args.model}_model/deploy.sh {args.candidate_version}")
    else:
        if d_exact < c_exact:
            print(f"  Regression: exact matches dropped by {c_exact - d_exact}")
        if d_acc < c_acc:
            print(f"  Regression: char accuracy dropped by {c_acc - d_acc:.1%}")

    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
