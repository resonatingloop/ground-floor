from __future__ import annotations

import unittest

from ground_floor.ledger import Ledger, LedgerError


def event(event_id: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "event_id": event_id,
        "episode_id": "episode-1",
        "timestamp": "2026-11-14T09:00:00Z",
        "participant_id": "agent-a",
        "proposition_id": "proposition-1",
        "action": "mention",
        "warrant": "unresolved",
        "source_event_ids": [],
        "evidence_refs": [],
        "information_horizon": [],
        "note": "",
    }
    record.update(overrides)
    return record


class LedgerTests(unittest.TestCase):
    def test_finds_earliest_crossing_and_root_source(self) -> None:
        ledger = Ledger.from_records(
            [
                event("source"),
                event(
                    "operationalized",
                    timestamp="2026-11-14T09:03:00Z",
                    participant_id="agent-c",
                    action="operationalize",
                    warrant="testimony",
                    source_event_ids=["endorsed"],
                ),
                event(
                    "endorsed",
                    timestamp="2026-11-14T09:01:00Z",
                    participant_id="agent-b",
                    action="endorse",
                    warrant="testimony",
                    source_event_ids=["source"],
                ),
            ]
        )

        self.assertEqual(
            ledger.crossings(),
            [
                {
                    "proposition_id": "proposition-1",
                    "crossing_event_id": "endorsed",
                    "participant_id": "agent-b",
                    "action": "endorse",
                    "warrant": "testimony",
                    "root_source_event_ids": ["source"],
                }
            ],
        )

    def test_rejects_unknown_source(self) -> None:
        with self.assertRaisesRegex(LedgerError, "unknown event"):
            Ledger.from_records([event("event-1", source_event_ids=["missing"])])

    def test_rejects_source_cycle(self) -> None:
        with self.assertRaisesRegex(LedgerError, "cycle"):
            Ledger.from_records(
                [
                    event("event-1", source_event_ids=["event-2"]),
                    event("event-2", source_event_ids=["event-1"]),
                ]
            )

    def test_rejects_timestamp_without_offset(self) -> None:
        with self.assertRaisesRegex(LedgerError, "utc offset"):
            Ledger.from_records([event("event-1", timestamp="2026-11-14T09:00:00")])

    def test_requires_information_horizon(self) -> None:
        record = event("event-1")
        del record["information_horizon"]
        with self.assertRaisesRegex(LedgerError, "information_horizon"):
            Ledger.from_records([record])

    def test_rejects_evidence_outside_information_horizon(self) -> None:
        with self.assertRaisesRegex(LedgerError, "outside its information horizon"):
            Ledger.from_records(
                [event("event-1", evidence_refs=["artifact-1"])]
            )

    def test_rejects_future_source(self) -> None:
        with self.assertRaisesRegex(LedgerError, "future event"):
            Ledger.from_records(
                [
                    event("event-1", source_event_ids=["event-2"]),
                    event("event-2", timestamp="2026-11-14T09:01:00Z"),
                ]
            )


if __name__ == "__main__":
    unittest.main()
