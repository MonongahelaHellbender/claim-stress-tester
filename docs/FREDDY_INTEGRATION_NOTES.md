# Freddy Integration Notes
*For a future collaboration with an R/Shiny developer*

## What this tool does (plain English)
Scientific Claim Stress Tester routes a scientific claim into a structured set of questions:
- What domain is this? (now includes cosmology, genetics, AI safety, climate)
- What stress tests apply? (scope overclaiming, null results, source conflict, staleness, evidence quality)
- What known structural truths does it bump against? (model degeneracy, population scope, feedback loops, etc.)

Output is JSON — readable from R with `jsonlite::fromJSON()`.

---

## R/Shiny integration path

### Option A: JSON CLI → R consumer (simplest)
Run the tool from R and read the output:

```r
library(jsonlite)
library(processx)

stress_test <- function(claim) {
  # Run the Python CLI, capture output JSON
  run("python3", c("tools/claim_bridge.py", claim),
      wd = "~/Documents/claim-stress-tester")
  result <- fromJSON("output/claim_bridge_latest.json")
  result
}

r <- stress_test("Logarithmic expansion drift resolves the Hubble tension.")
cat("Domain:", r$domain$primary, "\n")
cat("Truth constraints hit:", length(r$truth_constraints), "\n")
```

### Option B: Shiny app wraps the Python tool
A Shiny app can call the CLI and display structured results — the same pattern as the
Streamlit app but in R's ecosystem. Key files to expose:
- `output/claim_bridge_latest.json` — most recent analysis
- `output/claim_bridge_history.jsonl` — history log (one JSON per line)

### Option C: Port the core logic to R (most robust, most work)
The `claim_bridge.py` logic is not complex — keyword matching + JSON output.
A native R version would be faster and avoid the Python dependency.
Core data files needed:
- `data/known_truths.json` — constraint library (7 entries, easy to read as a list in R)
- `data/structural_dimensions.json` — dimension taxonomy

---

## Geometry-Likelihood as a demo claim
The Hubble tension paper (`~/Geometry-Likelihood/`) is a perfect demo case:

```
Claim: "Logarithmic expansion drift and half-turn topology resolve the Hubble tension
        without modifying the standard ΛCDM matter content."

Expected stress-test output:
  - Domain: cosmology ✓
  - Truth constraint: model_degeneracy (multiple models fit same data) ✓
  - Stress tests: scope_check (universal claim), evidence_quality ✓
  - Recommended questions: independent observables, parameter count, held-out validation
```

The MCMC chains and BAO validation in that project are exactly the kind of evidence the
tool asks about — so the paper can serve as a self-contained worked example.

---

## Relevant R packages (Freddy likely knows these)
| Package | Use |
|---|---|
| `jsonlite` | Read/write the tool's JSON output |
| `shiny` | UI wrapper |
| `processx` | Call Python CLI from R |
| `ggplot2` | Visualise r-scores, truth constraint matches |
| `rugarch` / `fGarch` | Market regime work (separate from claim tester) |
| `rrBLUP` / `BGLR` | DGRP/QTL work if genetics results are shared |

---

## What to ask Freddy
- Is he interested in testing scientific claims from his own field in R?
- Would a Shiny UI wrapping this tool be useful for teaching purposes?
- Could the genetics experiments (DGRP, codon evolution) benefit from his R bioinformatics stack?
- Is the Geometry-Likelihood paper something he'd want to run a claim-quality check on?
