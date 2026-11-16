#!/usr/bin/env python3
"""Validate private packet drafts and conservative public projections."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from packet_draft import CASE_ID_RE, SHA256_RE, canonical_bytes, sha256_bytes, sha256_file


class ValidationError(ValueError):
    pass


PRIVATE_PATTERNS = {
    "unix home path": re.compile(r"/home/[^/\s]+/"),
    "windows user path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
    "private message id": re.compile(r"\bmsg_[0-9a-f]{16,}\b"),
    "private participant id": re.compile(r"\bpt_[0-9a-f]{16,}\b"),
    "private annotation id": re.compile(r"\b(?:ann|adj)_[0-9a-f]{16,}\b"),
    "source author field": re.compile(r"\bsource_author_id\b"),
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read json {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must contain an object")
    return value


def _safe_packet_path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError(f"{label} escapes the packet root")
    candidate = root / path
    if candidate.is_symlink() or not candidate.is_file():
        raise ValidationError(f"{label} is missing or not a regular file: {value}")
    if root.resolve() not in candidate.resolve().parents:
        raise ValidationError(f"{label} resolves outside the packet root")
    return candidate


def validate_packet(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("packet root must be a real directory")
    manifest = _read_json(root / "packet.json")
    case_id = manifest.get("case_id")
    if not isinstance(case_id, str) or not CASE_ID_RE.fullmatch(case_id):
        raise ValidationError("manifest case_id is invalid")
    if manifest.get("state") != "packet-draft":
        raise ValidationError("this implementation validates packet-draft only")
    if manifest.get("privacy") != "private-ignored":
        raise ValidationError("packet privacy must remain private-ignored")

    fingerprint = manifest.get("packet_fingerprint")
    if not isinstance(fingerprint, str) or not SHA256_RE.fullmatch(fingerprint):
        raise ValidationError("packet_fingerprint is invalid")
    payload = dict(manifest)
    del payload["packet_fingerprint"]
    expected_fingerprint = sha256_bytes(canonical_bytes(payload))
    if fingerprint != expected_fingerprint:
        raise ValidationError("packet fingerprint does not match manifest content")

    gate = manifest.get("owner_gate")
    if gate != {
        "packet_approval": None,
        "intended_analyst": None,
        "model_exposure_authorized": False,
    }:
        raise ValidationError("packet-draft owner gate must remain unapproved and unassigned")
    if manifest.get("exposure_records") != []:
        raise ValidationError("packet-draft may not contain exposure records")

    declared_stage_files: set[str] = set()
    stages = manifest.get("stages")
    if not isinstance(stages, dict) or set(stages) != {"stage_a", "stage_b"}:
        raise ValidationError("manifest must declare stage_a and stage_b")
    for stage_key, directory_name in (("stage_a", "stage-a"), ("stage_b", "stage-b")):
        stage = stages.get(stage_key)
        if not isinstance(stage, dict) or not isinstance(stage.get("files"), list) or not stage["files"]:
            raise ValidationError(f"{stage_key} must contain files")
        for index, record in enumerate(stage["files"], 1):
            if not isinstance(record, dict):
                raise ValidationError(f"{stage_key}[{index}] must be an object")
            value = record.get("path")
            if not isinstance(value, str) or not value.startswith(f"{directory_name}/"):
                raise ValidationError(f"{stage_key}[{index}] path is outside its stage")
            if value in declared_stage_files:
                raise ValidationError(f"duplicate staged path: {value}")
            declared_stage_files.add(value)
            path = _safe_packet_path(root, value, f"{stage_key}[{index}].path")
            if record.get("sha256") != sha256_file(path):
                raise ValidationError(f"staged file fingerprint changed: {value}")
            if record.get("bytes") != path.stat().st_size:
                raise ValidationError(f"staged file size changed: {value}")

    actual_stage_files = {
        path.relative_to(root).as_posix()
        for directory in (root / "stage-a", root / "stage-b")
        for path in directory.iterdir()
        if path.is_file()
    }
    if actual_stage_files != declared_stage_files:
        raise ValidationError("stage directories contain undeclared or missing files")

    for field in ("custody_record", "owner_review_record"):
        record = manifest.get(field)
        if not isinstance(record, dict):
            raise ValidationError(f"{field} is missing")
        path = _safe_packet_path(root, record.get("path"), f"{field}.path")
        if record.get("sha256") != sha256_file(path):
            raise ValidationError(f"{field} fingerprint changed")
    return manifest


def validate_pair(first: Path, second: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if first.resolve() == second.resolve() or first.resolve() in second.resolve().parents or second.resolve() in first.resolve().parents:
        raise ValidationError("parallel packet roots must be separate")
    left = validate_packet(first)
    right = validate_packet(second)
    if left["case_id"] == right["case_id"]:
        raise ValidationError("parallel packets must have distinct case ids")
    return left, right


def _iter_text_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path


def scan_public_candidate(root: Path, sources: Iterable[Path] = ()) -> list[str]:
    findings: list[str] = []
    candidate_chunks: list[str] = []
    for path in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"binary or non-utf8 file: {path}")
            continue
        candidate_chunks.append(text)
        for label, pattern in PRIVATE_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}: {path}")
    candidate_text = "\n".join(candidate_chunks)
    for source in sources:
        source_text = source.read_text(encoding="utf-8", errors="ignore")
        for line in source_text.splitlines():
            normalized = " ".join(line.split())
            if len(normalized) >= 120 and normalized in " ".join(candidate_text.split()):
                findings.append(f"long exact source overlap with {source}")
                break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", type=Path)
    group.add_argument("--pair", nargs=2, type=Path, metavar=("CASE_A", "CASE_B"))
    group.add_argument("--public-candidate", type=Path)
    parser.add_argument("--source", action="append", default=[], type=Path)
    args = parser.parse_args()
    try:
        if args.case:
            manifest = validate_packet(args.case)
            print(f"valid packet-draft: {manifest['case_id']} {manifest['packet_fingerprint']}")
        elif args.pair:
            left, right = validate_pair(*args.pair)
            print(f"valid isolated packet pair: {left['case_id']} + {right['case_id']}")
        else:
            findings = scan_public_candidate(args.public_candidate, args.source)
            if findings:
                raise ValidationError("public boundary failed:\n- " + "\n- ".join(findings))
            print("public boundary scan passed; manual non-reconstructability review remains required")
    except (OSError, ValidationError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

