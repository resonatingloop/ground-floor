from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable


ACTIONS = frozenset(
    {
        "mention",
        "endorse",
        "rely",
        "operationalize",
        "challenge",
        "retract",
        "correct",
    }
)
WARRANTS = frozenset(
    {"direct_evidence", "testimony", "inference", "authority", "unresolved"}
)
CROSSING_ACTIONS = frozenset({"endorse", "rely", "operationalize"})


class LedgerError(ValueError):
    """raised when an event ledger violates the annotation contract."""


def _string(record: dict[str, Any], field: str, line: int) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"line {line}: {field} must be a non-empty string")
    return value


def _string_list(record: dict[str, Any], field: str, line: int) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise LedgerError(f"line {line}: {field} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise LedgerError(f"line {line}: {field} must not contain duplicates")
    return tuple(value)


def _timestamp(value: str, line: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise LedgerError(f"line {line}: timestamp is not iso 8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LedgerError(f"line {line}: timestamp must include a utc offset")
    return parsed


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    episode_id: str
    timestamp: datetime
    participant_id: str
    proposition_id: str
    action: str
    warrant: str
    source_event_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    information_horizon: tuple[str, ...]
    note: str

    @classmethod
    def from_record(cls, record: Any, line: int) -> "Event":
        if not isinstance(record, dict):
            raise LedgerError(f"line {line}: each record must be a json object")

        action = _string(record, "action", line)
        if action not in ACTIONS:
            raise LedgerError(f"line {line}: unknown action {action!r}")

        warrant = _string(record, "warrant", line)
        if warrant not in WARRANTS:
            raise LedgerError(f"line {line}: unknown warrant {warrant!r}")

        timestamp_text = _string(record, "timestamp", line)
        note = record.get("note", "")
        if not isinstance(note, str):
            raise LedgerError(f"line {line}: note must be a string")

        return cls(
            event_id=_string(record, "event_id", line),
            episode_id=_string(record, "episode_id", line),
            timestamp=_timestamp(timestamp_text, line),
            participant_id=_string(record, "participant_id", line),
            proposition_id=_string(record, "proposition_id", line),
            action=action,
            warrant=warrant,
            source_event_ids=_string_list(record, "source_event_ids", line),
            evidence_refs=_string_list(record, "evidence_refs", line),
            information_horizon=_string_list(record, "information_horizon", line),
            note=note,
        )


@dataclass(frozen=True, slots=True)
class Ledger:
    events: tuple[Event, ...]

    @classmethod
    def from_records(cls, records: Iterable[Any]) -> "Ledger":
        events = tuple(
            Event.from_record(record, line)
            for line, record in enumerate(records, start=1)
        )
        ledger = cls(events)
        ledger._validate_relations()
        return ledger

    @classmethod
    def from_jsonl(cls, path: Path) -> "Ledger":
        records: list[Any] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise LedgerError(f"line {line_number}: invalid json: {error.msg}") from error
        return cls.from_records(records)

    def _validate_relations(self) -> None:
        by_id: dict[str, Event] = {}
        for event in self.events:
            if event.event_id in by_id:
                raise LedgerError(f"duplicate event_id {event.event_id!r}")
            by_id[event.event_id] = event

        for event in self.events:
            unavailable_evidence = set(event.evidence_refs) - set(
                event.information_horizon
            )
            if unavailable_evidence:
                raise LedgerError(
                    f"event {event.event_id!r} cites evidence outside its "
                    f"information horizon: {sorted(unavailable_evidence)!r}"
                )
            for source_id in event.source_event_ids:
                if source_id == event.event_id:
                    raise LedgerError(f"event {event.event_id!r} cites itself")
                if source_id not in by_id:
                    raise LedgerError(
                        f"event {event.event_id!r} cites unknown event {source_id!r}"
                    )
                if by_id[source_id].timestamp > event.timestamp:
                    raise LedgerError(
                        f"event {event.event_id!r} cites future event {source_id!r}"
                    )

        self._assert_acyclic(by_id)

    def _assert_acyclic(self, by_id: dict[str, Event]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(event_id: str) -> None:
            if event_id in visiting:
                raise LedgerError(f"source-event cycle reaches {event_id!r}")
            if event_id in visited:
                return
            visiting.add(event_id)
            for source_id in by_id[event_id].source_event_ids:
                visit(source_id)
            visiting.remove(event_id)
            visited.add(event_id)

        for event_id in by_id:
            visit(event_id)

    def crossings(self) -> list[dict[str, Any]]:
        """return the earliest acceptance-shaped event for each proposition."""
        by_id = {event.event_id: event for event in self.events}
        candidates: dict[str, Event] = {}
        for event in self.events:
            if event.action not in CROSSING_ACTIONS:
                continue
            previous = candidates.get(event.proposition_id)
            if previous is None or (event.timestamp, event.event_id) < (
                previous.timestamp,
                previous.event_id,
            ):
                candidates[event.proposition_id] = event

        return [
            {
                "proposition_id": proposition_id,
                "crossing_event_id": event.event_id,
                "participant_id": event.participant_id,
                "action": event.action,
                "warrant": event.warrant,
                "root_source_event_ids": sorted(self._root_sources(event, by_id)),
            }
            for proposition_id, event in sorted(candidates.items())
        ]

    def _root_sources(self, event: Event, by_id: dict[str, Event]) -> set[str]:
        if not event.source_event_ids:
            return {event.event_id}
        roots: set[str] = set()
        for source_id in event.source_event_ids:
            roots.update(self._root_sources(by_id[source_id], by_id))
        return roots
