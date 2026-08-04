#!/usr/bin/env python3
"""Validate, plan and execute Truman World media generation jobs."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPOSITORY_ROOT / "art" / "pipeline.yml"
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SEMANTIC_VERSION_PATTERN = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)")
MMX_MINIMUM_DIMENSION = 512
MMX_MAXIMUM_DIMENSION = 2048
MMX_MAXIMUM_PROMPT_LENGTH = 1499


class AssetConfigurationError(ValueError):
    """Raised when the checked-in asset configuration is invalid."""


class AssetExecutionError(RuntimeError):
    """Raised when an external asset generator fails."""


@dataclass(frozen=True)
class BackgroundContract:
    id: str
    requested_rgb: tuple[int, int, int]
    sample_border_pixels: int
    color_tolerance: float
    uniformity_tolerance: float

    @property
    def hex_color(self) -> str:
        return "#" + "".join(f"{channel:02X}" for channel in self.requested_rgb)

    @property
    def prompt(self) -> str:
        red, green, blue = self.requested_rgb
        return (
            f"The entire background must be one perfectly uniform flat solid color: "
            f"RGB({red}, {green}, {blue}), HEX {self.hex_color}, edge to edge. Every background "
            "pixel must have the same color. No gradient, texture, vignette, lighting change, "
            "cast shadow, contact shadow, floor line, glow, dust, text, dividers or watermark."
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "requested_rgb": list(self.requested_rgb),
            "requested_hex": self.hex_color,
            "sample_border_pixels": self.sample_border_pixels,
            "color_tolerance": self.color_tolerance,
            "uniformity_tolerance": self.uniformity_tolerance,
        }


@dataclass(frozen=True)
class ResolvedJob:
    id: str
    kind: str
    prompt: str
    prompt_sha256: str
    seed: int
    width: int
    height: int
    count: int
    seed_stride: int
    max_parallel: int
    retry_attempts: int
    output_directory: Path
    receipt_directory: Path
    subject_reference: str | None
    background: BackgroundContract | None
    minimum_mmx_version: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "count": self.count,
            "candidate_strategy": "independent_parallel",
            "candidate_seeds": [
                self.seed + index * self.seed_stride for index in range(self.count)
            ],
            "max_parallel": self.max_parallel,
            "retry_attempts": self.retry_attempts,
            "output_directory": str(self.output_directory),
            "receipt_directory": str(self.receipt_directory),
            "subject_reference": self.subject_reference,
            "background": self.background.public_dict() if self.background else None,
            "minimum_mmx_version": self.minimum_mmx_version,
        }


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssetConfigurationError(f"missing configuration file: {path}")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise AssetConfigurationError(f"expected a YAML object: {path}")
    return parsed


def repository_path(value: str) -> Path:
    candidate = (REPOSITORY_ROOT / value).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT):
        raise AssetConfigurationError(f"path escapes repository: {value}")
    return candidate


def resolve_jobs(config_path: Path = DEFAULT_CONFIG) -> list[ResolvedJob]:
    config = load_yaml(config_path)
    _require_schema(config, config_path)
    minimum_mmx_version = _validate_toolchain(config)
    sources = _require_mapping(config, "prompt_sources")
    style_path = repository_path(_require_string(sources, "style"))
    characters_path = repository_path(_require_string(sources, "characters"))
    style = load_yaml(style_path)
    characters_config = load_yaml(characters_path)
    _require_schema(style, style_path)
    _require_schema(characters_config, characters_path)

    defaults = _require_mapping(config, "defaults")
    width = _mmx_dimension(defaults.get("width"), "defaults.width")
    height = _mmx_dimension(defaults.get("height"), "defaults.height")
    count = _positive_int(defaults.get("count"), "defaults.count")
    seed_stride = _positive_int(defaults.get("seed_stride", 1), "defaults.seed_stride")
    max_parallel = _positive_int(
        defaults.get("max_parallel", 3), "defaults.max_parallel"
    )
    retry_attempts = _positive_int(
        defaults.get("retry_attempts", 2), "defaults.retry_attempts"
    )
    _optional_bool(defaults, "prompt_optimizer", default=False)
    _optional_bool(defaults, "aigc_watermark", default=False)
    templates = _require_mapping(style, "templates")
    characters = _require_mapping(characters_config, "characters")
    base_prompt = _require_string(style, "base_prompt").strip()
    negative_prompt = _require_string(style, "negative_prompt").strip()
    backgrounds = _resolve_backgrounds(config)
    raw_jobs = config.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise AssetConfigurationError("pipeline jobs must be a non-empty list")

    resolved: list[ResolvedJob] = []
    seen_ids: set[str] = set()
    for index, raw_job in enumerate(raw_jobs):
        if not isinstance(raw_job, dict):
            raise AssetConfigurationError(f"job {index} must be an object")
        job_id = _require_string(raw_job, "id")
        if not SAFE_ID_PATTERN.fullmatch(job_id):
            raise AssetConfigurationError(f"invalid job id: {job_id}")
        if job_id in seen_ids:
            raise AssetConfigurationError(f"duplicate job id: {job_id}")
        seen_ids.add(job_id)

        template_id = _require_string(raw_job, "template")
        template = templates.get(template_id)
        if not isinstance(template, str) or not template.strip():
            raise AssetConfigurationError(
                f"job {job_id} has unknown template: {template_id}"
            )
        variables = dict(_optional_mapping(raw_job, "variables"))
        background_id = _optional_string(raw_job, "background")
        background = backgrounds.get(background_id) if background_id else None
        if background_id and background is None:
            raise AssetConfigurationError(
                f"job {job_id} has unknown background contract: {background_id}"
            )
        if background is not None:
            variables["background_contract"] = background.prompt
        subject_reference: str | None = None
        character_id = raw_job.get("character")
        if character_id is not None:
            if not isinstance(character_id, str) or character_id not in characters:
                raise AssetConfigurationError(
                    f"job {job_id} has unknown character: {character_id}"
                )
            character = characters[character_id]
            if not isinstance(character, dict):
                raise AssetConfigurationError(
                    f"character {character_id} must be an object"
                )
            variables["identity"] = _require_string(character, "identity").strip()
            raw_reference = character.get("subject_reference")
            use_subject_reference = raw_job.get("use_subject_reference", True)
            if not isinstance(use_subject_reference, bool):
                raise AssetConfigurationError(
                    f"job {job_id} use_subject_reference must be a boolean"
                )
            if use_subject_reference and raw_reference is not None:
                if not isinstance(raw_reference, str) or not raw_reference.strip():
                    raise AssetConfigurationError(
                        f"character {character_id} has invalid subject_reference"
                    )
                subject_reference = str(repository_path(raw_reference))

        try:
            task_prompt = template.format_map(variables)
        except KeyError as exc:
            raise AssetConfigurationError(
                f"job {job_id} is missing template variable: {exc.args[0]}"
            ) from exc
        prompt = "\n\n".join(
            (base_prompt, task_prompt.strip(), f"Avoid: {negative_prompt}")
        )
        if len(prompt) > MMX_MAXIMUM_PROMPT_LENGTH:
            raise AssetConfigurationError(
                f"job {job_id} prompt has {len(prompt)} characters; "
                f"MMX allows at most {MMX_MAXIMUM_PROMPT_LENGTH}"
            )
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        resolved.append(
            ResolvedJob(
                id=job_id,
                kind=_require_string(raw_job, "kind"),
                prompt=prompt,
                prompt_sha256=f"sha256:{prompt_hash}",
                seed=_positive_int(raw_job.get("seed"), f"job {job_id} seed"),
                width=width,
                height=height,
                count=count,
                seed_stride=seed_stride,
                max_parallel=max_parallel,
                retry_attempts=retry_attempts,
                output_directory=repository_path(
                    _optional_string(raw_job, "output_directory")
                    or _require_string(defaults, "output_directory")
                ),
                receipt_directory=repository_path(
                    _require_string(defaults, "receipt_directory")
                ),
                subject_reference=subject_reference,
                background=background,
                minimum_mmx_version=minimum_mmx_version,
            )
        )
        if subject_reference and not Path(subject_reference).is_file():
            raise AssetConfigurationError(
                f"job {job_id} subject_reference does not exist: {subject_reference}"
            )
    return resolved


def build_mmx_command(
    job: ResolvedJob, *, dry_run: bool, candidate_index: int = 0
) -> list[str]:
    if not 0 <= candidate_index < job.count:
        raise AssetConfigurationError(
            f"candidate index out of range: {candidate_index}"
        )
    candidate_number = candidate_index + 1
    command = [
        "mmx",
        "image",
        "generate",
        "--prompt",
        job.prompt,
        "--width",
        str(job.width),
        "--height",
        str(job.height),
        "--n",
        "1",
        "--seed",
        str(job.seed + candidate_index * job.seed_stride),
        "--out-dir",
        str(job.output_directory),
        "--out-prefix",
        f"{job.id}_candidate_{candidate_number:02d}",
        "--non-interactive",
        "--quiet",
        "--output",
        "json",
    ]
    if job.subject_reference:
        command.extend(
            ("--subject-ref", f"type=character,image={job.subject_reference}")
        )
    if dry_run:
        command.append("--dry-run")
    return command


def execute_job(job: ResolvedJob, *, dry_run: bool) -> dict[str, Any]:
    require_mmx_cli(job.minimum_mmx_version)
    job.output_directory.mkdir(parents=True, exist_ok=True)
    job.receipt_directory.mkdir(parents=True, exist_ok=True)
    worker_count = min(job.count, job.max_parallel)
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(_execute_candidate, job, index, dry_run=dry_run)
            for index in range(job.count)
        ]
        candidates = [future.result() for future in futures]
    receipt = {
        "schema_version": 2,
        "dry_run": dry_run,
        "job": job.public_dict(),
        "generation": {
            "strategy": "independent_parallel",
            "worker_count": worker_count,
            "candidates": candidates,
        },
    }
    receipt_suffix = "dry-run" if dry_run else "generated"
    receipt_path = job.receipt_directory / f"{job.id}.{receipt_suffix}.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    failed = [candidate for candidate in candidates if candidate["status"] == "failed"]
    if failed:
        failed_numbers = ", ".join(str(candidate["index"]) for candidate in failed)
        last_error = failed[0]["errors"][-1]["detail"]
        raise AssetExecutionError(
            f"MMX job {job.id} failed after retries for candidate(s) {failed_numbers}; "
            f"last error: {last_error}; receipt: {receipt_path}"
        )
    return {"receipt": str(receipt_path), "candidates": candidates}


def _execute_candidate(
    job: ResolvedJob, candidate_index: int, *, dry_run: bool
) -> dict[str, Any]:
    candidate_number = candidate_index + 1
    prefix = f"{job.id}_candidate_{candidate_number:02d}"
    before = _matching_images(job.output_directory, prefix)
    command = build_mmx_command(job, dry_run=dry_run, candidate_index=candidate_index)
    errors: list[dict[str, Any]] = []
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, job.retry_attempts + 1):
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if not completed.returncode:
            break
        detail = (
            completed.stderr.strip() or completed.stdout.strip() or "no error details"
        )
        errors.append(
            {
                "attempt": attempt,
                "exit_code": completed.returncode,
                "detail": sanitize_generator_result(detail),
            }
        )
    assert completed is not None
    if completed.returncode:
        return {
            "index": candidate_number,
            "seed": job.seed + candidate_index * job.seed_stride,
            "output_prefix": prefix,
            "status": "failed",
            "attempts": job.retry_attempts,
            "files": [],
            "background_qa": [],
            "errors": errors,
        }
    raw_output = completed.stdout.strip()
    try:
        result: Any = json.loads(raw_output)
    except json.JSONDecodeError:
        result = {"stdout": raw_output.splitlines()}

    files = [] if dry_run else _changed_images(job.output_directory, prefix, before)
    background_qa = [analyze_background(path, job.background) for path in files]
    return {
        "index": candidate_number,
        "seed": job.seed + candidate_index * job.seed_stride,
        "output_prefix": prefix,
        "status": "succeeded",
        "attempts": len(errors) + 1,
        "files": [str(path) for path in files],
        "background_qa": background_qa,
        "errors": errors,
        "result": sanitize_generator_result(result),
    }


def _matching_images(directory: Path, prefix: str) -> dict[Path, tuple[int, int]]:
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    return {
        path: (path.stat().st_mtime_ns, path.stat().st_size)
        for path in directory.glob(f"{prefix}*")
        if path.is_file() and path.suffix.lower() in extensions
    }


def _changed_images(
    directory: Path, prefix: str, before: dict[Path, tuple[int, int]]
) -> list[Path]:
    after = _matching_images(directory, prefix)
    return sorted(
        path for path, fingerprint in after.items() if before.get(path) != fingerprint
    )


def analyze_background(
    path: Path, contract: BackgroundContract | None
) -> dict[str, Any]:
    if contract is None:
        return {"status": "not_required"}
    with Image.open(path) as source:
        image = source.convert("RGB")
    width, height = image.size
    border = min(contract.sample_border_pixels, max(1, min(width, height) // 4))
    pixels = image.load()
    samples = [
        pixels[x, y]
        for y in range(height)
        for x in range(width)
        if x < border or x >= width - border or y < border or y >= height - border
    ]
    detected = tuple(
        round(statistics.median(pixel[channel] for pixel in samples))
        for channel in range(3)
    )
    deviations = sorted(_color_distance(pixel, detected) for pixel in samples)
    percentile_index = min(len(deviations) - 1, math.ceil(len(deviations) * 0.95) - 1)
    uniformity_p95 = round(deviations[percentile_index], 2)
    requested_distance = round(_color_distance(detected, contract.requested_rgb), 2)
    color_matches = requested_distance <= contract.color_tolerance
    uniform = uniformity_p95 <= contract.uniformity_tolerance
    return {
        "status": "pass" if color_matches and uniform else "reject",
        "requested_rgb": list(contract.requested_rgb),
        "requested_hex": contract.hex_color,
        "detected_rgb": list(detected),
        "detected_hex": "#" + "".join(f"{channel:02X}" for channel in detected),
        "requested_distance": requested_distance,
        "border_uniformity_p95": uniformity_p95,
        "color_matches": color_matches,
        "uniform": uniform,
        "sample_border_pixels": border,
    }


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def sanitize_generator_result(value: Any) -> Any:
    """Remove embedded media from generator output while retaining an auditable fingerprint."""
    if isinstance(value, dict):
        return {key: sanitize_generator_result(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_generator_result(item) for item in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"<redacted:data-image;characters={len(value)};sha256={digest}>"
    return value


def _require_schema(value: dict[str, Any], path: Path) -> None:
    if value.get("schema_version") != 1:
        raise AssetConfigurationError(f"unsupported schema_version in {path}")


def _validate_toolchain(config: dict[str, Any]) -> str:
    toolchain = _require_mapping(config, "toolchain")
    blender = _require_mapping(toolchain, "blender")
    mmx = _require_mapping(toolchain, "mmx")
    if blender.get("required_major") != 5 or blender.get("required_minor") != 2:
        raise AssetConfigurationError("toolchain.blender must require Blender 5.2.x")
    if blender.get("distribution") != "official_release":
        raise AssetConfigurationError("toolchain.blender must use an official release")
    minimum_mmx_version = _require_string(mmx, "minimum_cli_version")
    _semantic_version(minimum_mmx_version, "toolchain.mmx.minimum_cli_version")
    if mmx.get("image_model") != "image-01":
        raise AssetConfigurationError("toolchain.mmx.image_model must be image-01")
    return minimum_mmx_version


def _resolve_backgrounds(config: dict[str, Any]) -> dict[str, BackgroundContract]:
    raw_backgrounds = _optional_mapping(config, "backgrounds")
    resolved: dict[str, BackgroundContract] = {}
    for background_id, raw_contract in raw_backgrounds.items():
        if not isinstance(background_id, str) or not SAFE_ID_PATTERN.fullmatch(
            background_id
        ):
            raise AssetConfigurationError(
                f"invalid background contract id: {background_id}"
            )
        if not isinstance(raw_contract, dict):
            raise AssetConfigurationError(
                f"background contract {background_id} must be an object"
            )
        raw_rgb = raw_contract.get("requested_rgb")
        if (
            not isinstance(raw_rgb, list)
            or len(raw_rgb) != 3
            or any(
                not isinstance(channel, int)
                or isinstance(channel, bool)
                or not 0 <= channel <= 255
                for channel in raw_rgb
            )
        ):
            raise AssetConfigurationError(
                f"background contract {background_id} requested_rgb must contain three bytes"
            )
        resolved[background_id] = BackgroundContract(
            id=background_id,
            requested_rgb=(raw_rgb[0], raw_rgb[1], raw_rgb[2]),
            sample_border_pixels=_positive_int(
                raw_contract.get("sample_border_pixels"),
                f"background contract {background_id} sample_border_pixels",
            ),
            color_tolerance=_positive_number(
                raw_contract.get("color_tolerance"),
                f"background contract {background_id} color_tolerance",
            ),
            uniformity_tolerance=_positive_number(
                raw_contract.get("uniformity_tolerance"),
                f"background contract {background_id} uniformity_tolerance",
            ),
        )
    return resolved


def require_mmx_cli(minimum_version: str) -> None:
    try:
        completed = subprocess.run(
            ["mmx", "--version"], check=False, capture_output=True, text=True
        )
    except OSError as exc:
        raise AssetExecutionError(f"MMX CLI is not available: {exc}") from exc
    if completed.returncode:
        detail = completed.stderr.strip() or "version command failed"
        raise AssetExecutionError(f"MMX CLI is not usable: {detail}")
    installed = _semantic_version(completed.stdout.strip(), "installed MMX CLI version")
    required = _semantic_version(minimum_version, "required MMX CLI version")
    if installed < required:
        raise AssetExecutionError(
            f"MMX CLI {minimum_version} or newer is required; got {completed.stdout.strip()}"
        )


def _require_mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise AssetConfigurationError(f"{key} must be an object")
    return result


def _optional_mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key, {})
    if not isinstance(result, dict):
        raise AssetConfigurationError(f"{key} must be an object")
    return result


def _require_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise AssetConfigurationError(f"{key} must be a non-empty string")
    return result


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    result = value.get(key)
    if result is None:
        return None
    if not isinstance(result, str) or not result.strip():
        raise AssetConfigurationError(f"{key} must be a non-empty string")
    return result


def _optional_bool(value: dict[str, Any], key: str, *, default: bool) -> bool:
    result = value.get(key, default)
    if not isinstance(result, bool):
        raise AssetConfigurationError(f"{key} must be a boolean")
    return result


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AssetConfigurationError(f"{label} must be a positive integer")
    return value


def _positive_number(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise AssetConfigurationError(f"{label} must be a positive number")
    return float(value)


def _mmx_dimension(value: Any, label: str) -> int:
    dimension = _positive_int(value, label)
    if not MMX_MINIMUM_DIMENSION <= dimension <= MMX_MAXIMUM_DIMENSION:
        raise AssetConfigurationError(
            f"{label} must be between {MMX_MINIMUM_DIMENSION} and {MMX_MAXIMUM_DIMENSION}"
        )
    if dimension % 8:
        raise AssetConfigurationError(f"{label} must be a multiple of 8")
    return dimension


def _semantic_version(value: str, label: str) -> tuple[int, int, int]:
    match = SEMANTIC_VERSION_PATTERN.search(value)
    if match is None:
        raise AssetConfigurationError(f"{label} must contain a semantic version")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate all pipeline and prompt files")
    plan = subparsers.add_parser(
        "plan", help="print fully resolved prompts without generation"
    )
    plan.add_argument("--job")
    generate = subparsers.add_parser(
        "generate", help="execute an MMX image generation job"
    )
    generate.add_argument("--job", required=True)
    generate.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        jobs = resolve_jobs(args.config.resolve())
        if args.command == "validate":
            print(json.dumps({"ok": True, "jobs": len(jobs)}, ensure_ascii=False))
            return 0
        selected = [job for job in jobs if not args.job or job.id == args.job]
        if not selected:
            raise AssetConfigurationError(f"unknown job: {args.job}")
        if args.command == "plan":
            print(
                json.dumps(
                    [job.public_dict() for job in selected],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        result = execute_job(selected[0], dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (AssetConfigurationError, AssetExecutionError) as exc:
        print(f"asset pipeline error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
