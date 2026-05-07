# Scientific Claim Stress Tester

A lightweight tool that routes scientific claims into structured evidence-quality stress tests.

It does not verify claims or produce verdicts. It asks better questions.

---

## What it does

Given a claim like *"This intervention always improves outcomes in all populations"*, the tool:

- Identifies the domain (AI safety, materials science, climate, etc.)
- Triggers relevant stress tests: null result, source conflict, stale truth, scope check, evidence quality
- Flags overreaching language: universal quantifiers, causal claims, novelty language
- Matches against a constraint library of known structural truths
- Produces a structured list of questions for human review

---

## Quick start

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

Or run from the command line:

```bash
python tools/claim_bridge.py "Caffeine always improves cognitive performance in all adults."
```

---

## Structure

```
claim-stress-tester/
├── tools/
│   ├── claim_bridge.py        # Core routing logic
│   ├── evidence_integrator.py # Evidence draft and approval workflow
│   ├── research_synthesizer.py# Synthesis over accumulated evidence
│   └── qc_check.py            # File and data integrity check
├── data/
│   ├── known_truths.json      # Constraint library
│   └── structural_dimensions.json
├── ui/
│   └── app.py                 # Streamlit interface
└── output/                    # Generated analysis files (git-ignored)
```

---

## Stress tests

| Test | What it checks |
|---|---|
| `null_result` | Has the claim failed to replicate? Is absence of evidence being ignored? |
| `source_conflict` | Does any peer-reviewed literature directly contradict this? |
| `stale_truth` | Has this been superseded, revised, or retracted? |
| `evidence_quality` | What tier is the evidence: anecdote, correlation, RCT, mechanistic? |
| `scope_check` | Does the evidence support the stated breadth (all, always, never)? |

---

## What this tool is not

- It is not a fact-checker or citation database.
- It does not access the internet.
- It does not produce verdicts — only structured questions.
- Computational screening results (materials, drug candidates) require experimental validation before public claims of discovery.

---

## Data

`data/known_truths.json` — a small library of structural constraints (energy, feedback, thresholds, etc.)
that claims are checked against. Add domain-specific truths to extend coverage.

`data/structural_dimensions.json` — dimension taxonomy for encoding claim structure.
