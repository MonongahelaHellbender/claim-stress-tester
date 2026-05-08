from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs"

TRUTHS_PATH = DATA / "known_truths.json"
DIMENSIONS_PATH = DATA / "structural_dimensions.json"
LATEST_PATH = OUTPUT / "claim_bridge_latest.json"
HISTORY_PATH = OUTPUT / "claim_bridge_history.jsonl"
DOC_PATH = DOCS / "CLAIM_BRIDGE.md"


DOMAIN_KEYWORDS = {
    "scientific_claim": [
        "claim",
        "hypothesis",
        "evidence",
        "study",
        "research",
        "finding",
        "result",
        "experiment",
        "data",
        "publication",
        "paper",
        "peer review",
    ],
    "ai_safety": [
        "ai",
        "model",
        "safety",
        "drift",
        "failure",
        "hallucination",
        "benchmark",
        "alignment",
        "monitor",
        "constraint",
        "bias",
    ],
    "carbon_climate": [
        "carbon",
        "capture",
        "sequestration",
        "co2",
        "emission",
        "climate",
        "basalt",
        "weathering",
        "drawdown",
        "mineralization",
    ],
    "materials_science": [
        "battery",
        "electrolyte",
        "lithium",
        "conductivity",
        "sulfide",
        "dft",
        "band gap",
        "synthesis",
        "crystal",
        "oxide",
    ],
    "math_pattern": [
        "math",
        "equation",
        "sequence",
        "pattern",
        "function",
        "proof",
        "geometry",
        "symbol",
        "predict",
    ],
    "cosmology": [
        "hubble",
        "expansion",
        "universe",
        "cosmological",
        "dark energy",
        "dark matter",
        "redshift",
        "cmb",
        "bao",
        "concordance",
        "tension",
        "h0",
        "lambda",
        "omega",
        "lcdm",
        "supernova",
        "planck",
    ],
    "genetics_biology": [
        "gene",
        "allele",
        "selection",
        "fitness",
        "snp",
        "qtl",
        "gwas",
        "trait",
        "population",
        "drift",
        "codon",
        "protein",
        "expression",
        "heritability",
        "linkage",
    ],
    "general_problem": [
        "problem",
        "question",
        "issue",
        "topic",
        "subject",
    ],
}

STRESS_TEST_ROUTES = {
    "null_result": ["absence", "null", "no effect", "failed to show", "negative result", "inconclusive"],
    "source_conflict": ["conflict", "contradicts", "disagrees", "inconsistent", "opposing", "contradiction"],
    "stale_truth": ["outdated", "superseded", "revised", "retracted", "overturned", "no longer", "stale"],
    "evidence_quality": ["evidence", "study", "sample size", "replication", "peer review", "methodology"],
    "scope_check": ["claim", "generalize", "applies to", "in all cases", "always", "never", "universal"],
}


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=True) + "\n")


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def phrase_hits(text: str, words: list[str]) -> int:
    lower = text.lower()
    text_tokens = set(tokens(text))
    score = 0
    for word in words:
        key = word.lower()
        if " " in key:
            score += 2 if key in lower else 0
        elif key in text_tokens:
            score += 1
    return score


def infer_domain(claim: str) -> dict[str, Any]:
    scores = {
        domain: phrase_hits(claim, keywords)
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best, best_score = ranked[0] if ranked else ("general_problem", 0)
    if best_score <= 0:
        best = "general_problem"
    return {
        "primary": best,
        "scores": scores,
        "confidence": min(1.0, round(best_score / 6, 2)),
    }


def match_stress_tests(claim: str) -> list[dict[str, Any]]:
    routes = []
    for test, words in STRESS_TEST_ROUTES.items():
        score = phrase_hits(claim, words)
        if score:
            routes.append({"test": test, "fit": min(1.0, round(score / 4, 2)), "keywords_matched": score})
    return sorted(routes, key=lambda r: r["fit"], reverse=True)


def match_truths(claim: str, limit: int = 5) -> list[dict[str, Any]]:
    truths = read_json(TRUTHS_PATH, [])
    rows: list[dict[str, Any]] = []
    for truth in truths if isinstance(truths, list) else []:
        haystack = " ".join(
            str(part)
            for part in [
                truth.get("id", ""),
                truth.get("truth", ""),
                truth.get("plain", ""),
                " ".join(truth.get("domains", [])),
                " ".join(truth.get("patterns", [])),
            ]
        )
        overlap = set(tokens(claim)).intersection(tokens(haystack))
        score = len(overlap) + phrase_hits(claim, truth.get("patterns", []))
        if score > 0:
            rows.append(
                {
                    "id": truth.get("id"),
                    "truth": truth.get("truth"),
                    "plain": truth.get("plain"),
                    "score": score,
                    "gap_questions": truth.get("gap_questions", [])[:4],
                }
            )
    return sorted(rows, key=lambda row: row["score"], reverse=True)[:limit]


def match_structural_dimensions(claim: str) -> list[dict[str, Any]]:
    raw = read_json(DIMENSIONS_PATH, {})
    dimensions = raw.get("dimensions", raw) if isinstance(raw, dict) else {}
    matches: list[dict[str, Any]] = []
    for name, spec in dimensions.items():
        keyword_map = spec.get("keywords", {}) if isinstance(spec, dict) else {}
        best_value = "unknown"
        best_score = 0
        best_hits: list[str] = []
        for value, words in keyword_map.items():
            hits = [word for word in words if phrase_hits(claim, [word]) > 0]
            score = len(hits)
            if score > best_score:
                best_value = value
                best_score = score
                best_hits = hits[:5]
        if best_score > 0:
            matches.append(
                {
                    "dimension": name,
                    "value": best_value,
                    "score": best_score,
                    "hits": best_hits,
                    "description": spec.get("description", ""),
                }
            )
    return sorted(matches, key=lambda row: row["score"], reverse=True)


def unknown_flags(claim: str, domain: str) -> list[str]:
    flags = []
    if re.search(r"\b(always|never|all|every|none|proven|fact|definitely)\b", claim.lower()):
        flags.append("Universal quantifier detected — check whether the claim has been tested at the stated scope.")
    if re.search(r"\b(conscious|sentient|self[- ]?aware|feels|thinks)\b", claim.lower()):
        flags.append("Consciousness/experience language detected — verify evidence tier and avoid conflating behavioral with phenomenal claims.")
    if re.search(r"\b(causes|caused by|proves|confirms)\b", claim.lower()):
        flags.append("Causal language detected — check whether evidence establishes correlation, mechanism, or causal chain.")
    if re.search(r"\b(new|novel|first|breakthrough|revolutionary)\b", claim.lower()):
        flags.append("Novelty language detected — verify prior art and whether this is a replication of known findings.")
    return flags


def recommended_stress_tests(domain: str, routes: list[dict[str, Any]]) -> list[str]:
    tests = []
    if routes:
        top = routes[0]["test"]
        tests.append(f"Primary stress test recommended: `{top}`")
    tests += [
        "Check evidence tier: is this observational, experimental, or computational?",
        "Check scope: does the evidence support the stated breadth of the claim?",
        "Check for null results: has this claim failed to replicate anywhere?",
        "Check for source conflicts: does any peer-reviewed literature contradict this?",
        "Check staleness: is there a more recent revision, retraction, or update?",
    ]
    if domain == "ai_safety":
        tests.append("For AI claims: verify whether improvement metrics reflect generalisation or training-set overfitting.")
    if domain in {"carbon_climate", "materials_science"}:
        tests.append("Computational screening results require experimental validation before public claims of discovery.")
    return tests[:6]


def build_claim_bridge(claim: str, save: bool = True) -> dict[str, Any]:
    clean = " ".join(claim.strip().split())
    domain = infer_domain(clean)
    stress_tests = match_stress_tests(clean)
    dimensions = match_structural_dimensions(clean)
    truths = match_truths(clean)
    flags = unknown_flags(clean, domain["primary"])
    packet = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "claim": clean,
        "domain": domain,
        "structural_dimensions": dimensions,
        "truth_constraints": truths,
        "stress_tests": stress_tests,
        "unknown_flags": flags,
        "recommended_stress_tests": recommended_stress_tests(domain["primary"], stress_tests),
        "boundary": {
            "scope": "Routes scientific claims into evidence-quality stress tests.",
            "does_not_verify_claims": True,
            "outputs_are_questions_not_verdicts": True,
        },
    }
    if save:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        DOCS.mkdir(parents=True, exist_ok=True)
        LATEST_PATH.write_text(json.dumps(packet, indent=2, ensure_ascii=True), encoding="utf-8")
        append_jsonl(HISTORY_PATH, packet)
        _write_doc(packet)
    return packet


def _write_doc(packet: dict[str, Any]) -> None:
    tests = packet.get("stress_tests", [])
    dims = packet.get("structural_dimensions", [])
    truths = packet.get("truth_constraints", [])
    lines = [
        "# Claim Bridge",
        "",
        "Routes a scientific claim into structured stress tests.",
        "",
        f"Updated: {packet.get('created_at', '')}",
        "",
        "## Claim Under Review",
        "",
        packet.get("claim", ""),
        "",
        "## Domain",
        "",
        f"- Primary: `{packet.get('domain', {}).get('primary', 'unknown')}`",
        f"- Confidence: `{packet.get('domain', {}).get('confidence', 0)}`",
        "",
        "## Stress Tests Triggered",
        "",
    ]
    if tests:
        for t in tests:
            lines.append(f"- `{t.get('test')}`: fit `{t.get('fit')}`")
    else:
        lines.append("- No specific stress test triggered — apply general evidence-quality review.")
    lines.extend(["", "## Structural Dimensions", ""])
    if dims:
        for dim in dims[:6]:
            lines.append(f"- `{dim.get('dimension')}` → `{dim.get('value')}`: {dim.get('description')}")
    else:
        lines.append("- No strong structural dimension match.")
    lines.extend(["", "## Truth Constraints", ""])
    if truths:
        for t in truths:
            lines.append(f"- {t.get('truth')} ({t.get('plain')})")
    else:
        lines.append("- No saved constraint matched strongly.")
    lines.extend(["", "## Flags", ""])
    for flag in packet.get("unknown_flags", []) or ["No major flags."]:
        lines.append(f"- {flag}")
    lines.extend(["", "## Recommended Stress Tests", ""])
    for action in packet.get("recommended_stress_tests", []):
        lines.append(f"- {action}")
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_latest_bridge() -> dict[str, Any] | None:
    return read_json(LATEST_PATH, None)


def load_bridge_history(limit: int = 20) -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    rows = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows[-limit:][::-1]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Route a scientific claim into structured stress tests.")
    parser.add_argument("claim", nargs="*", help="The claim to stress-test.")
    args = parser.parse_args()
    text = " ".join(args.claim).strip() or "This intervention always improves outcomes in all populations."
    print(json.dumps(build_claim_bridge(text), indent=2))
