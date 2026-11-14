# epistemic event ledger

the ledger is newline-delimited json: one observed interactional event per line.
it records what the corpus supports, not an annotator's reconstruction of a
participant's private mental state.

## fields

| field | meaning |
| --- | --- |
| `event_id` | stable, corpus-local opaque id |
| `episode_id` | bounded case or incident |
| `timestamp` | iso 8601 timestamp with an explicit utc offset |
| `participant_id` | stable public alias, not necessarily the visible account |
| `proposition_id` | stable id for the claim or rule being tracked |
| `action` | `mention`, `endorse`, `rely`, `operationalize`, `challenge`, `retract`, or `correct` |
| `warrant` | `direct_evidence`, `testimony`, `inference`, `authority`, or `unresolved` |
| `source_event_ids` | earlier ledger events this observed action depends on |
| `evidence_refs` | opaque pointers to supporting corpus artifacts |
| `information_horizon` | evidence references available to this participant at this moment |
| `note` | optional annotator note; keep private material out of public ledgers |

## annotation rule

use the weakest action supported by observable behavior. a repeated claim is a
`mention`; explicit agreement may be an `endorse`; an action whose rationale
depends on the claim is `rely`; changing persistent system behavior is
`operationalize`. disagreement and repair receive their own events rather than
silently rewriting earlier annotations.

`ground-floor crossings` returns the first acceptance-shaped event for each
proposition and its ultimate source events. this is a candidate warrant
crossing, not a truth label. the source roots make “three endorsements, one
evidential ancestor” inspectable without pretending that ancestry alone proves
dependence.

## privacy and adjudication

keep raw data in an ignored local path. use stable aliases in any derived public
ledger. every candidate crossing should receive human review against the
participant's historical information horizon. disagreements between annotators
belong in the research record; do not collapse them into artificial consensus.
the validator requires every cited evidence reference to appear in that event's
information horizon and rejects sources from the future.
