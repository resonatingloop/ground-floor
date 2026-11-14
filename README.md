# ground-floor

`ground-floor` is a small research instrument for tracing **warrant crossings**:
moments when a proposition moves from being mentioned or reported to being
endorsed, relied upon, or operationalized by another participant in a
multi-agent system.

the immediate project is a pilot study for the [ai x epistemics research
sprint](https://apartresearch.com/sprints/ai-x-epistemics-research-sprint-2026-11-13-to-2026-11-15).
it reconstructs what was observable to whom at a historical moment without
pretending to recover anyone's private beliefs.

## quickest path

python 3.11 or newer is the only requirement.

```bash
python3 -m unittest discover -s tests -v
python3 -m ground_floor validate data/fixtures/synthetic-pilot.jsonl
python3 -m ground_floor crossings data/fixtures/synthetic-pilot.jsonl
```

the fixture is fictional. it demonstrates the method without publishing the
discord logs, memory snapshots, or other private source material.

## research boundary

- raw discord logs, agent logs, memory snapshots, and local corpora belong in
  `data/private/` or `data/raw/`; both paths are ignored by git.
- the ledger stores opaque evidence references, not private message contents.
- public examples must be synthetic or explicitly cleared, and participant ids
  should be replaced with stable aliases.
- mention, endorsement, reliance, and operationalization are separate actions.
  repetition alone is not treated as acceptance.
- `crossings` identifies candidates for human review; it does not decide that a
  claim was true, justified, or believed.

see [the ledger format](docs/ledger-format.md) for the annotation contract and
[the report scaffold](report/outline.md) for the sprint write-up.

## sprint provenance

this repository's initial readme and license predate the sprint implementation.
the event-ledger code, synthetic fixture, tests, and research/report scaffolds
were created during the november 13–15, 2026 sprint. the parallax instrument,
solar flares materials, swarm records, and source corpora are preexisting inputs;
they are not included here. every report draft should preserve that distinction.
