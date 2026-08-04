#!/usr/bin/env python3
"""Convert an MMX source image into a deterministic pixel-art sprite image."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


def remove_corner_background(image: Image.Image, tolerance: int) -> Image.Image:
    """Remove only background-colored pixels connected to the image boundary."""
    rgba = image.convert("RGBA")
    corners = [
        rgba.getpixel((0, 0)),
        rgba.getpixel((rgba.width - 1, 0)),
        rgba.getpixel((0, rgba.height - 1)),
        rgba.getpixel((rgba.width - 1, rgba.height - 1)),
    ]
    background = tuple(sum(pixel[channel] for pixel in corners) // 4 for channel in range(3))
    source = list(rgba.get_flattened_data())
    background_mask = bytearray(rgba.width * rgba.height)
    pending: deque[int] = deque()

    def enqueue_if_background(x: int, y: int) -> None:
        index = y * rgba.width + x
        if background_mask[index]:
            return
        pixel = source[index]
        distance = max(abs(pixel[channel] - background[channel]) for channel in range(3))
        if distance <= tolerance:
            background_mask[index] = 1
            pending.append(index)

    for x in range(rgba.width):
        enqueue_if_background(x, 0)
        enqueue_if_background(x, rgba.height - 1)
    for y in range(1, rgba.height - 1):
        enqueue_if_background(0, y)
        enqueue_if_background(rgba.width - 1, y)

    while pending:
        index = pending.popleft()
        x = index % rgba.width
        y = index // rgba.width
        if x:
            enqueue_if_background(x - 1, y)
        if x + 1 < rgba.width:
            enqueue_if_background(x + 1, y)
        if y:
            enqueue_if_background(x, y - 1)
        if y + 1 < rgba.height:
            enqueue_if_background(x, y + 1)

    output = Image.new("RGBA", rgba.size)
    output.putdata(
        [
            (*pixel[:3], 0 if background_mask[index] else pixel[3])
            for index, pixel in enumerate(source)
        ]
    )
    return output


def crop_visible(image: Image.Image) -> Image.Image:
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("image has no visible pixels after background removal")
    return image.crop(bounds)


def fit_sprite(image: Image.Image, width: int, height: int, padding: int) -> Image.Image:
    available_width = width - padding * 2
    available_height = height - padding * 2
    if available_width <= 0 or available_height <= 0:
        raise ValueError("padding leaves no room for the sprite")
    scale = min(available_width / image.width, available_height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    # BOX avoids the colored ringing that Lanczos creates around chroma-keyed silhouettes.
    resized = image.resize(size, Image.Resampling.BOX)
    canvas = Image.new("RGBA", (width, height))
    x = (width - resized.width) // 2
    y = height - padding - resized.height
    canvas.alpha_composite(resized, (x, y))
    return canvas


def quantize_sprite(image: Image.Image, colors: int) -> Image.Image:
    alpha = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    opaque_colors = [pixel[:3] for pixel in image.get_flattened_data() if pixel[3] >= 128]
    if not opaque_colors:
        raise ValueError("image has no opaque pixels to quantize")
    palette_source = Image.new("RGB", (len(opaque_colors), 1))
    palette_source.putdata(opaque_colors)
    palette = palette_source.quantize(
        colors=max(2, colors),
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    quantized = (
        image.convert("RGB")
        .quantize(
            palette=palette,
            dither=Image.Dither.NONE,
        )
        .convert("RGBA")
    )
    quantized.putalpha(alpha)
    return bleed_transparent_rgb(quantized)


def bleed_transparent_rgb(image: Image.Image, iterations: int = 4) -> Image.Image:
    """Extend edge colors under transparency to prevent filtering halos in Godot."""
    width, height = image.size
    pixels = list(image.get_flattened_data())
    colors = [pixel[:3] if pixel[3] else (0, 0, 0) for pixel in pixels]
    populated = [pixel[3] > 0 for pixel in pixels]

    for _ in range(iterations):
        next_colors = list(colors)
        next_populated = list(populated)
        changed = False
        for index, is_populated in enumerate(populated):
            if is_populated:
                continue
            x = index % width
            y = index // width
            neighbors: list[tuple[int, int, int]] = []
            for neighbor_x, neighbor_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= neighbor_x < width and 0 <= neighbor_y < height:
                    neighbor = neighbor_y * width + neighbor_x
                    if populated[neighbor]:
                        neighbors.append(colors[neighbor])
            if neighbors:
                next_colors[index] = tuple(
                    sum(color[channel] for color in neighbors) // len(neighbors)
                    for channel in range(3)
                )
                next_populated[index] = True
                changed = True
        colors = next_colors
        populated = next_populated
        if not changed:
            break

    output = Image.new("RGBA", image.size)
    output.putdata([(*colors[index], pixel[3]) for index, pixel in enumerate(pixels)])
    return output


def process_sprite(
    source: Path,
    output: Path,
    *,
    width: int,
    height: int,
    colors: int,
    padding: int,
    background_tolerance: int,
) -> None:
    with Image.open(source) as opened:
        foreground = crop_visible(remove_corner_background(opened, background_tolerance))
    sprite = fit_sprite(foreground, width, height, padding)
    sprite = quantize_sprite(sprite, colors)
    output.parent.mkdir(parents=True, exist_ok=True)
    sprite.save(output, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=96)
    parser.add_argument("--colors", type=int, default=24)
    parser.add_argument("--padding", type=int, default=4)
    parser.add_argument("--background-tolerance", type=int, default=44)
    args = parser.parse_args()
    process_sprite(
        args.source,
        args.output,
        width=args.width,
        height=args.height,
        colors=args.colors,
        padding=args.padding,
        background_tolerance=args.background_tolerance,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
