#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"

RESEARCH_LOG = OUTPUT / "research_log.jsonl"
LATENT_DYNAMICS = OUTPUT / "latent_dynamics_memory.jsonl"
LATENT_ATLAS = OUTPUT / "latent_atlas_memory.jsonl"
SCORECARD = OUTPUT / "recommendation_scorecard.jsonl"
EVIDENCE_DRAFTS = OUTPUT / "evidence_drafts.jsonl"

def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except Exception:
            pass
    return rows


def evidence_key(item):
    text = "|".join([
        str(item.get("type", "")),
        str(item.get("hypothesis", "")),
        str(item.get("direction", "")),
        str(item.get("source", "")),
        str(item.get("evidence", "")),
    ])
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def existing_evidence_keys():
    keys = set()
    for path in [EVIDENCE_DRAFTS, RESEARCH_LOG]:
        for item in read_jsonl(path):
            keys.add(evidence_key(item))
    return keys


def append_jsonl(path, item):
    OUTPUT.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(item) + "\n")

def rewrite_jsonl(path, rows):
    OUTPUT.mkdir(exist_ok=True)
    path.write_text("")
    for row in rows:
        append_jsonl(path, row)

def classify_direction(text):
    low = text.lower()
    positive = ["improved", "decreased", "reduced", "lower", "smoother", "organized", "helped"]
    negative = ["worsened", "increased", "unstable", "failure", "jagged", "rollback"]
    pos = sum(1 for w in positive if w in low)
    neg = sum(1 for w in negative if w in low)
    if pos > neg:
        return "support"
    if neg > pos:
        return "against"
    return "mixed"

def latest_hypothesis():
    rows = read_jsonl(RESEARCH_LOG)
    hypotheses = [r for r in rows if r.get("type") == "hypothesis"]
    if not hypotheses:
        return "Focused practice makes latent dynamics more organized by reducing surprise and smoothing hidden-state paths."
    return hypotheses[-1].get("title") or hypotheses[-1].get("claim") or "latest hypothesis"

def build_latest_latent_dynamics_evidence():
    rows = read_jsonl(LATENT_DYNAMICS)
    if not rows:
        return None

    item = rows[-1]
    stage = item.get("stage", "unknown")
    delta = item.get("delta") or {}
    interp = item.get("interpretation") or []

    pieces = []
    pieces.append(f"Latent Dynamics Viewer saved a before/after report for stage `{stage}`.")

    for key in [
        "mean_abs_prediction_error_change_pct",
        "mean_surprise_change_pct",
        "smoothness_ratio_change_pct",
        "state_spread_change_pct",
    ]:
        if key in delta:
            pieces.append(f"{key}: {delta.get(key)}")

    if interp:
        pieces.append("Interpretation: " + " ".join(str(x) for x in interp))

    text = " ".join(pieces)

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "evidence",
        "hypothesis": latest_hypothesis(),
        "direction": classify_direction(text),
        "evidence": text,
        "source": "output/latent_dynamics_memory.jsonl",
        "notes": "Auto-drafted by Evidence Integration Suite from latest latent dynamics report.",
        "draft_status": "draft",
    }

def build_latest_atlas_evidence():
    rows = read_jsonl(LATENT_ATLAS)
    if not rows:
        return None

    item = rows[-1]
    stages = item.get("stages", [])
    interpretation = item.get("interpretation", [])
    summary = item.get("summary", [])

    text = (
        "Latent Atlas compared stages: "
        + ", ".join(stages)
        + ". "
        + "Interpretation: "
        + " ".join(str(x) for x in interpretation)
    )

    if summary:
        text += f" Atlas contained {len(summary)} stage summaries."

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "evidence",
        "hypothesis": latest_hypothesis(),
        "direction": classify_direction(text),
        "evidence": text,
        "source": "output/latent_atlas_memory.jsonl",
        "notes": "Auto-drafted by Evidence Integration Suite from latest latent atlas report.",
        "draft_status": "draft",
    }

def build_latest_scorecard_evidence():
    rows = read_jsonl(SCORECARD)
    if not rows:
        return None

    item = rows[-1]
    stage = item.get("weakest_stage", "unknown")
    improvement = item.get("eval_loss_improvement_pct")
    companion = item.get("companion_class") or item.get("companion_trust") or ""

    text = (
        f"Recommendation scorecard recorded latest practice result for stage `{stage}`. "
        f"Improvement percent: {improvement}. "
    )

    if companion:
        text += f"Companion classification/trust: {companion}."

    direction = "mixed"
    try:
        if improvement is not None and float(improvement) > 0:
            direction = "support"
        elif improvement is not None and float(improvement) <= 0:
            direction = "against"
    except Exception:
        direction = classify_direction(text)

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "evidence",
        "hypothesis": latest_hypothesis(),
        "direction": direction,
        "evidence": text,
        "source": "output/recommendation_scorecard.jsonl",
        "notes": "Auto-drafted by Evidence Integration Suite from latest scorecard result.",
        "draft_status": "draft",
    }

def draft(args):
    drafts = []
    skipped = 0
    existing = existing_evidence_keys()

    for fn in [
        build_latest_latent_dynamics_evidence,
        build_latest_atlas_evidence,
        build_latest_scorecard_evidence,
    ]:
        item = fn()
        if not item:
            continue

        key = evidence_key(item)

        if key in existing:
            skipped += 1
            continue

        drafts.append(item)
        existing.add(key)
        append_jsonl(EVIDENCE_DRAFTS, item)

    print(f"Created {len(drafts)} new evidence drafts.")
    print(f"Skipped {skipped} duplicate drafts.")

    for d in drafts:
        print(f"- {d['direction']}: {d['source']}")

    return 0

def approve_latest(args):
    drafts = read_jsonl(EVIDENCE_DRAFTS)
    if not drafts:
        print("No evidence drafts found.")
        return 1

    latest = drafts[-1]
    latest["draft_status"] = "approved"
    latest["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_jsonl(RESEARCH_LOG, latest)
    print("Approved latest evidence draft into research log.")
    print(latest.get("evidence", ""))
    return 0

def approve_all(args):
    drafts = read_jsonl(EVIDENCE_DRAFTS)
    if not drafts:
        print("No evidence drafts found.")
        return 1

    directions = set(getattr(args, "direction", []) or [])
    limit = getattr(args, "limit", 0) or 0
    research_keys = {evidence_key(item) for item in read_jsonl(RESEARCH_LOG)}
    count = 0
    skipped_approved = 0
    skipped_duplicate = 0
    skipped_direction = 0

    for item in drafts:
        if item.get("draft_status") == "approved":
            skipped_approved += 1
            continue
        if directions and item.get("direction") not in directions:
            skipped_direction += 1
            continue
        if evidence_key(item) in research_keys:
            item["draft_status"] = "approved"
            item["approved_at"] = item.get("approved_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            skipped_duplicate += 1
            continue
        if limit and count >= limit:
            continue

        item["draft_status"] = "approved"
        item["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        append_jsonl(RESEARCH_LOG, item)
        research_keys.add(evidence_key(item))
        count += 1

    rewrite_jsonl(EVIDENCE_DRAFTS, drafts)

    print(f"Approved {count} evidence drafts into research log.")
    print(f"Skipped already approved: {skipped_approved}")
    print(f"Marked duplicate existing evidence as approved: {skipped_duplicate}")
    print(f"Skipped by direction filter: {skipped_direction}")
    return 0

def bulk_status(args):
    drafts = read_jsonl(EVIDENCE_DRAFTS)
    research = read_jsonl(RESEARCH_LOG)
    research_keys = {evidence_key(item) for item in research}
    pending = [item for item in drafts if item.get("draft_status") != "approved"]
    duplicate_pending = [item for item in pending if evidence_key(item) in research_keys]
    by_direction = {}
    for item in pending:
        direction = item.get("direction", "mixed")
        by_direction[direction] = by_direction.get(direction, 0) + 1
    status = {
        "drafts": len(drafts),
        "approved_drafts": len([item for item in drafts if item.get("draft_status") == "approved"]),
        "pending_drafts": len(pending),
        "pending_duplicates_already_in_research": len(duplicate_pending),
        "pending_by_direction": by_direction,
        "research_records": len(research),
        "research_evidence": len([item for item in research if item.get("type") == "evidence"]),
    }
    print(json.dumps(status, indent=2))
    return 0

def list_drafts(args):
    drafts = read_jsonl(EVIDENCE_DRAFTS)
    if not drafts:
        print("No drafts found.")
        return 0

    for i, d in enumerate(drafts, start=1):
        print(f"{i}. [{d.get('draft_status')}] {d.get('direction')} | {d.get('source')}")
        print(f"   {d.get('evidence')}")
    return 0

def build_parser():
    parser = argparse.ArgumentParser(description="Foundation Evidence Integrator")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("draft")
    p.set_defaults(func=draft)

    p = sub.add_parser("approve-latest")
    p.set_defaults(func=approve_latest)

    p = sub.add_parser("approve-all")
    p.add_argument(
        "--direction",
        action="append",
        choices=["support", "mixed", "against"],
        help="Optional direction filter. Can be repeated.",
    )
    p.add_argument("--limit", type=int, default=0, help="Optional maximum number of pending drafts to approve.")
    p.set_defaults(func=approve_all)

    p = sub.add_parser("bulk-status")
    p.set_defaults(func=bulk_status)

    p = sub.add_parser("list")
    p.set_defaults(func=list_drafts)

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
