#!/usr/bin/env python3
"""validate and build the fictional settlement-mapping visualization."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
PROTOCOL = ROOT / "protocol"
STUDY_PATH = ROOT / "study.json"

LAYERS = {"evidential", "inferential", "deontic", "positional", "organizational"}
ACTIONS = {"introduction", "receipt", "admission", "reliance", "challenge", "preservation", "residue"}
PATH_ROLES = {"forward-displacement", "downstream-reliance", "reverse-pressure", "preservation", "residue"}
BANDS = {"priority set", "operative", "challenged", "non-return"}
MOMENT_EVIDENCE = {
    "fictional utterance",
    "fictional acknowledgment",
    "fictional working record",
    "fictional task selection",
    "fictional procedural advice",
    "fictional authorized instruction",
    "fictional completed action",
}
DEPENDENCY_EVIDENCE = {
    "authored within-trace dependency",
    "authored persistence relation",
    "authored authority mismatch",
    "authored residue relation",
}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ACTIVE_RE = re.compile(r"[<>]|(?:https?|javascript|data):|on(?:error|load)\s*=", re.IGNORECASE)


class StudyError(ValueError):
    """Raised when source or run data violates the bounded contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any, *, pretty: bool = True) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return text.encode("utf-8")


def require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StudyError(f"{where} must be an object")
    return value


def require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise StudyError(f"{where} must be a list")
    return value


def require_keys(value: dict[str, Any], keys: set[str], where: str) -> None:
    missing = sorted(keys - value.keys())
    if missing:
        raise StudyError(f"{where} missing required fields: {', '.join(missing)}")


def validate_id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise StudyError(f"{where} must be a lowercase kebab identifier")
    return value


def validate_text_tree(value: Any, where: str = "study") -> None:
    if isinstance(value, str):
        if not value.strip():
            raise StudyError(f"{where} contains an empty string")
        if "\x00" in value or ACTIVE_RE.search(value):
            raise StudyError(f"{where} contains active markup, a url, or an executable fragment")
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_text_tree(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_text_tree(item, f"{where}[{index}]")


def ensure_unique(values: list[str], where: str) -> None:
    if len(values) != len(set(values)):
        raise StudyError(f"{where} contains duplicate identifiers")


def validate_study(data: Any) -> dict[str, Any]:
    study = require_mapping(data, "study")
    require_keys(study, {"schemaVersion", "title", "fictional", "warning", "standingLayers", "scenarios"}, "study")
    if study["schemaVersion"] != 1:
        raise StudyError("study.schemaVersion must be 1")
    if study["fictional"] is not True:
        raise StudyError("study.fictional must be true")
    layers = require_list(study["standingLayers"], "study.standingLayers")
    if set(layers) != LAYERS or len(layers) != len(LAYERS):
        raise StudyError("study.standingLayers must contain the five provisional layers exactly once")

    scenarios = require_list(study["scenarios"], "study.scenarios")
    if len(scenarios) != 2:
        raise StudyError("study.scenarios must contain the matched fictional pair")
    scenario_ids: list[str] = []
    cold_scenario_ids: list[str] = []
    band_sequences: list[list[str]] = []

    for scenario_index, raw_scenario in enumerate(scenarios):
        where = f"study.scenarios[{scenario_index}]"
        scenario = require_mapping(raw_scenario, where)
        require_keys(
            scenario,
            {"id", "coldId", "label", "shortLabel", "neutralLabel", "neutralMeta", "observer", "changeCondition", "standingObjects", "moments", "dependencies", "returnStages"},
            where,
        )
        scenario_ids.append(validate_id(scenario["id"], f"{where}.id"))
        cold_scenario_ids.append(validate_id(scenario["coldId"], f"{where}.coldId"))

        observer = require_mapping(scenario["observer"], f"{where}.observer")
        if set(observer) != {"slice", "projection", "attribution", "occlusion"}:
            raise StudyError(f"{where}.observer must declare slice, projection, attribution, and occlusion")
        condition = require_mapping(scenario["changeCondition"], f"{where}.changeCondition")
        require_keys(condition, {"priority", "reversePressure", "revisionAuthority", "interpretationLabel", "interpretation", "nonClaim"}, f"{where}.changeCondition")

        objects = require_list(scenario["standingObjects"], f"{where}.standingObjects")
        object_ids: list[str] = []
        for object_index, raw_object in enumerate(objects):
            object_where = f"{where}.standingObjects[{object_index}]"
            obj = require_mapping(raw_object, object_where)
            require_keys(obj, {"id", "proposition", "kind", "relation", "claimCeiling"}, object_where)
            object_ids.append(validate_id(obj["id"], f"{object_where}.id"))
            if obj["kind"] not in LAYERS:
                raise StudyError(f"{object_where}.kind is unknown")
        ensure_unique(object_ids, f"{where}.standingObjects")

        moments = require_list(scenario["moments"], f"{where}.moments")
        if len(moments) < 4:
            raise StudyError(f"{where}.moments must contain a complete path")
        moment_ids: list[str] = []
        cold_moment_ids: list[str] = []
        for moment_index, raw_moment in enumerate(moments):
            moment_where = f"{where}.moments[{moment_index}]"
            moment = require_mapping(raw_moment, moment_where)
            require_keys(moment, {"id", "coldId", "order", "actor", "action", "layer", "objectId", "label", "text", "evidenceClass"}, moment_where)
            moment_ids.append(validate_id(moment["id"], f"{moment_where}.id"))
            cold_moment_ids.append(validate_id(moment["coldId"], f"{moment_where}.coldId"))
            if moment["order"] != moment_index + 1:
                raise StudyError(f"{moment_where}.order must be contiguous and source ordered")
            if moment["action"] not in ACTIONS:
                raise StudyError(f"{moment_where}.action is unknown")
            if moment["layer"] not in LAYERS:
                raise StudyError(f"{moment_where}.layer is unknown")
            if moment["objectId"] not in object_ids:
                raise StudyError(f"{moment_where}.objectId is unresolved")
            if moment["evidenceClass"] not in MOMENT_EVIDENCE:
                raise StudyError(f"{moment_where}.evidenceClass is unknown")
        ensure_unique(moment_ids, f"{where}.moments")
        ensure_unique(cold_moment_ids, f"{where}.moments cold ids")
        moments_by_id = {moment["id"]: moment for moment in moments}

        dependencies = require_list(scenario["dependencies"], f"{where}.dependencies")
        dependency_ids: list[str] = []
        for dependency_index, raw_dependency in enumerate(dependencies):
            dependency_where = f"{where}.dependencies[{dependency_index}]"
            dependency = require_mapping(raw_dependency, dependency_where)
            require_keys(
                dependency,
                {"id", "sourceObjectId", "sourceMomentId", "targetMomentId", "relation", "support", "evidenceClass", "alternative", "nonClaim"},
                dependency_where,
            )
            dependency_ids.append(validate_id(dependency["id"], f"{dependency_where}.id"))
            if dependency["sourceObjectId"] not in object_ids:
                raise StudyError(f"{dependency_where}.sourceObjectId is unresolved")
            if dependency["sourceMomentId"] not in moment_ids or dependency["targetMomentId"] not in moment_ids:
                raise StudyError(f"{dependency_where} contains an unresolved moment reference")
            if moments_by_id[dependency["sourceMomentId"]]["objectId"] != dependency["sourceObjectId"]:
                raise StudyError(f"{dependency_where}.sourceObjectId must match its source moment object")
            if dependency["evidenceClass"] not in DEPENDENCY_EVIDENCE:
                raise StudyError(f"{dependency_where}.evidenceClass is unknown")
        ensure_unique(dependency_ids, f"{where}.dependencies")

        stages = require_list(scenario["returnStages"], f"{where}.returnStages")
        stage_ids: list[str] = []
        bands: list[str] = []
        for stage_index, raw_stage in enumerate(stages):
            stage_where = f"{where}.returnStages[{stage_index}]"
            stage = require_mapping(raw_stage, stage_where)
            require_keys(stage, {"id", "order", "band", "role", "momentId", "interpretation"}, stage_where)
            stage_ids.append(validate_id(stage["id"], f"{stage_where}.id"))
            if stage["order"] != stage_index + 1:
                raise StudyError(f"{stage_where}.order must be contiguous and source ordered")
            if stage["band"] not in BANDS:
                raise StudyError(f"{stage_where}.band is unknown")
            if stage["role"] not in PATH_ROLES:
                raise StudyError(f"{stage_where}.role is unknown")
            if stage["momentId"] not in moment_ids:
                raise StudyError(f"{stage_where}.momentId is unresolved")
            bands.append(stage["band"])
        ensure_unique(stage_ids, f"{where}.returnStages")
        band_sequences.append(bands)

    ensure_unique(scenario_ids, "study.scenarios")
    ensure_unique(cold_scenario_ids, "study.scenarios cold ids")
    if band_sequences[0] != band_sequences[1]:
        raise StudyError("matched scenarios must preserve comparable return-path bands")
    validate_text_tree(study)
    return study


def load_study(path: Path = STUDY_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudyError(f"could not read study data: {exc}") from exc
    return validate_study(value)


def neutral_trace(study: dict[str, Any]) -> dict[str, Any]:
    scenarios = []
    for scenario in study["scenarios"]:
        scenarios.append(
            {
                "id": scenario["coldId"],
                "observer": scenario["observer"],
                "moments": [
                    {
                        "id": moment["coldId"],
                        "order": moment["order"],
                        "actor": moment["actor"],
                        "text": moment["text"],
                        "evidenceClass": moment["evidenceClass"],
                    }
                    for moment in scenario["moments"]
                ],
            }
        )
    return {
        "schemaVersion": 1,
        "fictional": True,
        "warning": "neutral fictional trace; no reference map or answer key is included",
        "scenarios": scenarios,
    }


DEFINITIONS = """# bounded operational definitions

- interactional standing: the capacity of a proposition, relation, rule, role,
  or objective to organize what may be inferred, required, decided, or done
  next inside the displayed slice.
- consequential reliance: a later move whose organization depends on the
  candidate standing relation. acknowledgment alone is insufficient.
- reverse pressure: a move that withdraws, contradicts, challenges, or replaces
  a relation that has organized earlier action.
- interactional hysteresis: path-dependent non-return after relevant pressure
  is reversed. non-return is not automatically harmful.
- valence: a separate judgment about whether persistence preserves an endorsed
  priority or resists a warranted transition.

these terms are a response aperture, not an exhaustive codebook or answer key.
"""


def stage_manifest(files: dict[str, bytes]) -> bytes:
    return json_bytes(
        {
            "schemaVersion": 1,
            "files": {path: sha256_bytes(payload) for path, payload in sorted(files.items())},
        }
    )


def render_files(study: dict[str, Any]) -> dict[str, bytes]:
    payload = json.dumps(study, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    main_files = {
        "index.html": (STATIC / "index.html").read_bytes(),
        "study.css": (STATIC / "study.css").read_bytes(),
        "study.js": (STATIC / "study.js").read_bytes(),
        "study-data.js": f"window.__SETTLEMENT_STUDY__ = JSON.parse({json.dumps(payload)});\n".encode("utf-8"),
    }

    stage_a = {
        "stage-a-prompt.md": (PROTOCOL / "stage-a-prompt.md").read_bytes(),
        "response-template.md": (PROTOCOL / "response-template.md").read_bytes(),
        "definitions.md": DEFINITIONS.encode("utf-8"),
        "trace.json": json_bytes(neutral_trace(study)),
    }
    stage_a["stage-manifest.json"] = stage_manifest(stage_a)

    stage_b = {
        "stage-b-prompt.md": (PROTOCOL / "stage-b-prompt.md").read_bytes(),
        **{f"visualization/{path}": payload for path, payload in main_files.items()},
    }
    stage_b["stage-manifest.json"] = stage_manifest(stage_b)

    files = dict(main_files)
    files["protocol/README.md"] = (PROTOCOL / "README.md").read_bytes()
    files.update({f"protocol/stage-a/{path}": payload for path, payload in stage_a.items()})
    files.update({f"protocol/stage-b/{path}": payload for path, payload in stage_b.items()})
    files["protocol/packet-manifest.json"] = json_bytes(
        {
            "schemaVersion": 1,
            "studySourceSha256": sha256_file(STUDY_PATH),
            "stageA": {
                "path": "stage-a",
                "manifestSha256": sha256_bytes(stage_a["stage-manifest.json"]),
            },
            "stageB": {
                "path": "stage-b",
                "manifestSha256": sha256_bytes(stage_b["stage-manifest.json"]),
            },
            "authority": "fictional packet for one bounded built-in collaboration sub-agent run",
        }
    )
    files["bundle-manifest.json"] = json_bytes(
        {
            "schemaVersion": 1,
            "sourceSha256": sha256_file(STUDY_PATH),
            "files": {path: sha256_bytes(payload) for path, payload in sorted(files.items())},
        }
    )
    return files


def write_bundle(output: Path, files: dict[str, bytes]) -> None:
    if output.exists():
        raise StudyError(f"output must not already exist: {output}")
    output.mkdir(parents=True)
    try:
        for relative, payload in sorted(files.items()):
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def check_bundle(output: Path, expected: dict[str, bytes]) -> None:
    if not output.is_dir():
        raise StudyError(f"bundle does not exist: {output}")
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    expected_paths = set(expected)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    changed = sorted(
        relative
        for relative in expected_paths & actual_paths
        if (output / relative).read_bytes() != expected[relative]
    )
    if missing or extra or changed:
        parts = []
        if missing:
            parts.append("missing=" + ",".join(missing))
        if extra:
            parts.append("extra=" + ",".join(extra))
        if changed:
            parts.append("changed=" + ",".join(changed))
        raise StudyError("bundle differs from source: " + " ".join(parts))


def safe_relative_file(run_root: Path, value: Any, where: str) -> Path:
    if not isinstance(value, str):
        raise StudyError(f"{where} must be a relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise StudyError(f"{where} must stay inside the run directory")
    path = run_root.joinpath(*pure.parts)
    if not path.is_file():
        raise StudyError(f"{where} does not exist: {value}")
    return path


def read_json_object(path: Path, where: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudyError(f"could not read {where}: {exc}") from exc
    return require_mapping(value, where)


def validate_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise StudyError(f"{where} must be a sha-256 fingerprint")
    return value


def validate_run_receipt(path: Path) -> dict[str, Any]:
    record = read_json_object(path, "run receipt")
    require_keys(
        record,
        {
            "schemaVersion",
            "runId",
            "status",
            "builderId",
            "analystId",
            "conversationInherited",
            "coachingBetweenStages",
            "packetManifestFile",
            "packetManifestSha256",
            "stageA",
            "exposure",
        },
        "run",
    )
    if record["schemaVersion"] != 1:
        raise StudyError("run.schemaVersion must be 1")
    validate_id(record["runId"], "run.runId")
    if record["status"] not in {"complete", "contaminated", "incomplete"}:
        raise StudyError("run.status is unknown")
    role_collapsed = record["builderId"] == record["analystId"]
    inherited = record["conversationInherited"] is not False
    coached = record["coachingBetweenStages"] is not False
    reasons = record.get("contaminationReasons", [])
    if record["status"] == "contaminated":
        if not isinstance(reasons, list) or not reasons or not all(isinstance(item, str) and item for item in reasons):
            raise StudyError("a contaminated run must name its contamination reasons")
    elif reasons:
        raise StudyError("only a contaminated run may carry contamination reasons")
    if record["status"] == "complete" and role_collapsed:
        raise StudyError("builder and analyst must be distinct in a complete cold run")
    if record["status"] == "complete" and inherited:
        raise StudyError("a complete cold run may not inherit the builder conversation")
    if record["status"] == "complete" and coached:
        raise StudyError("a complete cold run may not include coaching between stages")
    if role_collapsed and "role-collapse" not in reasons:
        raise StudyError("role collapse must be marked as contamination")
    if inherited and "inherited-conversation" not in reasons:
        raise StudyError("inherited conversation must be marked as contamination")
    if coached and "coaching-between-stages" not in reasons:
        raise StudyError("coaching between stages must be marked as contamination")
    if "coaching-between-stages" in reasons and not coached:
        raise StudyError("coaching contamination reason requires coachingBetweenStages=true")

    root = path.parent
    packet_path = safe_relative_file(root, record["packetManifestFile"], "run.packetManifestFile")
    packet_sha = validate_sha(record["packetManifestSha256"], "run.packetManifestSha256")
    if sha256_file(packet_path) != packet_sha:
        raise StudyError("packet manifest fingerprint does not match")
    packet = read_json_object(packet_path, "packet manifest")
    require_keys(packet, {"schemaVersion", "stageA", "stageB"}, "packet manifest")
    if packet["schemaVersion"] != 1:
        raise StudyError("packet manifest schemaVersion must be 1")

    packet_stages: dict[str, dict[str, Any]] = {}
    for stage_key in ("stageA", "stageB"):
        stage_ref = require_mapping(packet[stage_key], f"packet manifest.{stage_key}")
        require_keys(stage_ref, {"path", "manifestSha256"}, f"packet manifest.{stage_key}")
        stage_manifest_path = safe_relative_file(
            packet_path.parent,
            f"{stage_ref['path']}/stage-manifest.json",
            f"packet manifest.{stage_key}.path",
        )
        expected_manifest_sha = validate_sha(
            stage_ref["manifestSha256"], f"packet manifest.{stage_key}.manifestSha256"
        )
        if sha256_file(stage_manifest_path) != expected_manifest_sha:
            raise StudyError(f"{stage_key} manifest fingerprint does not match packet manifest")
        stage_manifest = read_json_object(stage_manifest_path, f"{stage_key} manifest")
        require_keys(stage_manifest, {"schemaVersion", "files"}, f"{stage_key} manifest")
        if stage_manifest["schemaVersion"] != 1:
            raise StudyError(f"{stage_key} manifest schemaVersion must be 1")
        stage_files = require_mapping(stage_manifest["files"], f"{stage_key} manifest.files")
        for relative, expected_sha in stage_files.items():
            leaf_path = safe_relative_file(stage_manifest_path.parent, relative, f"{stage_key} manifest.files.{relative}")
            if sha256_file(leaf_path) != validate_sha(expected_sha, f"{stage_key} manifest.files.{relative}"):
                raise StudyError(f"{stage_key} leaf fingerprint does not match: {relative}")
        actual_stage_files = {
            leaf.relative_to(stage_manifest_path.parent).as_posix()
            for leaf in stage_manifest_path.parent.rglob("*")
            if leaf.is_file() and leaf != stage_manifest_path
        }
        if actual_stage_files != set(stage_files):
            raise StudyError(f"{stage_key} manifest file set does not match its directory")
        packet_stages[stage_key] = stage_manifest

    stage_a = require_mapping(record["stageA"], "run.stageA")
    require_keys(stage_a, {"returnFile", "returnSha256", "receivedBeforeStageB"}, "run.stageA")
    if stage_a["receivedBeforeStageB"] is not True:
        if "premature-reveal" not in reasons:
            raise StudyError("premature reveal must be marked as contamination")
    stage_a_path = safe_relative_file(root, stage_a["returnFile"], "run.stageA.returnFile")
    if sha256_file(stage_a_path) != validate_sha(stage_a["returnSha256"], "run.stageA.returnSha256"):
        raise StudyError("stage-a return fingerprint does not match")

    exposure = require_mapping(record["exposure"], "run.exposure")
    require_keys(exposure, {"file", "sha256", "openedOnlyAllowlistedFiles", "hiddenContextDeclared"}, "run.exposure")
    exposure_path = safe_relative_file(root, exposure["file"], "run.exposure.file")
    if sha256_file(exposure_path) != validate_sha(exposure["sha256"], "run.exposure.sha256"):
        raise StudyError("exposure fingerprint does not match")
    exposure_record = read_json_object(exposure_path, "exposure record")
    require_keys(
        exposure_record,
        {
            "schemaVersion",
            "analystId",
            "forkTurns",
            "suppliedFiles",
            "openedFiles",
            "openedAnythingElse",
            "conversationInherited",
            "hiddenContextDeclared",
            "hiddenContext",
            "stageAReceivedBeforeStageB",
        },
        "exposure record",
    )
    allowlisted = set(require_mapping(packet_stages["stageA"]["files"], "stageA manifest.files"))
    allowlisted.add("stage-manifest.json")
    supplied = require_list(exposure_record["suppliedFiles"], "exposure record.suppliedFiles")
    opened = require_list(exposure_record["openedFiles"], "exposure record.openedFiles")
    exposure_exact = (
        exposure_record["schemaVersion"] == 1
        and exposure_record["analystId"] == record["analystId"]
        and exposure_record["forkTurns"] == "none"
        and exposure_record["conversationInherited"] is record["conversationInherited"]
        and exposure_record["openedAnythingElse"] is False
        and exposure_record["hiddenContextDeclared"] is True
        and isinstance(exposure_record["hiddenContext"], str)
        and bool(exposure_record["hiddenContext"].strip())
        and exposure_record["stageAReceivedBeforeStageB"] is stage_a["receivedBeforeStageB"]
        and set(supplied) == allowlisted
        and len(supplied) == len(allowlisted)
        and set(opened) == allowlisted
        and len(opened) == len(allowlisted)
    )
    exposure_failed = (
        exposure["openedOnlyAllowlistedFiles"] is not True
        or exposure["hiddenContextDeclared"] is not True
        or not exposure_exact
    )
    if exposure_failed and "undeclared-exposure" not in reasons:
        raise StudyError("undeclared exposure must be marked as contamination")

    record_paths = [stage_a_path, exposure_path]

    if record["status"] == "complete":
        require_keys(record, {"stageB", "stageBExposure", "concordance"}, "complete run")
        for key in ("stageB", "concordance"):
            item = require_mapping(record[key], f"run.{key}")
            require_keys(item, {"file", "sha256"}, f"run.{key}")
            item_path = safe_relative_file(root, item["file"], f"run.{key}.file")
            if sha256_file(item_path) != validate_sha(item["sha256"], f"run.{key}.sha256"):
                raise StudyError(f"{key} fingerprint does not match")
            record_paths.append(item_path)
        stage_b_exposure = require_mapping(record["stageBExposure"], "run.stageBExposure")
        require_keys(
            stage_b_exposure,
            {"file", "sha256", "openedOnlyAllowlistedFiles", "renderedInteraction"},
            "run.stageBExposure",
        )
        stage_b_exposure_path = safe_relative_file(root, stage_b_exposure["file"], "run.stageBExposure.file")
        if sha256_file(stage_b_exposure_path) != validate_sha(stage_b_exposure["sha256"], "run.stageBExposure.sha256"):
            raise StudyError("stage-b exposure fingerprint does not match")
        stage_b_record = read_json_object(stage_b_exposure_path, "stage-b exposure record")
        require_keys(
            stage_b_record,
            {
                "schemaVersion",
                "analystId",
                "suppliedFiles",
                "openedFiles",
                "openedAnythingElse",
                "renderedInteraction",
                "scenariosInteracted",
            },
            "stage-b exposure record",
        )
        stage_b_allowlisted = set(require_mapping(packet_stages["stageB"]["files"], "stageB manifest.files"))
        stage_b_allowlisted.add("stage-manifest.json")
        stage_b_supplied = require_list(stage_b_record["suppliedFiles"], "stage-b exposure record.suppliedFiles")
        stage_b_opened = require_list(stage_b_record["openedFiles"], "stage-b exposure record.openedFiles")
        scenarios_interacted = require_list(stage_b_record["scenariosInteracted"], "stage-b exposure record.scenariosInteracted")
        stage_b_exact = (
            stage_b_record["schemaVersion"] == 1
            and stage_b_record["analystId"] == record["analystId"]
            and stage_b_record["openedAnythingElse"] is False
            and stage_b_record["renderedInteraction"] is True
            and stage_b_exposure["openedOnlyAllowlistedFiles"] is True
            and stage_b_exposure["renderedInteraction"] is True
            and set(stage_b_supplied) == stage_b_allowlisted
            and len(stage_b_supplied) == len(stage_b_allowlisted)
            and set(stage_b_opened) == stage_b_allowlisted
            and len(stage_b_opened) == len(stage_b_allowlisted)
            and len(set(scenarios_interacted)) >= 2
            and all(isinstance(item, str) and item for item in scenarios_interacted)
        )
        if not stage_b_exact:
            raise StudyError("complete run requires exact stage-b exposure and rendered interaction with both scenarios")
        record_paths.append(stage_b_exposure_path)
    if len(record_paths) != len(set(record_paths)):
        raise StudyError("stage-a, stage-b, exposure, stage-b exposure, and concordance records must be distinct files")
    return record


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="fresh bundle output directory")
    parser.add_argument("--check", action="store_true", help="compare an existing bundle with deterministic source output")
    parser.add_argument("--validate-run", type=Path, help="validate a cold-run receipt and its local records")
    args = parser.parse_args(argv)
    if args.validate_run and (args.output or args.check):
        parser.error("--validate-run cannot be combined with bundle options")
    if not args.validate_run and not args.output:
        parser.error("--output is required for build or check")
    if args.check and not args.output:
        parser.error("--check requires --output")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.validate_run:
            record = validate_run_receipt(args.validate_run)
            print(f"valid run receipt: {record['runId']} status={record['status']}")
            return 0
        study = load_study()
        files = render_files(study)
        if args.check:
            check_bundle(args.output, files)
            print(f"bundle is current: {args.output} files={len(files)}")
        else:
            write_bundle(args.output, files)
            print(f"built fictional settlement study: {args.output} files={len(files)}")
        return 0
    except StudyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
