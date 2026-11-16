#!/usr/bin/env python3
"""Build a private, ignored packet draft without authorizing exposure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


def _safe_artifact_name(value: Any, label: str) -> str:
    name = _require_string(value, label)
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or len(parsed.parts) != 1 or name in {".", ".."}:
        raise PacketDraftError(f"{label} must be one safe filename")
    return name


def _safe_output_name(value: Any, label: str) -> str:
    name = _safe_artifact_name(value, label)
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


def _chatgpt_conversation_tree(
    source: Path,
    entry: dict[str, Any],
    label: str,
) -> tuple[bytes, list[dict[str, Any]]]:
    conversation_id = _require_string(entry.get("conversation_id"), f"{label}.conversation_id")
    expected_template = _require_string(
        entry.get("expected_conversation_template_id"),
        f"{label}.expected_conversation_template_id",
    )
    prefix = _require_string(entry.get("moment_prefix"), f"{label}.moment_prefix")
    if not CASE_ID_RE.fullmatch(prefix):
        raise PacketDraftError(f"{label}.moment_prefix must be a safe lowercase id")
    asset_root = Path(_require_string(entry.get("asset_root"), f"{label}.asset_root"))
    if not asset_root.is_absolute() or asset_root.is_symlink() or not asset_root.is_dir():
        raise PacketDraftError(f"{label}.asset_root must be an absolute real directory")

    exported = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(exported, list):
        raise PacketDraftError(f"{label} export shard must contain a conversation list")
    matches = [
        item
        for item in exported
        if isinstance(item, dict)
        and (item.get("id") == conversation_id or item.get("conversation_id") == conversation_id)
    ]
    if len(matches) != 1:
        raise PacketDraftError(f"{label} expected one exact conversation match, found {len(matches)}")
    conversation = matches[0]
    if conversation.get("id") != conversation_id or conversation.get("conversation_id") != conversation_id:
        raise PacketDraftError(f"{label} conversation id fields disagree")
    if conversation.get("conversation_template_id") != expected_template:
        raise PacketDraftError(f"{label} conversation template id changed")
    mapping = _require_dict(conversation.get("mapping"), f"{label}.mapping")
    current_node = _require_string(conversation.get("current_node"), f"{label}.current_node")
    if current_node not in mapping:
        raise PacketDraftError(f"{label}.current_node is absent from mapping")

    source_index = {node_id: index for index, node_id in enumerate(mapping)}
    children: dict[str | None, list[str]] = defaultdict(list)
    for node_id, raw_node in mapping.items():
        node = _require_dict(raw_node, f"{label}.mapping[{node_id!r}]")
        parent = node.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise PacketDraftError(f"{label} node parent must be a string or null")
        if parent is not None and parent not in mapping:
            raise PacketDraftError(f"{label} node parent is absent from mapping")
        children[parent].append(node_id)

    def node_sort_key(node_id: str) -> tuple[float, int]:
        message = mapping[node_id].get("message")
        created = message.get("create_time") if isinstance(message, dict) else None
        return (float(created) if isinstance(created, (int, float)) else float("inf"), source_index[node_id])

    for siblings in children.values():
        siblings.sort(key=node_sort_key)
    roots = children[None]
    if not roots:
        raise PacketDraftError(f"{label} conversation tree has no root")

    ordered_nodes: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise PacketDraftError(f"{label} conversation tree contains a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        ordered_nodes.append(node_id)
        for child in children.get(node_id, []):
            visit(child)
        visiting.remove(node_id)
        visited.add(node_id)

    for root in sorted(roots, key=node_sort_key):
        visit(root)
    if len(visited) != len(mapping):
        raise PacketDraftError(f"{label} conversation tree contains unreachable nodes")

    active_path: set[str] = set()
    cursor: str | None = current_node
    while cursor is not None:
        if cursor in active_path:
            raise PacketDraftError(f"{label} active path contains a cycle")
        active_path.add(cursor)
        cursor = mapping[cursor].get("parent")

    excluded_types = {"reasoning_recap", "thoughts"}
    visible_nodes: list[str] = []
    excluded_counts: Counter[str] = Counter()
    for node_id in ordered_nodes:
        message = mapping[node_id].get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("author", {}).get("role") if isinstance(message.get("author"), dict) else None
        content = message.get("content")
        content_type = content.get("content_type") if isinstance(content, dict) else None
        if content_type in excluded_types:
            excluded_counts[str(content_type)] += 1
            continue
        if role not in {"user", "assistant"}:
            excluded_counts[f"role:{role}"] += 1
            continue
        if content_type not in {"text", "multimodal_text"}:
            raise PacketDraftError(f"{label} has unsupported participant-visible content type {content_type!r}")
        visible_nodes.append(node_id)
    if not visible_nodes:
        raise PacketDraftError(f"{label} contains no participant-visible messages")

    moment_ids = {node_id: f"{prefix}-{index:04d}" for index, node_id in enumerate(visible_nodes, 1)}

    def visible_parent(node_id: str) -> str | None:
        parent = mapping[node_id].get("parent")
        while parent is not None and parent not in moment_ids:
            parent = mapping[parent].get("parent")
        return parent

    attachment_metadata: dict[str, dict[str, Any]] = {}
    attachment_associations: dict[str, set[str]] = defaultdict(set)
    attachment_order: list[str] = []

    def register_attachment(raw: Any, moment_id: str) -> str:
        if not isinstance(raw, str) or not re.fullmatch(r"file_[0-9a-f]+", raw):
            raise PacketDraftError(f"{label} has an invalid attachment id")
        if raw not in attachment_associations:
            attachment_order.append(raw)
        attachment_associations[raw].add(moment_id)
        return raw

    for node_id in visible_nodes:
        message = mapping[node_id]["message"]
        moment_id = moment_ids[node_id]
        metadata = message.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise PacketDraftError(f"{label} message metadata must be an object")
        for raw_attachment in (metadata or {}).get("attachments") or []:
            attachment = _require_dict(raw_attachment, f"{label} attachment")
            attachment_id = register_attachment(attachment.get("id"), moment_id)
            previous = attachment_metadata.get(attachment_id)
            if previous is not None and previous != attachment:
                raise PacketDraftError(f"{label} attachment metadata disagrees for one id")
            attachment_metadata[attachment_id] = attachment
        content = _require_dict(message.get("content"), f"{label} visible content")
        parts = content.get("parts")
        if not isinstance(parts, list):
            raise PacketDraftError(f"{label} visible content parts must be a list")
        for part in parts:
            if isinstance(part, dict) and part.get("content_type") == "image_asset_pointer":
                pointer = _require_string(part.get("asset_pointer"), f"{label} image asset pointer")
                if not pointer.startswith("sediment://"):
                    raise PacketDraftError(f"{label} has an unsupported image asset pointer")
                register_attachment(pointer.removeprefix("sediment://"), moment_id)
            elif not isinstance(part, str):
                raise PacketDraftError(f"{label} has an unsupported participant-visible content part")

    missing_metadata = [item for item in attachment_order if item not in attachment_metadata]
    if missing_metadata:
        raise PacketDraftError(f"{label} attachment metadata is missing for {len(missing_metadata)} file(s)")

    extension_by_mime = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "text/markdown": ".md.export.txt",
    }
    attachment_labels: dict[str, str] = {}
    extras: list[dict[str, Any]] = []
    for index, attachment_id in enumerate(attachment_order, 1):
        metadata = attachment_metadata[attachment_id]
        mime_type = _require_string(metadata.get("mime_type"), f"{label} attachment mime_type")
        extension = extension_by_mime.get(mime_type)
        if extension is None:
            raise PacketDraftError(f"{label} has unsupported attachment mime type {mime_type!r}")
        output_name = f"attachment-{index:03d}{extension}"
        attachment_labels[attachment_id] = output_name
        attachment_source = asset_root / f"{attachment_id}.dat"
        if attachment_source.is_symlink() or not attachment_source.is_file():
            raise PacketDraftError(f"{label} attachment source is missing or not a regular file")
        declared_size = metadata.get("size")
        if not isinstance(declared_size, int) or declared_size != attachment_source.stat().st_size:
            raise PacketDraftError(f"{label} attachment size disagrees with export metadata")
        extras.append(
            {
                "output_name": output_name,
                "payload": attachment_source.read_bytes(),
                "source": attachment_source,
                "role": f"participant-visible attachment associated with {', '.join(sorted(attachment_associations[attachment_id]))}",
                "evidence_class": "participant-visible primary-source attachment",
                "mode": "chatgpt-asset-copy",
                "selection": {
                    "associations": sorted(attachment_associations[attachment_id]),
                    "original_name": metadata.get("name"),
                    "mime_type": mime_type,
                },
            }
        )

    rendered = [
        "private source projection",
        "scope: complete participant-visible conversation tree",
        "topology: active path and alternate branches are retained; parent links skip non-visible export apparatus",
        f"stable moments: {prefix}-0001 through {prefix}-{len(visible_nodes):04d}",
        f"participant-visible attachments: {len(extras)}",
        "excluded export apparatus: " + ", ".join(f"{key}={value}" for key, value in sorted(excluded_counts.items())),
        "",
    ]
    for node_id in visible_nodes:
        message = mapping[node_id]["message"]
        content = message["content"]
        moment_id = moment_ids[node_id]
        parent = visible_parent(node_id)
        parent_label = moment_ids[parent] if parent is not None else "root"
        role = "owner" if message["author"]["role"] == "user" else "assistant"
        path_label = "active" if node_id in active_path else "alternate"
        created = message.get("create_time")
        timestamp = (
            datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat().replace("+00:00", "Z")
            if isinstance(created, (int, float))
            else "unknown"
        )
        rendered.append(f"[ {moment_id} | {role} | parent {parent_label} | path {path_label} | {timestamp} ]")
        for part in content["parts"]:
            if isinstance(part, str):
                rendered.append(part)
            else:
                attachment_id = part["asset_pointer"].removeprefix("sediment://")
                rendered.append(f"[attached image: {attachment_labels[attachment_id]}]")
        metadata_ids = [
            item["id"]
            for item in (message.get("metadata") or {}).get("attachments") or []
            if isinstance(item, dict) and item.get("id") in attachment_labels
        ]
        content_ids = {
            part["asset_pointer"].removeprefix("sediment://")
            for part in content["parts"]
            if isinstance(part, dict) and part.get("content_type") == "image_asset_pointer"
        }
        for attachment_id in metadata_ids:
            if attachment_id not in content_ids:
                rendered.append(f"[attached file: {attachment_labels[attachment_id]}]")
        rendered.append("")
    return "\n".join(rendered).encode("utf-8"), extras


TRANSFORMS = {
    "copy": _copy_bytes,
    "jsonl-message-range": _jsonl_message_range,
    "prompt-response-sections": _prompt_response_sections,
    "line-range": _line_range,
}


def _render_source(source: Path, entry: dict[str, Any], label: str) -> tuple[bytes, list[dict[str, Any]]]:
    mode = _require_string(entry.get("mode"), f"{label}.mode")
    if mode == "chatgpt-conversation-tree":
        return _chatgpt_conversation_tree(source, entry, label)
    transform = TRANSFORMS.get(mode)
    if transform is None:
        raise PacketDraftError(f"{label}.mode is unsupported: {mode}")
    if mode == "copy":
        return transform(source), []  # type: ignore[misc]
    return transform(source, entry, label), []  # type: ignore[misc]


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
            payload, extra_artifacts = _render_source(source, entry, f"{stage_key}[{index}]")
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
            for extra in extra_artifacts:
                extra_name = _safe_artifact_name(extra["output_name"], f"{stage_key}[{index}].extra.output_name")
                if Path(extra_name).suffix not in {".png", ".jpg", ".txt"}:
                    raise PacketDraftError(f"{stage_key}[{index}] produced an unsupported attachment suffix")
                extra_target = stage_directory / extra_name
                if extra_target.exists():
                    raise PacketDraftError(f"duplicate output name in {stage_key}: {extra_name}")
                extra_payload = extra["payload"]
                if not isinstance(extra_payload, bytes):
                    raise PacketDraftError(f"{stage_key}[{index}] produced invalid attachment bytes")
                extra_target.write_bytes(extra_payload)
                extra_relative = extra_target.relative_to(output).as_posix()
                files.append(
                    {
                        "path": extra_relative,
                        "sha256": sha256_bytes(extra_payload),
                        "bytes": len(extra_payload),
                        "role": _require_string(extra.get("role"), f"{stage_key}[{index}].extra.role"),
                        "evidence_class": _require_string(
                            extra.get("evidence_class"),
                            f"{stage_key}[{index}].extra.evidence_class",
                        ),
                        "mode": _require_string(extra.get("mode"), f"{stage_key}[{index}].extra.mode"),
                    }
                )
                extra_source = extra.get("source")
                if not isinstance(extra_source, Path) or extra_source.is_symlink() or not extra_source.is_file():
                    raise PacketDraftError(f"{stage_key}[{index}] produced an invalid attachment source")
                custody_entries.append(
                    {
                        "stage": stage_key,
                        "output": extra_relative,
                        "source_path": str(extra_source),
                        "resolved_source_path": str(extra_source.resolve()),
                        "source_sha256": sha256_file(extra_source),
                        "source_bytes": extra_source.stat().st_size,
                        "selection": extra.get("selection"),
                        "private_speaker_map": None,
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

