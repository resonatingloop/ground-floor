from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("settlement_build_protocol", ROOT / "build.py")
assert SPEC and SPEC.loader
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class PacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = build.render_files(build.load_study())

    def test_stage_a_is_neutral_and_stage_b_contains_reference_labels(self) -> None:
        stage_a = b"\n".join(payload for path, payload in self.files.items() if path.startswith("protocol/stage-a/"))
        stage_b = b"\n".join(payload for path, payload in self.files.items() if path.startswith("protocol/stage-b/"))
        for forbidden in (b"protective retention", b"stale capture", b"sourceObjectId", b"returnStages"):
            self.assertNotIn(forbidden, stage_a)
        self.assertIn(b"scenario-a", stage_a)
        self.assertIn(b"scenario-b", stage_a)
        self.assertIn(b"protective retention", stage_b)
        self.assertIn(b"stale capture", stage_b)

    def test_packet_manifest_binds_both_stages(self) -> None:
        packet = json.loads(self.files["protocol/packet-manifest.json"])
        self.assertEqual(build.sha256_bytes(self.files["protocol/stage-a/stage-manifest.json"]), packet["stageA"]["manifestSha256"])
        self.assertEqual(build.sha256_bytes(self.files["protocol/stage-b/stage-manifest.json"]), packet["stageB"]["manifestSha256"])


class RunReceiptTests(unittest.TestCase):
    def write_run(self, root: Path) -> Path:
        bundle = root / "frozen-bundle"
        build.write_bundle(bundle, build.render_files(build.load_study()))
        stage_a_manifest = json.loads((bundle / "protocol/stage-a/stage-manifest.json").read_text(encoding="utf-8"))
        allowlisted = [*stage_a_manifest["files"], "stage-manifest.json"]
        stage_b_manifest = json.loads((bundle / "protocol/stage-b/stage-manifest.json").read_text(encoding="utf-8"))
        stage_b_allowlisted = [*stage_b_manifest["files"], "stage-manifest.json"]
        records = {
            "stage-a-return.md": "first reading\n",
            "stage-b-return.md": "post reveal\n",
            "concordance.md": "preserved disagreement\n",
        }
        for name, content in records.items():
            (root / name).write_text(content, encoding="utf-8")
        exposure_record = {
            "schemaVersion": 1,
            "analystId": "cold-analyst",
            "forkTurns": "none",
            "suppliedFiles": allowlisted,
            "openedFiles": allowlisted,
            "openedAnythingElse": False,
            "conversationInherited": False,
            "hiddenContextDeclared": True,
            "hiddenContext": "runtime and training context are not fully observable",
            "stageAReceivedBeforeStageB": True,
        }
        (root / "exposure.json").write_text(json.dumps(exposure_record), encoding="utf-8")
        stage_b_exposure_record = {
            "schemaVersion": 1,
            "analystId": "cold-analyst",
            "suppliedFiles": stage_b_allowlisted,
            "openedFiles": stage_b_allowlisted,
            "openedAnythingElse": False,
            "renderedInteraction": True,
            "scenariosInteracted": ["scenario-a", "scenario-b"],
        }
        (root / "exposure-stage-b.json").write_text(json.dumps(stage_b_exposure_record), encoding="utf-8")
        packet_path = bundle / "protocol/packet-manifest.json"
        receipt = {
            "schemaVersion": 1,
            "runId": "cold-001",
            "status": "complete",
            "builderId": "primary-builder",
            "analystId": "cold-analyst",
            "conversationInherited": False,
            "coachingBetweenStages": False,
            "packetManifestFile": "frozen-bundle/protocol/packet-manifest.json",
            "packetManifestSha256": build.sha256_file(packet_path),
            "stageA": {
                "returnFile": "stage-a-return.md",
                "returnSha256": build.sha256_file(root / "stage-a-return.md"),
                "receivedBeforeStageB": True,
            },
            "stageB": {"file": "stage-b-return.md", "sha256": build.sha256_file(root / "stage-b-return.md")},
            "stageBExposure": {
                "file": "exposure-stage-b.json",
                "sha256": build.sha256_file(root / "exposure-stage-b.json"),
                "openedOnlyAllowlistedFiles": True,
                "renderedInteraction": True,
            },
            "exposure": {
                "file": "exposure.json",
                "sha256": build.sha256_file(root / "exposure.json"),
                "openedOnlyAllowlistedFiles": True,
                "hiddenContextDeclared": True,
            },
            "concordance": {"file": "concordance.md", "sha256": build.sha256_file(root / "concordance.md")},
        }
        path = root / "run.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return path

    def mutate_receipt(self, path: Path, mutation) -> dict:
        record = json.loads(path.read_text(encoding="utf-8"))
        mutation(record)
        path.write_text(json.dumps(record), encoding="utf-8")
        return record

    def test_complete_run_is_bound_to_real_packet_and_exposure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record = build.validate_run_receipt(self.write_run(Path(temporary)))
            self.assertEqual("complete", record["status"])

    def test_wrong_packet_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_run(Path(temporary))
            self.mutate_receipt(path, lambda record: record.__setitem__("packetManifestSha256", "0" * 64))
            with self.assertRaisesRegex(build.StudyError, "packet manifest fingerprint"):
                build.validate_run_receipt(path)

    def test_mutated_stage_leaf_is_rejected_even_when_manifest_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_run(root)
            (root / "frozen-bundle/protocol/stage-a/trace.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(build.StudyError, "leaf fingerprint"):
                build.validate_run_receipt(path)

    def test_duplicate_evidence_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_run(Path(temporary))
            def duplicate(record):
                record["stageB"]["file"] = record["stageA"]["returnFile"]
                record["stageB"]["sha256"] = record["stageA"]["returnSha256"]
            self.mutate_receipt(path, duplicate)
            with self.assertRaisesRegex(build.StudyError, "distinct files"):
                build.validate_run_receipt(path)

    def test_exposure_record_is_parsed_not_merely_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_run(root)
            exposure = json.loads((root / "exposure.json").read_text(encoding="utf-8"))
            exposure["openedAnythingElse"] = True
            (root / "exposure.json").write_text(json.dumps(exposure), encoding="utf-8")
            record = json.loads(path.read_text(encoding="utf-8"))
            record["exposure"]["sha256"] = build.sha256_file(root / "exposure.json")
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(build.StudyError, "undeclared exposure"):
                build.validate_run_receipt(path)

    def test_coaching_requires_contaminated_status_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_run(Path(temporary))
            self.mutate_receipt(path, lambda record: record.__setitem__("coachingBetweenStages", True))
            with self.assertRaisesRegex(build.StudyError, "may not include coaching"):
                build.validate_run_receipt(path)

    def test_complete_run_requires_rendered_stage_b_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_run(root)
            exposure = json.loads((root / "exposure-stage-b.json").read_text(encoding="utf-8"))
            exposure["renderedInteraction"] = False
            exposure["scenariosInteracted"] = []
            (root / "exposure-stage-b.json").write_text(json.dumps(exposure), encoding="utf-8")
            record = json.loads(path.read_text(encoding="utf-8"))
            record["stageBExposure"]["sha256"] = build.sha256_file(root / "exposure-stage-b.json")
            record["stageBExposure"]["renderedInteraction"] = False
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(build.StudyError, "rendered interaction"):
                build.validate_run_receipt(path)

    def test_contaminated_coaching_run_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_run(Path(temporary))
            def contaminate(record):
                record["status"] = "contaminated"
                record["coachingBetweenStages"] = True
                record["contaminationReasons"] = ["coaching-between-stages"]
            self.mutate_receipt(path, contaminate)
            self.assertEqual("contaminated", build.validate_run_receipt(path)["status"])

    def test_role_collapse_is_rejected_for_complete_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_run(Path(temporary))
            self.mutate_receipt(path, lambda record: record.__setitem__("analystId", record["builderId"]))
            with self.assertRaisesRegex(build.StudyError, "must be distinct"):
                build.validate_run_receipt(path)

    def test_rewritten_return_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_run(root)
            (root / "stage-a-return.md").write_text("rewritten\n", encoding="utf-8")
            with self.assertRaisesRegex(build.StudyError, "fingerprint"):
                build.validate_run_receipt(path)


if __name__ == "__main__":
    unittest.main()
