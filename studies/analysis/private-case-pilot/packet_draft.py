#!/usr/bin/env python3
"""Build a private, ignored packet draft without authorizing exposure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CASE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PacketDraftError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PacketDraftError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PacketDraftError(f"{label} must be a non-empty string")
    return value


def _safe_output_name(value: Any, label: str) -> str:
    name = _require_string(value, label)
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or len(parsed.parts) != 1 or name in {".", ".."}:
        raise PacketDraftError(f"{label} must be one safe filename")
    if not name.endswith(".txt"):
        raise PacketDraftError(f"{label} must use the .txt raw-evidence suffix")
    return name


def _source(entry: dict[str, Any], label: str) -> tuple[Path, str]:
    source = Path(_require_string(entry.get("source_path"), f"{label}.source_path"))
    if not source.is_absolute():
        raise PacketDraftError(f"{label}.source_path must be absolute and private")
    if source.is_symlink() or not source.is_file():
        raise PacketDraftError(f"{label}.source_path must be a regular non-symlink file")
    expected = _require_string(entry.get("expected_sha256"), f"{label}.expected_sha256")
    if not SHA256_RE.fullmatch(expected):
        raise PacketDraftError(f"{label}.expected_sha256 must be lowercase sha-256")
    actual = sha256_file(source)
    if actual != expected:
        raise PacketDraftError(f"{label} source fingerprint changed: expected {expected}, got {actual}")
    return source, actual


def _copy_bytes(source: Path) -> bytes:
    return source.read_bytes()


def _jsonl_message_range(source: Path, entry: dict[str, Any], label: str) -> bytes:
    start = entry.get("start_order")
    end = entry.get("end_order")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise PacketDraftError(f"{label} needs a valid inclusive source-order range")
    speaker_map = _require_dict(entry.get("speaker_map"), f"{label}.speaker_map")
    prefix = _require_string(entry.get("moment_prefix"), f"{label}.moment_prefix")
    if not CASE_ID_RE.fullmatch(prefix):
        raise PacketDraftError(f"{label}.moment_prefix must be a safe lowercase id")

    selected: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise PacketDraftError(f"{label} invalid jsonl at line {line_number}: {exc}") from exc
        order = record.get("source_order")
        if isinstance(order, int) and start <= order <= end:
            selected.append(record)
    expected_orders = list(range(start, end + 1))
    orders = [record.get("source_order") for record in selected]
    if orders != expected_orders:
        raise PacketDraftError(f"{label} range is not complete and ordered")

    rendered = [
        "private source projection",
        f"stable range: {prefix}-{start:04d} through {prefix}-{end:04d}",
        "attribution is neutralized according to the private custody record.",
        "",
    ]
    for record in selected:
        author = _require_dict(record.get("author"), f"{label}.author")
        display_label = _require_string(author.get("display_label"), f"{label}.author.display_label")
        if display_label not in speaker_map:
            raise PacketDraftError(f"{label} has unmapped speaker {display_label!r}")
        neutral = _require_string(speaker_map[display_label], f"{label}.speaker_map[{display_label!r}]")
        content = record.get("content")
        if not isinstance(content, str):
            raise PacketDraftError(f"{label} source order {record['source_order']} has non-text content")
        rendered.extend(
            [
                f"[ {prefix}-{record['source_order']:04d} | {neutral} ]",
                content,
                "",
            ]
        )
    return "\n".join(rendered).encode("utf-8")


def _prompt_response_sections(source: Path, entry: dict[str, Any], label: str) -> bytes:
    prefix = _require_string(entry.get("moment_prefix"), f"{label}.moment_prefix")
    if not CASE_ID_RE.fullmatch(prefix):
        raise PacketDraftError(f"{label}.moment_prefix must be a safe lowercase id")
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    sections: list[tuple[str, list[str]]] = []
    current_label: str | None = None
    current_lines: list[str] = []
    exchange = 0
    for line in lines:
        stripped = line.strip().lower()
        role: str | None = None
        if stripped == "## prompt:":
            exchange += 1
            role = "owner"
        elif stripped == "## response:":
            if exchange == 0:
                raise PacketDraftError(f"{label} response precedes first prompt")
            role = "assistant"
        if role is not None:
            if current_label is not None:
                sections.append((current_label, current_lines))
            current_label = f"{prefix}-{exchange:04d}-{role}"
            current_lines = []
        elif current_label is not None:
            current_lines.append(line)
        elif line.strip():
            raise PacketDraftError(f"{label} has content before its first prompt heading")
    if current_label is not None:
        sections.append((current_label, current_lines))
    if not sections:
        raise PacketDraftError(f"{label} contains no prompt/response sections")

    rendered = [
        "private source projection\n",
        "prompt/response headings are replaced with stable neutral moment ids.\n",
        "all section body text remains in source order.\n",
        "\n",
    ]
    for moment_id, body in sections:
        rendered.append(f"[ {moment_id} ]\n")
        rendered.extend(body)
        if not body or not body[-1].endswith("\n"):
            rendered.append("\n")
    return "".join(rendered).encode("utf-8")


def _line_range(source: Path, entry: dict[str, Any], label: str) -> bytes:
    start = entry.get("start_line")
    end = entry.get("end_line")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise PacketDraftError(f"{label} needs a valid inclusive line range")
    lines = source.read_bytes().splitlines(keepends=True)
    if end > len(lines):
        raise PacketDraftError(f"{label} line range exceeds source length {len(lines)}")
    return b"".join(lines[start - 1 : end])


TRANSFORMS = {
    "copy": _copy_bytes,
    "jsonl-message-range": _jsonl_message_range,
    "prompt-response-sections": _prompt_response_sections,
    "line-range": _line_range,
}


def _render_source(source: Path, entry: dict[str, Any], label: str) -> bytes:
    mode = _require_string(entry.get("mode"), f"{label}.mode")
    transform = TRANSFORMS.get(mode)
    if transform is None:
        raise PacketDraftError(f"{label}.mode is unsupported: {mode}")
    if mode == "copy":
        return transform(source)  # type: ignore[misc]
    return transform(source, entry, label)  # type: ignore[misc]


def build_packet(recipe_path: Path, output: Path) -> dict[str, Any]:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise PacketDraftError("output must be absent or an empty real directory")
    if output.is_symlink():
        raise PacketDraftError("output may not be a symlink")

    recipe_bytes = recipe_path.read_bytes()
    recipe = _require_dict(json.loads(recipe_bytes), "recipe")
    case_id = _require_string(recipe.get("case_id"), "case_id")
    if not CASE_ID_RE.fullmatch(case_id):
        raise PacketDraftError("case_id must be a safe lowercase id")
    if recipe.get("intended_analyst") is not None:
        raise PacketDraftError("packet-draft intended_analyst must be null")
    observer = _require_dict(recipe.get("observer"), "observer")
    for field in ("slice", "projection", "attribution_policy", "occlusion", "selection_risk"):
        _require_string(observer.get(field), f"observer.{field}")
    omissions = recipe.get("omissions")
    if not isinstance(omissions, list) or not omissions or not all(isinstance(item, str) and item.strip() for item in omissions):
        raise PacketDraftError("omissions must be a non-empty string list")

    prepared_at = _require_string(recipe.get("prepared_at"), "prepared_at")
    output.mkdir(parents=True, exist_ok=True)
    custody_entries: list[dict[str, Any]] = []
    stage_records: dict[str, dict[str, Any]] = {}

    for stage_key, directory_name in (("stage_a", "stage-a"), ("stage_b", "stage-b")):
        entries = recipe.get(stage_key)
        if not isinstance(entries, list) or not entries:
            raise PacketDraftError(f"{stage_key} must contain at least one source")
        stage_directory = output / directory_name
        stage_directory.mkdir()
        files: list[dict[str, Any]] = []
        for index, raw_entry in enumerate(entries, 1):
            entry = _require_dict(raw_entry, f"{stage_key}[{index}]")
            source, source_hash = _source(entry, f"{stage_key}[{index}]")
            output_name = _safe_output_name(entry.get("output_name"), f"{stage_key}[{index}].output_name")
            target = stage_directory / output_name
            if target.exists():
                raise PacketDraftError(f"duplicate output name in {stage_key}: {output_name}")
            payload = _render_source(source, entry, f"{stage_key}[{index}]")
            target.write_bytes(payload)
            relative = target.relative_to(output).as_posix()
            record = {
                "path": relative,
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
                "role": _require_string(entry.get("role"), f"{stage_key}[{index}].role"),
                "evidence_class": _require_string(
                    entry.get("evidence_class"),
                    f"{stage_key}[{index}].evidence_class",
                ),
                "mode": entry["mode"],
            }
            files.append(record)
            custody_entries.append(
                {
                    "stage": stage_key,
                    "output": relative,
                    "source_path": str(source),
                    "resolved_source_path": str(source.resolve()),
                    "source_sha256": source_hash,
                    "source_bytes": source.stat().st_size,
                    "selection": {key: value for key, value in entry.items() if key not in {"source_path", "expected_sha256", "speaker_map"}},
                    "private_speaker_map": entry.get("speaker_map"),
                }
            )
        stage_records[stage_key] = {
            "access": "primary-source-only" if stage_key == "stage_a" else "sealed-until-stage-a-return-is-fingerprinted",
            "files": files,
        }

    custody = {
        "schema_version": "0.1.0",
        "case_id": case_id,
        "prepared_at": prepared_at,
        "recipe_sha256": sha256_bytes(recipe_bytes),
        "sources": custody_entries,
    }
    custody_path = output / "custody.private.json"
    custody_path.write_text(json.dumps(custody, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review_lines = [
        f"private packet review: {case_id}",
        "state: packet-draft",
        "intended analyst: unassigned",
        "model exposure authorized: no",
        "",
        "observer conditions",
    ]
    review_lines.extend(f"- {key.replace('_', ' ')}: {observer[key]}" for key in ("slice", "projection", "attribution_policy", "occlusion", "selection_risk"))
    for stage_key, title in (("stage_a", "stage a allowlist"), ("stage_b", "stage b allowlist")):
        review_lines.extend(["", title])
        for record, custody_record in zip(stage_records[stage_key]["files"], [item for item in custody_entries if item["stage"] == stage_key], strict=True):
            review_lines.append(f"- {record['path']} | {record['sha256']} | {record['bytes']} bytes | {record['role']} | source {custody_record['source_path']}")
    review_lines.extend(["", "declared omissions"])
    review_lines.extend(f"- {item}" for item in omissions)
    review_lines.extend(
        [
            "",
            "approval boundary",
            "- this review is a draft, not approval.",
            "- approval must name the packet fingerprint and intended cold analyst.",
            "- any changed byte or declaration requires a new packet draft.",
            "",
        ]
    )
    review_path = output / "owner-review.txt"
    review_path.write_text("\n".join(review_lines), encoding="utf-8")

    manifest: dict[str, Any] = {
        "schema_version": "0.1.0",
        "case_id": case_id,
        "state": "packet-draft",
        "prepared_at": prepared_at,
        "privacy": "private-ignored",
        "observer": observer,
        "stages": stage_records,
        "omissions": omissions,
        "custody_record": {
            "path": "custody.private.json",
            "sha256": sha256_file(custody_path),
        },
        "owner_review_record": {
            "path": "owner-review.txt",
            "sha256": sha256_file(review_path),
        },
        "owner_gate": {
            "packet_approval": None,
            "intended_analyst": None,
            "model_exposure_authorized": False,
        },
        "exposure_records": [],
    }
    manifest["packet_fingerprint"] = sha256_bytes(canonical_bytes(manifest))
    manifest_path = output / "packet.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = build_packet(args.recipe, args.output)
    except (OSError, json.JSONDecodeError, PacketDraftError) as exc:
        parser.error(str(exc))
    print(f"prepared {manifest['case_id']} packet-draft: {args.output}")
    print(f"packet fingerprint: {manifest['packet_fingerprint']}")
    print("model exposure authorized: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

