from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
PROCESSOR_PATH = ROOT / "scripts" / "assets" / "process_sprite.py"
SPEC = importlib.util.spec_from_file_location("truman_sprite_processor", PROCESSOR_PATH)
assert SPEC is not None and SPEC.loader is not None
processor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = processor
SPEC.loader.exec_module(processor)


def test_process_sprite_removes_background_and_aligns_to_baseline(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    output = tmp_path / "sprite.png"
    image = Image.new("RGB", (128, 128), (255, 0, 255))
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((48, 18, 80, 112), fill=(45, 94, 88))
    image.save(source)

    processor.process_sprite(
        source,
        output,
        width=64,
        height=96,
        colors=8,
        padding=4,
        background_tolerance=10,
    )

    with Image.open(output) as result:
        assert result.size == (64, 96)
        assert result.mode == "RGBA"
        assert result.getpixel((0, 0))[3] == 0
        assert result.getchannel("A").getbbox() is not None
        assert result.getchannel("A").getbbox()[3] == 92
        assert (255, 0, 255, 0) not in result.get_flattened_data()


def test_background_removal_preserves_enclosed_matching_color() -> None:
    image = Image.new("RGB", (9, 9), (255, 0, 255))
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((2, 2, 6, 6), fill=(30, 80, 70))
    drawing.point((4, 4), fill=(255, 0, 255))

    result = processor.remove_corner_background(image, tolerance=10)

    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((4, 4)) == (255, 0, 255, 255)
