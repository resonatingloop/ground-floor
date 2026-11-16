# ground-floor

`ground-floor` is the working repository for **the distinction survives**, a
small naturalistic study of interactional hysteresis in human–ai epistemics.
the study asks how a defeated qualification can survive as a narrower
successor-distinction, ratchet epistemic labor onto the user, and change what a
conversation is organized to accomplish.

the immediate deliverable is a research report for the [ai x epistemics
research sprint](https://apartresearch.com/sprints/ai-x-epistemics-research-sprint-2026-11-13-to-2026-11-15).
the report develops interactional hysteresis v1.1 through three private,
naturalistic episodes and a mechanism-matched intervention framework. it does
not claim access to model interiors or general causal effects from a small
observational corpus.

## current state

the repository has been pivoted from an unadopted warrant-crossing prototype.
the current research object has been grounded conceptually but has not been
promoted into an accepted method. one bounded fictional visualization study is
implemented and verified; its base spec and independence amendment are now
retired as fulfilled planning authority. the final cold run preserves both
analytical recovery and disagreement rather than treating the reference map as
ground truth. accepted spec 004 plans two isolated private case studies that may
run in parallel through case-local owner review; cross-case synthesis waits for
both closures. its public-safe protocol is implemented through `packet-draft`,
and two ignored packet candidates await exact owner review. neither packet is
approved or model-visible; analysis, public diffs, and paper prose remain behind
their later gates.
start with [the current checkpoint](STATUS.md),
then read [the informational settlement-mapping
checkpoint](docs/research/settlement-mapping-checkpoint.md).

## research boundary

- raw chats, screenshots, exports, and local corpora remain outside tracked
  repository state.
- public examples are paraphrased, synthetic, or explicitly cleared for
  quotation.
- propositions, evidence relations, rules, roles, and goals may acquire
  interactional standing; the current checkpoint treats their standing and
  consequences as the object, not as claims about hidden model beliefs.
- source availability, source uptake, and source-governed behavior remain
  distinct.
- the report preserves both contemporaneous benefit and retrospectively
  recognized interactional cost.
- provider calls and intervention evals require a separate explicit handoff.

see [the data boundary](data/README.md) and [the report
outline](report/outline.md).

## authority map

| artifact | authority |
| --- | --- |
| `README.md` | current front door and research boundary |
| `AGENTS.md` | agent authorization, collaboration routing, privacy boundary, validation, and close protocol |
| `STATUS.md` | current checkpoint and next transition |
| `docs/research/settlement-mapping-checkpoint.md` | advisory informational synthesis; current conceptual account, not an accepted method |
| `docs/roadmaps/001-interactional-hysteresis-sprint.md` | parked workshop draft; predates the current conceptual account and has no implementation authority |
| `docs/specs/001-observer-conditioned-settlement-mapping.md` | parked workshop draft; not current planning authority and not accepted |
| `docs/specs/002-settlement-mapping-visualization-study.md` | retired fulfilled base plan for the bounded visualization study |
| `docs/specs/003-settlement-mapping-independent-analysis-amendment.md` | retired fulfilled amendment requiring builder/analyst separation and a sealed cold-read protocol |
| `docs/specs/004-two-case-private-settlement-mapping-pilot.md` | accepted planning authority for two parallel, isolated, separately gated private cases; not implementation or publication authority |
| `studies/analysis/settlement-mapping-visualization/README.md` | implemented study, verification commands, cold-run protocol, and claim ceilings |
| `studies/analysis/private-case-pilot/README.md` | implemented public-safe packet-draft protocol, validation commands, gate boundary, and recovery path |
| `report/outline.md` | historical proposed report structure; predates the current checkpoint |
| `plans/initial-thoughts.md` | local historical brainstorming; not directive |
| `ground_floor/`, `tests/`, `docs/ledger-format.md` | historical unadopted prototype; executable but non-governing |

## historical prototype

the retained python package validates a fictional warrant-crossing event ledger.
it remains intact as evidence of an earlier sprint exploration, not as the
method or result of the current study. python 3.11 or newer is sufficient to
exercise it:

```bash
python3 -m unittest discover -s tests -v
python3 -m ground_floor validate data/fixtures/synthetic-pilot.jsonl
python3 -m ground_floor crossings data/fixtures/synthetic-pilot.jsonl
```

passing these checks proves only that the historical prototype still behaves as
documented. it does not validate the interactional-hysteresis method.

## provenance

preexisting work includes interactional hysteresis v1.0, its template and prior
applications, the private source conversations, the owner-facing guidance
cards, the hedge ward, and the historical prototype retained here. sprint-native
work begins with the v1.1 method revision, three-case comparison, intervention
selection framework, and report. the final report must preserve this boundary.
