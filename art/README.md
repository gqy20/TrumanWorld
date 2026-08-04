# Truman World Art Sources

This directory contains editable art inputs and deterministic generation configuration.

- `prompts/` is the single source of truth for MMX image prompts.
- `pipeline.yml` declares reproducible generation jobs and tool versions.
- `svg_pose_sets.yml` defines reusable deterministic character pose geometry.
- `../scenarios/*/visuals.yml` selects a visual style and pose set for each scenario.
- `../scenarios/*/agents/*/appearance.yml` owns scenario-specific character appearance.
- `generated/` is local scratch output and is not committed.
- Curated runtime assets belong under `godot/world-client/assets/`.

Do not place API keys in prompt files or generation receipts.
