# settlement mapping visualization study

this directory implements the accepted bounded fictional study. it is not an
accepted settlement-mapping method, an empirical result, or an annotation
platform.

the instrument compares two matched toy-sprint traces. both display continued
deadline-first action under pressure, but the cold analysis disputes whether
scenario-a contains a governing reversal at all. scenario-b retains the old
priority after the owner explicitly replaces it and is the stronger bounded
hysteresis candidate. the display tests whether loop shape can remain separate
from the change condition used to interpret it.

all relations are authored categorical claims. there are no inferred edges,
scores, probabilities, causal weights, private sources, imports, storage,
network requests, accounts, or external assets.

## build and open

from the repository root:

```bash
python3 studies/analysis/settlement-mapping-visualization/build.py --output artifacts/settlement-mapping-visualization/bundle
```

open `artifacts/settlement-mapping-visualization/bundle/index.html` directly in
a browser. no server or dependency installation is required.

the builder refuses an existing destination. use a fresh output directory when
source changes; do not merge generated states.

## verify

```bash
python3 -m unittest discover -s studies/analysis/settlement-mapping-visualization/tests -v
python3 studies/analysis/settlement-mapping-visualization/build.py --output artifacts/settlement-mapping-visualization/bundle --check
node studies/analysis/settlement-mapping-visualization/tests/browser_smoke.mjs http://127.0.0.1:9351
```

the first command checks the contract, deterministic builder, inert payload,
packet separation, and run lifecycle. the second proves that an existing bundle
matches current source exactly.

## cold-analysis packet

the build creates:

- `protocol/stage-a/`: neutral trace, bounded definitions, fixed response form,
  exposure instructions, and a stage manifest;
- `protocol/stage-b/`: the complete visualization, neutral post-reveal prompt,
  and a stage manifest; and
- `protocol/packet-manifest.json`: fingerprints for both frozen stages.

the primary agent is the builder and run steward, never the cold analyst. spawn
at least one sub-agent without inherited conversation and give it only the
stage-a path. preserve and fingerprint the complete return before giving the
same analyst the stage-b path. do not coach between stages.

run records live in ignored
`artifacts/settlement-mapping-visualization/runs/<run-id>/`. validate a complete
receipt with:

```bash
python3 studies/analysis/settlement-mapping-visualization/build.py --validate-run artifacts/settlement-mapping-visualization/runs/<run-id>/run.json
```

the completed final run is `cold-006`, bound to packet-manifest sha-256
`712564f7128281031049e2dd868b93a390560e1621e818c8dabf929464cf0d1e`.
its rendered, interacted reveal agrees on the scenario-b contrast while retaining
scenario-a authority ambiguity, irreversibility alternatives, and
display-induced cueing. cold-002 and cold-004 are explicitly contaminated by
their analysts' own inheritance declarations. cold-001, cold-003, and cold-005
remain preserved but incomplete because their stage-b analyst could not render
and interact with the visualization; cold-003 also exposed and caused repair
of a misleading detail label.

packet isolation is procedural, not a filesystem security boundary. the
built-in model service receives the fictional prompt and packet. “cold” means
no inherited conversation and declared packet exposure, not blank priors.

## limitations

- the fictional pair is designed to expose the distinction and cannot evidence
  occurrence in private cases.
- one cold analyst can reveal legibility, alternatives, and failure; it cannot
  establish reliability or generality.
- a clean protocol receipt proves ordering and preservation, not method
  validity or owner usefulness.
- synchronized repetition across the verdict, field, rails, path, detail, and
  prose can resemble convergent evidence even though every view derives from
  one authored payload.
- post-reveal self-report may rationalize what changed.
- the five displayed standing layers are provisional and non-exhaustive.
