#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IMPORTANT_FILES = [
    "tools/claim_bridge.py",
    "tools/evidence_integrator.py",
    "tools/research_synthesizer.py",
    "ui/app.py",
]

IMPORTANT_DATA = [
    "data/known_truths.json",
    "data/structural_dimensions.json",
]


def check_files() -> list[str]:
    issues = []
    for rel in IMPORTANT_FILES:
        path = ROOT / rel
        if not path.exists():
            issues.append(f"MISSING: {rel}")
            continue
        try:
            ast.parse(path.read_text())
        except SyntaxError as exc:
            issues.append(f"SYNTAX ERROR in {rel}: {exc}")
    return issues


def check_data() -> list[str]:
    issues = []
    for rel in IMPORTANT_DATA:
        path = ROOT / rel
        if not path.exists():
            issues.append(f"MISSING DATA: {rel}")
            continue
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            issues.append(f"JSON ERROR in {rel}: {exc}")
    return issues


def run() -> int:
    all_issues = check_files() + check_data()
    if not all_issues:
        print("QC passed — all critical files present and parseable.")
        return 0
    for issue in all_issues:
        print(f"  {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(run())
