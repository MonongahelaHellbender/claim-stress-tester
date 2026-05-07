#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs"

RESEARCH_LOG = OUTPUT / "research_log.jsonl"
EXPERIMENT_LOG = OUTPUT / "experiment_plans.jsonl"
EVIDENCE_DRAFTS = OUTPUT / "evidence_drafts.jsonl"
SCORECARD = OUTPUT / "recommendation_scorecard.jsonl"
LATENT_DYNAMICS = OUTPUT / "latent_dynamics_memory.jsonl"
LATENT_ATLAS = OUTPUT / "latent_atlas_memory.jsonl"
LATEST_FULL_CYCLE = OUTPUT / "latest_full_cycle.json"
CONFIRMATION = OUTPUT / "confirmation_latest.json"
RUN_RECOMMENDATION = OUTPUT / "run_recommendation.json"
TRAINING_UPDATE = OUTPUT / "training_update.json"

SYNTHESIS_JSON = OUTPUT / "research_synthesis.json"
SYNTHESIS_MD = DOCS / "RESEARCH_SYNTHESIS.md"


def read_jsonl(path: Path) -> list[dict]:
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


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def evidence_key(row: dict) -> str:
    text = "|".join([
        str(row.get("hypothesis", "")),
        str(row.get("direction", "")),
        str(row.get("source", "")),
        str(row.get("evidence", "")),
    ])
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def compact_text(text: str, limit: int = 280) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def infer_stage(text: str) -> str:
    text = str(text or "")
    known = [
        "nested_rule",
        "noise_then_stability",
        "stability_then_noise",
        "entropy_ramp",
        "noise_tolerance",
        "spike_then_recovery",
        "sine",
    ]

    for stage in known:
        if stage in text:
            return stage

    return "unknown"


def score_evidence(row: dict) -> int:
    evidence = str(row.get("evidence", "")).lower()
    direction = row.get("direction", "mixed")

    score = 1

    metric_words = [
        "prediction error",
        "mean surprise",
        "improved",
        "decreased",
        "worsened",
        "failure",
        "rollback",
        "smoothness",
        "state_spread",
        "eval loss",
    ]

    score += sum(1 for word in metric_words if word in evidence)

    if direction == "support":
        score += 2
    elif direction == "against":
        score += 2
    elif direction == "mixed":
        score += 1

    if "nested_rule" in evidence:
        score += 1

    return score


def synthesize() -> dict:
    research = read_jsonl(RESEARCH_LOG)
    experiments = read_jsonl(EXPERIMENT_LOG)
    drafts = read_jsonl(EVIDENCE_DRAFTS)
    scorecard = read_jsonl(SCORECARD)
    latent_dynamics = read_jsonl(LATENT_DYNAMICS)
    latent_atlas = read_jsonl(LATENT_ATLAS)
    latest_full_cycle = read_json(LATEST_FULL_CYCLE)
    confirmation = read_json(CONFIRMATION)
    run_recommendation = read_json(RUN_RECOMMENDATION)
    training_update = read_json(TRAINING_UPDATE)

    hypotheses = [r for r in research if r.get("type") == "hypothesis"]
    evidence = [r for r in research if r.get("type") == "evidence"]

    evidence_counts = Counter(e.get("direction", "unknown") for e in evidence)
    experiment_counts = Counter(e.get("status", "unknown") for e in experiments)

    unique_evidence = {}
    duplicate_count = 0

    for row in evidence:
        key = evidence_key(row)
        if key in unique_evidence:
            duplicate_count += 1
            continue
        unique_evidence[key] = row

    unique_rows = list(unique_evidence.values())
    unique_counts = Counter(e.get("direction", "unknown") for e in unique_rows)

    by_stage = defaultdict(list)
    for row in unique_rows:
        stage = infer_stage(row.get("evidence", "") + " " + row.get("source", ""))
        by_stage[stage].append(row)

    stage_summary = []
    for stage, rows in sorted(by_stage.items()):
        counts = Counter(r.get("direction", "unknown") for r in rows)
        stage_summary.append({
            "stage": stage,
            "total": len(rows),
            "support": counts.get("support", 0),
            "against": counts.get("against", 0),
            "mixed": counts.get("mixed", 0),
        })

    strongest_support = sorted(
        [r for r in unique_rows if r.get("direction") == "support"],
        key=score_evidence,
        reverse=True,
    )[:5]

    strongest_against = sorted(
        [r for r in unique_rows if r.get("direction") == "against"],
        key=score_evidence,
        reverse=True,
    )[:5]

    strongest_mixed = sorted(
        [r for r in unique_rows if r.get("direction") == "mixed"],
        key=score_evidence,
        reverse=True,
    )[:5]

    latest_latent = latest_full_cycle.get("latent_report") or (latent_dynamics[-1] if latent_dynamics else {})
    latest_scorecard = scorecard[-1] if scorecard else {}

    next_action = choose_next_action(
        unique_counts=unique_counts,
        experiments=experiments,
        stage_summary=stage_summary,
        latest_latent=latest_latent,
        latest_scorecard=latest_scorecard,
        latest_full_cycle=latest_full_cycle,
        confirmation=confirmation,
        run_recommendation=run_recommendation,
    )

    conclusion = build_conclusion(unique_counts, stage_summary, latest_full_cycle, confirmation)

    synthesis = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "hypotheses": len(hypotheses),
            "research_evidence_records": len(evidence),
            "unique_evidence_records": len(unique_rows),
            "duplicate_evidence_records_detected": duplicate_count,
            "evidence_drafts": len(drafts),
            "experiment_plans": len(experiments),
            "scorecard_records": len(scorecard),
            "latent_dynamics_reports": len(latent_dynamics),
            "latent_atlas_reports": len(latent_atlas),
        },
        "evidence_counts_all": dict(evidence_counts),
        "evidence_counts_unique": dict(unique_counts),
        "experiment_status_counts": dict(experiment_counts),
        "stage_summary": stage_summary,
        "strongest_support": simplify_evidence_list(strongest_support),
        "strongest_against": simplify_evidence_list(strongest_against),
        "strongest_mixed": simplify_evidence_list(strongest_mixed),
        "latest_latent_report": summarize_latest_latent(latest_latent),
        "latest_full_cycle": summarize_latest_full_cycle(latest_full_cycle),
        "latest_confirmation": summarize_confirmation(confirmation),
        "training_update": summarize_training_update(training_update),
        "run_recommendation": run_recommendation,
        "latest_scorecard": latest_scorecard,
        "current_conclusion": conclusion,
        "recommended_next_action": next_action,
    }

    return synthesis


def simplify_evidence_list(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            "direction": row.get("direction"),
            "hypothesis": row.get("hypothesis"),
            "source": row.get("source"),
            "stage": infer_stage(row.get("evidence", "")),
            "evidence": compact_text(row.get("evidence", ""), 450),
            "notes": compact_text(row.get("notes", ""), 240),
        })
    return out


def summarize_latest_latent(row: dict) -> dict:
    if not row:
        return {}

    return {
        "created_at": row.get("created_at"),
        "stage": row.get("stage"),
        "module": row.get("module"),
        "before_loss": row.get("before_loss"),
        "after_loss": row.get("after_loss"),
        "delta": row.get("delta", {}),
        "interpretation": row.get("interpretation", []),
    }


def summarize_latest_full_cycle(row: dict) -> dict:
    if not row:
        return {}
    latent = row.get("latent_report", {})
    return {
        "created_at": row.get("created_at"),
        "stage": row.get("stage"),
        "status": row.get("status"),
        "before_loss": latent.get("before_loss"),
        "after_loss": latent.get("after_loss"),
        "delta": latent.get("delta", {}),
        "interpretation": latent.get("interpretation", []),
    }


def summarize_confirmation(row: dict) -> dict:
    if not row:
        return {}
    reliability = row.get("reliability", {})
    return {
        "created_at": row.get("created_at"),
        "stage": row.get("config", {}).get("stage"),
        "decision": reliability.get("decision"),
        "pass_rate": reliability.get("pass_rate"),
        "prediction_error_change_mean": reliability.get("prediction_error_change_pct", {}).get("mean"),
        "mean_surprise_change_mean": reliability.get("mean_surprise_change_pct", {}).get("mean"),
        "next_action": reliability.get("next_action"),
    }


def summarize_training_update(row: dict) -> dict:
    if not row:
        return {}
    latest = row.get("latest", {}) or {}
    confirmation = row.get("confirmation", {}) or {}
    progress = row.get("progress", {}) or {}
    read = row.get("learning_read", {}) or {}
    return {
        "created_at": row.get("created_at"),
        "current_stage": latest.get("stage"),
        "current_status": latest.get("status"),
        "loss_improvement_pct": latest.get("loss_improvement_pct"),
        "prediction_error_change_pct": latest.get("prediction_error_change_pct"),
        "mean_surprise_change_pct": latest.get("mean_surprise_change_pct"),
        "confirmed_stage": confirmation.get("stage"),
        "confirmation_pass_pct": progress.get("confirmation_pass_pct"),
        "plain_english": read.get("plain_english", []),
        "boundary": row.get("boundary"),
    }


def build_conclusion(
    unique_counts: Counter,
    stage_summary: list[dict],
    latest_full_cycle: dict,
    confirmation: dict,
) -> str:
    support = unique_counts.get("support", 0)
    against = unique_counts.get("against", 0)
    mixed = unique_counts.get("mixed", 0)

    nested = next((s for s in stage_summary if s["stage"] == "nested_rule"), None)
    latest_stage = latest_full_cycle.get("stage")
    latest_status = latest_full_cycle.get("status")
    confirmed_stage = confirmation.get("config", {}).get("stage")
    confirmation_decision = confirmation.get("reliability", {}).get("decision")

    if confirmation_decision == "reliable_supported" and latest_stage and latest_stage != confirmed_stage:
        return (
            f"Nested_rule has been confirmed as reliable under the current small architecture. "
            f"The system has advanced to `{latest_stage}`, where the latest run is `{latest_status}`. "
            "The current priority is confirming this newer stage before increasing model size or adding features."
        )

    if support > against and nested and nested.get("support", 0) >= 1 and nested.get("against", 0) >= 1:
        return (
            "Current evidence suggests focused practice can improve latent dynamics, "
            "but the effect depends on stage and settings. Nested_rule appears to have failed under one setting "
            "and improved under safer settings, so training stability is a key variable."
        )

    if support > against:
        return (
            "Current evidence leans supportive: focused practice appears associated with improved latent metrics, "
            "especially when prediction error and mean surprise decrease."
        )

    if against > support:
        return (
            "Current evidence is cautionary: several results weaken the hypothesis or suggest unstable settings. "
            "More controlled retests are needed."
        )

    return (
        "Current evidence is mixed. Continue controlled experiments and avoid drawing a broad conclusion from one stage."
    )


def choose_next_action(
    unique_counts,
    experiments,
    stage_summary,
    latest_latent,
    latest_scorecard,
    latest_full_cycle,
    confirmation,
    run_recommendation,
) -> dict:
    open_plans = [e for e in experiments if e.get("status") in ["planned", "running"]]
    completed = [e for e in experiments if str(e.get("status", "")).startswith("completed")]

    nested = next((s for s in stage_summary if s["stage"] == "nested_rule"), None)
    latest_stage = latest_full_cycle.get("stage")
    latest_status = latest_full_cycle.get("status")
    confirmed_stage = confirmation.get("config", {}).get("stage")
    confirmation_decision = confirmation.get("reliability", {}).get("decision")

    if open_plans:
        return {
            "title": "Update experiment statuses",
            "why": f"There are {len(open_plans)} open/planned experiment records. Mark completed ones so the research board is accurate.",
            "suggested_page": "ui/experiment_center.py",
            "suggested_command": "streamlit run ui/experiment_center.py",
        }

    if (
        nested
        and nested.get("support", 0) >= 1
        and nested.get("against", 0) >= 1
        and confirmation_decision != "reliable_supported"
    ):
        return {
            "title": "Run one confirmation test for nested_rule",
            "why": "Nested_rule has both prior failure evidence and safer-settings support evidence. A repeat test would check reliability.",
            "suggested_page": "ui/latent_dynamics_viewer.py",
            "suggested_command": "streamlit run ui/latent_dynamics_viewer.py",
            "settings": {
                "stage": "nested_rule",
                "steps": 300,
                "batch": 32,
                "hidden": 56,
                "learning_rate": 0.001,
            },
        }

    if confirmation_decision == "reliable_supported" and latest_stage and latest_stage != confirmed_stage:
        settings = {
            "stage": latest_stage,
            "steps": int(run_recommendation.get("steps", 300) or 300),
            "batch": int(run_recommendation.get("batch", 32) or 32),
            "hidden": int(run_recommendation.get("hidden", 56) or 56),
            "learning_rate": float(run_recommendation.get("learning_rate", 0.001) or 0.001),
        }
        return {
            "title": f"Confirm current stage: {latest_stage}",
            "why": (
                f"`{confirmed_stage}` is already confirmed. The latest run advanced to `{latest_stage}` "
                f"and ended `{latest_status}`. Run repeated confirmation before advancing again."
            ),
            "suggested_page": "ui/pages/brains.py",
            "suggested_command": "streamlit run ui/app.py",
            "settings": settings,
        }

    if run_recommendation:
        return {
            "title": run_recommendation.get("title", "Run recommended next step"),
            "why": run_recommendation.get("reason", "Use the current run recommendation."),
            "suggested_page": "ui/full_cycle_center.py",
            "suggested_command": "streamlit run ui/app.py",
            "settings": {
                "stage": run_recommendation.get("stage"),
                "steps": run_recommendation.get("steps"),
                "batch": run_recommendation.get("batch"),
                "hidden": run_recommendation.get("hidden"),
                "learning_rate": run_recommendation.get("learning_rate"),
            },
        }

    if unique_counts.get("mixed", 0) >= unique_counts.get("support", 0):
        return {
            "title": "Clarify mixed evidence with a targeted retest",
            "why": "Mixed evidence is high. Pick one stage and repeat with controlled settings.",
            "suggested_page": "ui/experiment_center.py",
            "suggested_command": "streamlit run ui/experiment_center.py",
        }

    return {
        "title": "Create a release candidate research brief",
        "why": "Evidence is organized enough to generate a clean research brief.",
        "suggested_page": "ui/research_synthesis_center.py",
        "suggested_command": "streamlit run ui/research_synthesis_center.py",
    }


def write_markdown(synthesis: dict) -> None:
    DOCS.mkdir(exist_ok=True)

    lines = []
    lines.append("# Foundation Research Synthesis")
    lines.append("")
    lines.append(f"Generated: {synthesis['created_at']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key, value in synthesis["summary"].items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("## Current Conclusion")
    lines.append("")
    lines.append(synthesis["current_conclusion"])

    latest = synthesis.get("latest_full_cycle", {})
    if latest:
        lines.append("")
        lines.append("## Latest Full Cycle")
        lines.append("")
        lines.append(f"- Stage: {latest.get('stage')}")
        lines.append(f"- Status: {latest.get('status')}")
        lines.append(f"- Before loss: {latest.get('before_loss')}")
        lines.append(f"- After loss: {latest.get('after_loss')}")

    confirmation = synthesis.get("latest_confirmation", {})
    if confirmation:
        lines.append("")
        lines.append("## Latest Confirmation")
        lines.append("")
        lines.append(f"- Stage: {confirmation.get('stage')}")
        lines.append(f"- Decision: {confirmation.get('decision')}")
        lines.append(f"- Pass rate: {confirmation.get('pass_rate')}")
        lines.append(f"- Prediction error change mean: {confirmation.get('prediction_error_change_mean')}")

    training_update = synthesis.get("training_update", {})
    if training_update:
        lines.append("")
        lines.append("## Training Update")
        lines.append("")
        for item in training_update.get("plain_english", []):
            lines.append(f"- {item}")
        lines.append(f"- Boundary: {training_update.get('boundary')}")

    lines.append("")
    lines.append("## Evidence Counts - Unique")
    lines.append("")
    for key, value in synthesis["evidence_counts_unique"].items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("## Stage Summary")
    lines.append("")
    for row in synthesis["stage_summary"]:
        lines.append(
            f"- {row['stage']}: total {row['total']}, support {row['support']}, against {row['against']}, mixed {row['mixed']}"
        )

    lines.append("")
    lines.append("## Strongest Support")
    lines.append("")
    for row in synthesis["strongest_support"]:
        lines.append(f"- {row['stage']}: {row['evidence']}")

    lines.append("")
    lines.append("## Strongest Against")
    lines.append("")
    for row in synthesis["strongest_against"]:
        lines.append(f"- {row['stage']}: {row['evidence']}")

    lines.append("")
    lines.append("## Strongest Mixed")
    lines.append("")
    for row in synthesis["strongest_mixed"]:
        lines.append(f"- {row['stage']}: {row['evidence']}")

    lines.append("")
    lines.append("## Recommended Next Action")
    lines.append("")
    action = synthesis["recommended_next_action"]
    lines.append(f"- title: {action.get('title')}")
    lines.append(f"- why: {action.get('why')}")
    lines.append(f"- command: {action.get('suggested_command')}")

    SYNTHESIS_MD.write_text("\n".join(lines) + "\n")


def command_build(args) -> int:
    synthesis = synthesize()
    write_json(SYNTHESIS_JSON, synthesis)
    write_markdown(synthesis)

    print("Research synthesis generated.")
    print(f"JSON: {SYNTHESIS_JSON}")
    print(f"Markdown: {SYNTHESIS_MD}")
    print("")
    print("Conclusion:")
    print(synthesis["current_conclusion"])
    print("")
    print("Recommended next action:")
    action = synthesis["recommended_next_action"]
    print(action.get("title"))
    print(action.get("why"))
    return 0


def command_print(args) -> int:
    if not SYNTHESIS_JSON.exists():
        synthesis = synthesize()
    else:
        synthesis = json.loads(SYNTHESIS_JSON.read_text())

    print(json.dumps(synthesis, indent=2))
    return 0


def command_next(args) -> int:
    synthesis = synthesize()
    action = synthesis["recommended_next_action"]
    print(action.get("title"))
    print(action.get("why"))
    print(action.get("suggested_command"))
    if action.get("settings"):
        print(json.dumps(action["settings"], indent=2))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Foundation Research Synthesizer")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build")
    p.set_defaults(func=command_build)

    p = sub.add_parser("print")
    p.set_defaults(func=command_print)

    p = sub.add_parser("next")
    p.set_defaults(func=command_next)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
