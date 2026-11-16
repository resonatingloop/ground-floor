from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packet_draft import PacketDraftError, build_packet  # noqa: E402
from validate import ValidationError, scan_public_candidate, validate_packet, validate_pair  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PacketDraftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.messages = self.root / "messages.jsonl"
        records = [
            {
                "source_order": index,
                "author": {"display_label": "human" if index % 2 else "agent"},
                "content": f"fictional moment {index}",
            }
            for index in range(1, 5)
        ]
        self.messages.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        self.reference = self.root / "reference.txt"
        self.reference.write_text("fictional prior account\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def recipe(self, case_id: str = "case-a") -> Path:
        recipe = {
            "case_id": case_id,
            "prepared_at": "2026-11-16",
            "intended_analyst": None,
            "observer": {
                "slice": "fictional source orders 1-4",
                "projection": "neutral readable projection",
                "attribution_policy": "human to owner; agent to agent-a",
                "occlusion": "no provider request envelope",
                "selection_risk": "range boundaries may cue a result",
            },
            "omissions": ["fictional material outside orders 1-4"],
            "stage_a": [
                {
                    "source_path": str(self.messages),
                    "expected_sha256": digest(self.messages),
                    "output_name": "source-001.txt",
                    "mode": "jsonl-message-range",
                    "start_order": 1,
                    "end_order": 4,
                    "moment_prefix": "f",
                    "speaker_map": {"human": "owner", "agent": "agent-a"},
                    "role": "primary-source-projection",
                    "evidence_class": "fictional direct text",
                }
            ],
            "stage_b": [
                {
                    "source_path": str(self.reference),
                    "expected_sha256": digest(self.reference),
                    "output_name": "reference-001.txt",
                    "mode": "copy",
                    "role": "prior-reference-account",
                    "evidence_class": "fictional historical analysis",
                }
            ],
        }
        path = self.root / f"{case_id}.json"
        path.write_text(json.dumps(recipe), encoding="utf-8")
        return path

    def test_builds_and_validates_unapproved_draft(self) -> None:
        output = self.root / "out-a"
        manifest = build_packet(self.recipe(), output)
        validated = validate_packet(output)
        self.assertEqual(validated["packet_fingerprint"], manifest["packet_fingerprint"])
        self.assertEqual(validated["owner_gate"]["packet_approval"], None)
        self.assertFalse(validated["owner_gate"]["model_exposure_authorized"])
        self.assertEqual(validated["exposure_records"], [])

    def test_projection_uses_stable_neutral_moments(self) -> None:
        output = self.root / "out-a"
        build_packet(self.recipe(), output)
        projection = (output / "stage-a" / "source-001.txt").read_text(encoding="utf-8")
        self.assertIn("[ f-0001 | owner ]", projection)
        self.assertIn("[ f-0002 | agent-a ]", projection)
        self.assertNotIn("display_label", projection)

    def test_prompt_response_projection_preserves_sections(self) -> None:
        transcript = self.root / "transcript.md"
        transcript.write_text(
            "\n## Prompt:\nfirst question\n\n## Response:\nfirst answer\n"
            "\n## Prompt:\nsecond question\n\n## Response:\nsecond answer\n",
            encoding="utf-8",
        )
        recipe_path = self.recipe()
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        recipe["stage_a"] = [
            {
                "source_path": str(transcript),
                "expected_sha256": digest(transcript),
                "output_name": "source-001.txt",
                "mode": "prompt-response-sections",
                "moment_prefix": "p",
                "role": "primary-source-projection",
                "evidence_class": "fictional direct text",
            }
        ]
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        output = self.root / "prompt-out"
        build_packet(recipe_path, output)
        projection = (output / "stage-a" / "source-001.txt").read_text(encoding="utf-8")
        self.assertTrue(projection.startswith("private source projection\n"))
        self.assertIn("[ p-0001-owner ]", projection)
        self.assertIn("[ p-0001-assistant ]", projection)
        self.assertIn("[ p-0002-owner ]", projection)
        self.assertIn("second answer", projection)

    def test_chatgpt_tree_preserves_visible_branches_and_attachments(self) -> None:
        export_root = self.root / "export"
        export_root.mkdir()
        markdown_id = "file_aaa"
        image_id = "file_bbb"
        markdown_payload = b"# attached source\n"
        image_payload = b"fictional-png-bytes"
        (export_root / f"{markdown_id}.dat").write_bytes(markdown_payload)
        (export_root / f"{image_id}.dat").write_bytes(image_payload)

        def message(role: str, content: dict, created: float, attachments: list[dict] | None = None) -> dict:
            return {
                "author": {"role": role},
                "content": content,
                "create_time": created,
                "metadata": {"attachments": attachments or []},
            }

        conversation_id = "conversation-private-id"
        template_id = "project-private-id"
        mapping = {
            "root": {"parent": None, "message": None},
            "user-1": {
                "parent": "root",
                "message": message(
                    "user",
                    {"content_type": "text", "parts": ["opening visible turn"]},
                    1.0,
                    [{"id": markdown_id, "name": "private-name.md", "mime_type": "text/markdown", "size": len(markdown_payload)}],
                ),
            },
            "recap": {
                "parent": "user-1",
                "message": message("assistant", {"content_type": "reasoning_recap", "content": "hidden recap"}, 2.0),
            },
            "assistant-1": {
                "parent": "recap",
                "message": message("assistant", {"content_type": "text", "parts": ["visible answer"]}, 3.0),
            },
            "active": {
                "parent": "assistant-1",
                "message": message(
                    "user",
                    {
                        "content_type": "multimodal_text",
                        "parts": [
                            "active branch",
                            {"content_type": "image_asset_pointer", "asset_pointer": f"sediment://{image_id}"},
                        ],
                    },
                    4.0,
                    [{"id": image_id, "name": "private-image.png", "mime_type": "image/png", "size": len(image_payload)}],
                ),
            },
            "alternate": {
                "parent": "assistant-1",
                "message": message("user", {"content_type": "text", "parts": ["alternate branch"]}, 5.0),
            },
        }
        shard = export_root / "conversations-000.json"
        shard.write_text(
            json.dumps(
                [
                    {
                        "id": conversation_id,
                        "conversation_id": conversation_id,
                        "conversation_template_id": template_id,
                        "current_node": "active",
                        "mapping": mapping,
                    }
                ]
            ),
            encoding="utf-8",
        )
        recipe_path = self.recipe()
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        recipe["stage_a"] = [
            {
                "source_path": str(shard),
                "expected_sha256": digest(shard),
                "output_name": "source-001.txt",
                "mode": "chatgpt-conversation-tree",
                "conversation_id": conversation_id,
                "expected_conversation_template_id": template_id,
                "asset_root": str(export_root),
                "moment_prefix": "t",
                "role": "complete fictional conversation tree",
                "evidence_class": "fictional participant-visible evidence",
            }
        ]
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        output = self.root / "tree-out"
        manifest = build_packet(recipe_path, output)
        validate_packet(output)

        projection = (output / "stage-a" / "source-001.txt").read_text(encoding="utf-8")
        self.assertIn("complete participant-visible conversation tree", projection)
        self.assertIn("[ t-0003 | owner | parent t-0002 | path active", projection)
        self.assertIn("[ t-0004 | owner | parent t-0002 | path alternate", projection)
        self.assertIn("[attached file: attachment-001.md.export.txt]", projection)
        self.assertIn("[attached image: attachment-002.png]", projection)
        self.assertNotIn("hidden recap", projection)
        self.assertNotIn(conversation_id, projection)
        self.assertNotIn(markdown_id, projection)
        self.assertEqual((output / "stage-a" / "attachment-001.md.export.txt").read_bytes(), markdown_payload)
        self.assertEqual((output / "stage-a" / "attachment-002.png").read_bytes(), image_payload)
        self.assertEqual(len(manifest["stages"]["stage_a"]["files"]), 3)

        custody = (output / "custody.private.json").read_text(encoding="utf-8")
        self.assertIn(conversation_id, custody)
        self.assertIn(markdown_id, custody)
        (output / "stage-a" / "attachment-002.png").write_bytes(b"tampered")
        with self.assertRaises(ValidationError):
            validate_packet(output)

    def test_private_paths_do_not_enter_packet_manifest(self) -> None:
        output = self.root / "out-a"
        build_packet(self.recipe(), output)
        packet = (output / "packet.json").read_text(encoding="utf-8")
        custody = (output / "custody.private.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.messages), packet)
        self.assertIn(str(self.messages), custody)

    def test_source_fingerprint_change_is_rejected(self) -> None:
        recipe = self.recipe()
        self.messages.write_text("changed\n", encoding="utf-8")
        with self.assertRaises(PacketDraftError):
            build_packet(recipe, self.root / "out-a")

    def test_output_traversal_is_rejected(self) -> None:
        recipe_path = self.recipe()
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        recipe["stage_a"][0]["output_name"] = "../escape.txt"
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        with self.assertRaises(PacketDraftError):
            build_packet(recipe_path, self.root / "out-a")

    def test_tamper_invalidates_draft(self) -> None:
        output = self.root / "out-a"
        build_packet(self.recipe(), output)
        with (output / "stage-a" / "source-001.txt").open("a", encoding="utf-8") as handle:
            handle.write("tamper")
        with self.assertRaises(ValidationError):
            validate_packet(output)

    def test_custody_and_review_tamper_invalidate_draft(self) -> None:
        for filename in ("custody.private.json", "owner-review.txt"):
            with self.subTest(filename=filename):
                output = self.root / f"tamper-{filename.replace('.', '-')}"
                build_packet(self.recipe(), output)
                with (output / filename).open("a", encoding="utf-8") as handle:
                    handle.write("tamper")
                with self.assertRaises(ValidationError):
                    validate_packet(output)

    def test_non_empty_destination_is_refused(self) -> None:
        output = self.root / "occupied"
        output.mkdir()
        (output / "keep.txt").write_text("owner data", encoding="utf-8")
        with self.assertRaises(PacketDraftError):
            build_packet(self.recipe(), output)
        self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "owner data")

    def test_line_range_projection_is_exact(self) -> None:
        source = self.root / "lines.txt"
        source.write_bytes(b"one\ntwo\nthree\nfour\n")
        recipe_path = self.recipe()
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        recipe["stage_b"] = [
            {
                "source_path": str(source),
                "expected_sha256": digest(source),
                "output_name": "reference-001.txt",
                "mode": "line-range",
                "start_line": 2,
                "end_line": 3,
                "role": "bounded later context",
                "evidence_class": "fictional retrospective context",
            }
        ]
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        output = self.root / "line-range-out"
        build_packet(recipe_path, output)
        self.assertEqual((output / "stage-b" / "reference-001.txt").read_bytes(), b"two\nthree\n")

    def test_validator_refuses_premature_state_or_exposure(self) -> None:
        output = self.root / "out-a"
        build_packet(self.recipe(), output)
        manifest_path = output / "packet.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["state"] = "packet-approved"
        payload = dict(manifest)
        payload.pop("packet_fingerprint")
        manifest["packet_fingerprint"] = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValidationError):
            validate_packet(output)

    def test_parallel_pair_requires_distinct_cases_and_roots(self) -> None:
        first = self.root / "out-a"
        second = self.root / "out-b"
        build_packet(self.recipe("case-a"), first)
        build_packet(self.recipe("case-b"), second)
        left, right = validate_pair(first, second)
        self.assertNotEqual(left["case_id"], right["case_id"])
        with self.assertRaises(ValidationError):
            validate_pair(first, first)

    def test_public_boundary_rejects_private_paths_ids_and_overlap(self) -> None:
        candidate = self.root / "candidate.txt"
        candidate.write_text("clean derived claim\n", encoding="utf-8")
        self.assertEqual(scan_public_candidate(candidate), [])
        candidate.write_text("/home/person/private/file and msg_0123456789abcdef\n", encoding="utf-8")
        self.assertGreaterEqual(len(scan_public_candidate(candidate)), 2)
        long_line = "a sufficiently long fictional source sentence " * 4
        self.reference.write_text(long_line, encoding="utf-8")
        candidate.write_text(long_line, encoding="utf-8")
        self.assertTrue(any("overlap" in finding for finding in scan_public_candidate(candidate, [self.reference])))


if __name__ == "__main__":
    unittest.main()

