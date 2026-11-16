# private-case pilot protocol

this directory implements the public-safe portion of accepted spec 004. it can
prepare an ignored, fingerprinted `packet-draft` from read-only private sources
and validate that draft. it cannot approve a packet, expose it to an analyst,
run either analytical stage, or promote any result.

## authority boundary

the current implementation stops at `packet-draft`.

- the tracked code and fictional tests contain no private source wording,
  identity-bearing locator, or case-specific identifier;
- private recipes, source projections, custody records, and owner review slips
  live beneath ignored `artifacts/private-case-pilot/`;
- a draft records `intended_analyst: null`,
  `model_exposure_authorized: false`, no approval, and no exposure record;
- changing any staged byte, observer declaration, omission, custody record, or
  review slip invalidates the packet fingerprint; and
- a valid draft is not evidence of owner approval or analytical correctness.

case-a and case-b may be prepared independently. later analysis may run in
parallel only after the owner approves each exact packet and named analyst.
cross-case synthesis remains unavailable until both private owner reviews close.

## packet contents

each ignored packet draft contains:

```text
packet.json                 fingerprinted packet identity and gate state
custody.private.json        private source locators and source fingerprints
owner-review.txt            complete inclusion, omission, and exposure review
stage-a/*.txt               primary-source-only projection
stage-b/*.txt               reference material, sealed until stage a is frozen
```

`packet_draft.py` supports exact byte copies, normalized jsonl message ranges,
prompt/response projections with stable moment ids, and exact line ranges. all
source paths remain in `custody.private.json`; they never enter `packet.json`.

## commands

prepare a fresh draft from an ignored private recipe:

```bash
python3 studies/analysis/private-case-pilot/packet_draft.py \
  --recipe artifacts/private-case-pilot/recipes/case-a.private.json \
  --output artifacts/private-case-pilot/case-a/packet-draft-v1
```

validate one draft or the parallel pair:

```bash
python3 studies/analysis/private-case-pilot/validate.py \
  --case artifacts/private-case-pilot/case-a/packet-draft-v1

python3 studies/analysis/private-case-pilot/validate.py \
  --pair artifacts/private-case-pilot/case-a/packet-draft-v1 \
         artifacts/private-case-pilot/case-b/packet-draft-v2
```

run the public-safe fictional proof:

```bash
python3 -m unittest discover \
  -s studies/analysis/private-case-pilot/tests -v
```

the builder refuses non-empty destinations. after a recipe change, create a new
versioned draft; do not overwrite the earlier candidate.

## owner review

before any model exposure, the owner reviews each ignored `owner-review.txt`
and its `packet.json` fingerprint. approval must name the exact fingerprint and
the intended cold analyst. no review mark, valid checksum, general willingness,
or approval of the other case can substitute for that transition.

## recovery

resume from the ignored recipe and the latest named draft. re-run validation
before review. if source bytes changed, if any staged file changed, or if the
recipe is revised, prepare a new draft version and treat every earlier approval
as inapplicable.

the public-candidate scanner in `validate.py` is a later-boundary guardrail. it
detects seeded private paths, private ids, and long exact source overlap; it
cannot prove that a paraphrase is non-reconstructive or emotionally safe.

