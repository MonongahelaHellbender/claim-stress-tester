from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.claim_bridge import build_claim_bridge, load_latest_bridge, load_bridge_history
from tools.evidence_integrator import read_jsonl

OUTPUT = ROOT / "output"


st.set_page_config(page_title="Scientific Claim Stress Tester", page_icon="⚗", layout="wide")
st.markdown("""
<style>
body { font-family: 'IBM Plex Mono', monospace; }
.block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("⚗ Scientific Claim Stress Tester")
st.caption("Routes a claim into evidence-quality stress tests. Does not verify claims — asks better questions.")

st.divider()

default_claim = "This intervention always improves outcomes in all patient populations."

claim_input = st.text_area(
    "Enter a scientific claim to stress-test",
    value=(load_latest_bridge() or {}).get("claim", default_claim),
    height=120,
    key="claim_input",
)

c1, c2 = st.columns([0.3, 0.7])
with c1:
    analyze = st.button("Run Stress Test", type="primary", key="run_stress")
with c2:
    st.caption("Checks scope, evidence quality, null results, source conflicts, and staleness.")

packet = build_claim_bridge(claim_input) if analyze and claim_input.strip() else load_latest_bridge()

if not packet:
    st.info("Enter a claim above and click Run Stress Test.")
    st.stop()

domain = packet.get("domain", {})
tests = packet.get("stress_tests", [])
flags = packet.get("unknown_flags", [])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Domain", str(domain.get("primary", "unknown")).replace("_", " ").title())
m2.metric("Confidence", domain.get("confidence", 0))
m3.metric("Tests triggered", len(tests))
m4.metric("Flags", len(flags))

tab_tests, tab_structure, tab_flags, tab_history = st.tabs(
    ["Stress Tests", "Structure", "Flags", "History"]
)

with tab_tests:
    st.subheader("Recommended stress tests")
    for action in packet.get("recommended_stress_tests", []):
        st.write(f"- {action}")

    if tests:
        st.subheader("Triggered tests")
        for test in tests:
            with st.container(border=True):
                a, b = st.columns([0.3, 0.7])
                a.metric("Test", test.get("test", "unknown").replace("_", " ").title())
                a.metric("Fit", test.get("fit", 0))
                b.write(f"Keywords matched: {test.get('keywords_matched', 0)}")
    else:
        st.info("No specific stress test triggered by this claim — apply general evidence-quality review.")

    st.divider()
    st.caption(
        "This tool asks questions. It does not verify claims, produce verdicts, or make evidence determinations. "
        "All outputs are structured prompts for human review."
    )

with tab_structure:
    st.subheader("Structural dimensions")
    dims = packet.get("structural_dimensions", [])
    if dims:
        st.dataframe(dims, use_container_width=True, hide_index=True)
    else:
        st.info("No strong structural dimension match.")

    truths = packet.get("truth_constraints", [])
    if truths:
        st.subheader("Constraint library matches")
        st.dataframe(truths, use_container_width=True, hide_index=True)
    else:
        st.info("No saved truth constraint matched strongly.")

with tab_flags:
    st.subheader("Language flags")
    for flag in flags or ["No major flags detected."]:
        st.write(f"- {flag}")
    st.divider()
    st.caption("Flags highlight language patterns that often signal scope problems, causal overclaiming, or missing evidence qualifications.")

with tab_history:
    st.subheader("Recent analyses")
    history = load_bridge_history(20)
    if history:
        rows = [
            {
                "created_at": item.get("created_at"),
                "domain": item.get("domain", {}).get("primary"),
                "tests": len(item.get("stress_tests", [])),
                "flags": len(item.get("unknown_flags", [])),
                "claim": (item.get("claim") or "")[:80],
            }
            for item in history
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No history yet.")
