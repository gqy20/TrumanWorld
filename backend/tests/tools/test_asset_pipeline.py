from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PIPELINE_PATH = ROOT / "scripts" / "assets" / "pipeline.py"
SPEC = importlib.util.spec_from_file_location("truman_asset_pipeline", PIPELINE_PATH)
assert SPEC is not None and SPEC.loader is not None
pipeline = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pipeline
SPEC.loader.exec_module(pipeline)


def test_checked_in_asset_pipeline_resolves_deterministically() -> None:
    first = pipeline.resolve_jobs()
    second = pipeline.resolve_jobs()

    assert len(first) == 6
    assert [job.public_dict() for job in first] == [job.public_dict() for job in second]
    assert first[0].id == "mei_identity_reference"
    assert first[0].prompt_sha256.startswith("sha256:")
    assert "Mei" in first[0].prompt
    assert "Avoid:" in first[0].prompt
    assert first[0].subject_reference is None
    assert first[0].output_directory.name == "characters"


def test_mmx_command_is_non_interactive_and_deterministic() -> None:
    job = pipeline.resolve_jobs()[1]

    command = pipeline.build_mmx_command(job, dry_run=True)
    third_command = pipeline.build_mmx_command(job, dry_run=True, candidate_index=2)

    assert command[:3] == ["mmx", "image", "generate"]
    assert "--non-interactive" in command
    assert "--quiet" in command
    assert "--output" in command
    assert "--dry-run" in command
    assert command[command.index("--n") + 1] == "1"
    assert command[command.index("--seed") + 1] == "12031"
    assert third_command[third_command.index("--seed") + 1] == "12033"
    assert third_command[third_command.index("--out-prefix") + 1].endswith("candidate_03")
    assert not any("sk-" in argument for argument in command)


def test_checked_in_jobs_generate_three_independent_candidates() -> None:
    job = pipeline.resolve_jobs()[1]

    assert job.count == 3
    assert job.max_parallel == 3
    assert job.public_dict()["candidate_seeds"] == [12031, 12032, 12033]
    assert job.background.requested_rgb == (255, 0, 255)
    assert "RGB(255, 0, 255)" in job.prompt
    assert "#FF00FF" in job.prompt


def test_background_analysis_reports_detected_color_and_rejects_gradient(
    tmp_path: Path,
) -> None:
    contract = pipeline.BackgroundContract(
        id="test",
        requested_rgb=(255, 0, 255),
        sample_border_pixels=2,
        color_tolerance=10,
        uniformity_tolerance=5,
    )
    solid_path = tmp_path / "solid.png"
    Image.new("RGB", (16, 16), (254, 1, 253)).save(solid_path)

    solid = pipeline.analyze_background(solid_path, contract)

    assert solid["status"] == "pass"
    assert solid["detected_rgb"] == [254, 1, 253]
    assert solid["detected_hex"] == "#FE01FD"

    gradient_path = tmp_path / "gradient.png"
    gradient = Image.new("RGB", (16, 16))
    gradient.putdata([(255, min(255, x * 16), 255) for _y in range(16) for x in range(16)])
    gradient.save(gradient_path)

    rejected = pipeline.analyze_background(gradient_path, contract)

    assert rejected["status"] == "reject"
    assert rejected["uniform"] is False


def test_pipeline_rejects_template_with_missing_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "REPOSITORY_ROOT", tmp_path)
    style = tmp_path / "style.yml"
    characters = tmp_path / "characters.yml"
    style.write_text(
        """schema_version: 1
base_prompt: base
negative_prompt: avoid
templates:
  broken: "{identity} {missing}"
""",
        encoding="utf-8",
    )
    characters.write_text(
        """schema_version: 1
characters:
  mei:
    identity: Mei
""",
        encoding="utf-8",
    )
    config = tmp_path / "pipeline.yml"
    config.write_text(
        """schema_version: 1
toolchain:
  blender:
    required_major: 5
    required_minor: 2
    distribution: official_release
  mmx:
    minimum_cli_version: 1.0.16
    image_model: image-01
defaults:
  width: 512
  height: 512
  count: 1
  output_directory: output
  receipt_directory: receipts
prompt_sources:
  style: style.yml
  characters: characters.yml
jobs:
  - id: broken_job
    kind: character_sprite
    character: mei
    template: broken
    seed: 1
""",
        encoding="utf-8",
    )

    with pytest.raises(pipeline.AssetConfigurationError, match="missing template variable"):
        pipeline.resolve_jobs(config)


def test_execute_job_reports_generator_error_without_dumping_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = pipeline.resolve_jobs()[0]
    job = pipeline.ResolvedJob(
        **{
            **source.__dict__,
            "output_directory": tmp_path / "raw",
            "receipt_directory": tmp_path / "receipts",
        }
    )
    monkeypatch.setattr(pipeline, "require_mmx_cli", lambda version: None)
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="service unavailable"
        ),
    )

    with pytest.raises(pipeline.AssetExecutionError, match="service unavailable") as raised:
        pipeline.execute_job(job, dry_run=False)

    assert "--prompt" not in str(raised.value)
    receipt = json.loads((tmp_path / "receipts" / f"{job.id}.generated.json").read_text())
    assert len(receipt["generation"]["candidates"]) == 3
    assert all(
        candidate["status"] == "failed"
        and candidate["attempts"] == 2
        and len(candidate["errors"]) == 2
        for candidate in receipt["generation"]["candidates"]
    )


def test_candidate_retries_a_transient_generator_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = pipeline.resolve_jobs()[0]
    job = pipeline.ResolvedJob(
        **{
            **source.__dict__,
            "count": 1,
            "output_directory": tmp_path / "raw",
            "receipt_directory": tmp_path / "receipts",
        }
    )
    job.output_directory.mkdir()
    outcomes = iter(
        [
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="temporary EOF"),
            subprocess.CompletedProcess(args=[], returncode=0, stdout='{"saved": []}', stderr=""),
        ]
    )
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: next(outcomes))

    candidate = pipeline._execute_candidate(job, 0, dry_run=True)

    assert candidate["status"] == "succeeded"
    assert candidate["attempts"] == 2
    assert candidate["errors"] == [{"attempt": 1, "exit_code": 1, "detail": "temporary EOF"}]


def test_require_mmx_cli_rejects_outdated_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="mmx 1.0.15\n", stderr=""
        ),
    )

    with pytest.raises(pipeline.AssetExecutionError, match=r"1\.0\.16 or newer"):
        pipeline.require_mmx_cli("1.0.16")


def test_sanitize_generator_result_fingerprints_embedded_images() -> None:
    value = {"request": {"subject_reference": [{"image_file": "data:image/png;base64,AAAA"}]}}

    sanitized = pipeline.sanitize_generator_result(value)

    image_file = sanitized["request"]["subject_reference"][0]["image_file"]
    assert image_file.startswith("<redacted:data-image;characters=26;sha256=")
    assert "AAAA" not in image_file
