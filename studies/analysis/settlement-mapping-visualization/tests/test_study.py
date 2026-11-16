from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("settlement_build", ROOT / "build.py")
assert SPEC and SPEC.loader
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class StudyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.study = json.loads((ROOT / "study.json").read_text(encoding="utf-8"))

    def test_valid_matched_pair(self) -> None:
        validated = build.validate_study(copy.deepcopy(self.study))
        self.assertEqual(2, len(validated["scenarios"]))
        self.assertEqual(
            [stage["band"] for stage in validated["scenarios"][0]["returnStages"]],
            [stage["band"] for stage in validated["scenarios"][1]["returnStages"]],
        )

    def test_admission_is_distinct_from_receipt_and_reliance(self) -> None:
        validated = build.validate_study(copy.deepcopy(self.study))
        for scenario in validated["scenarios"]:
            actions = [moment["action"] for moment in scenario["moments"]]
            self.assertEqual(["introduction", "receipt", "admission", "reliance", "challenge"], actions[:5])

    def test_unknown_action_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.study)
        candidate["scenarios"][0]["moments"][0]["action"] = "vibes"
        with self.assertRaisesRegex(build.StudyError, "action is unknown"):
            build.validate_study(candidate)

    def test_broken_cross_reference_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.study)
        candidate["scenarios"][0]["dependencies"][0]["targetMomentId"] = "missing-moment"
        with self.assertRaisesRegex(build.StudyError, "unresolved moment"):
            build.validate_study(candidate)

    def test_unordered_moments_are_rejected(self) -> None:
        candidate = copy.deepcopy(self.study)
        candidate["scenarios"][0]["moments"][1]["order"] = 8
        with self.assertRaisesRegex(build.StudyError, "contiguous"):
            build.validate_study(candidate)

    def test_duplicate_cold_ids_are_rejected(self) -> None:
        candidate = copy.deepcopy(self.study)
        candidate["scenarios"][0]["moments"][1]["coldId"] = "a-01"
        with self.assertRaisesRegex(build.StudyError, "duplicate"):
            build.validate_study(candidate)

    def test_active_fixture_string_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.study)
        candidate["warning"] = "open https://example.invalid"
        with self.assertRaisesRegex(build.StudyError, "active markup"):
            build.validate_study(candidate)


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.study = build.load_study()

    def test_render_is_deterministic_and_inert(self) -> None:
        first = build.render_files(self.study)
        second = build.render_files(self.study)
        self.assertEqual(first, second)
        self.assertEqual(
            {
                "index.html",
                "study.css",
                "study.js",
                "study-data.js",
                "bundle-manifest.json",
                "protocol/README.md",
                "protocol/packet-manifest.json",
                "protocol/stage-a/definitions.md",
                "protocol/stage-a/response-template.md",
                "protocol/stage-a/stage-a-prompt.md",
                "protocol/stage-a/stage-manifest.json",
                "protocol/stage-a/trace.json",
                "protocol/stage-b/stage-b-prompt.md",
                "protocol/stage-b/stage-manifest.json",
                "protocol/stage-b/visualization/index.html",
                "protocol/stage-b/visualization/study.css",
                "protocol/stage-b/visualization/study.js",
                "protocol/stage-b/visualization/study-data.js",
            },
            set(first),
        )
        runtime = b"\n".join(first[path] for path in ("index.html", "study.css", "study.js"))
        for forbidden in (b"http://", b"https://", b"fetch(", b"XMLHttpRequest", b"localStorage", b"sessionStorage", b"WebSocket", b"serviceWorker"):
            self.assertNotIn(forbidden, runtime)

    def test_fresh_build_and_check(self) -> None:
        files = build.render_files(self.study)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            build.write_bundle(output, files)
            build.check_bundle(output, files)
            with self.assertRaisesRegex(build.StudyError, "must not already exist"):
                build.write_bundle(output, files)
            (output / "unexpected.txt").write_text("nope", encoding="utf-8")
            with self.assertRaisesRegex(build.StudyError, "extra=unexpected.txt"):
                build.check_bundle(output, files)

    def test_manifest_fingerprints_every_generated_file(self) -> None:
        files = build.render_files(self.study)
        manifest = json.loads(files["bundle-manifest.json"])
        expected = set(files) - {"bundle-manifest.json"}
        self.assertEqual(expected, set(manifest["files"]))
        for path, fingerprint in manifest["files"].items():
            self.assertEqual(build.sha256_bytes(files[path]), fingerprint)


if __name__ == "__main__":
    unittest.main()
