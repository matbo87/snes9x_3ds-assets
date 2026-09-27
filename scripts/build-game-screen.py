import argparse
import os
import sys
import tempfile
from pathlib import Path

from background_build_common import (
    apply_rgb565_o4x4_dither,
    build_output_filename,
    collect_images,
    compress_png,
    ensure_input_dir,
    handle_compression_failure,
    recompress_lossless,
    run_magick,
    validate_flat_name_collisions,
)

VALID_EXTENSIONS = {".png"}

# Gameplay and title snapshots are expected to be 256x224
# The larger canvas prevents the in-game depth shrink and parallax from exposing an edge.
OUTPUT_WIDTH = 448
OUTPUT_HEIGHT = 256

# Nearest-neighbor scaling preserves hard source edges; Gaussian blur does the softening.
BLUR_SIGMA = 6

# Mosaic size in pixels after downscaling and scaling back without interpolation.
MOSAIC_SIZE = 4

DESATURATE_PERCENT = 100

# Black rectangle covering the centered game screen.
MASK_WIDTH = 212
MASK_HEIGHT = 160

# pngquant images that miss this quality range fall back to lossless compression.
PNGQUANT_QUALITY = "90-100"


def parse_args():
    parser = argparse.ArgumentParser(description="Depth-aware game-screen background builder")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input folder containing source images",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(Path("dist") / "backgrounds" / "game_screen"),
        help="Output folder (default: dist/backgrounds/game_screen)",
    )
    parser.add_argument(
        "--lossless",
        action="store_true",
        help="Skip pngquant; keep full-colour max-zlib PNGs",
    )
    return parser.parse_args()


def apply_background_effect(source_path, destination_path):
    cmd = [
        "magick",
        str(source_path),
        # Fill the background without interpolation, then crop to the canvas.
        "-filter",
        "point",
        "-resize",
        f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}^",
        "-gravity",
        "center",
        "-crop",
        f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}+0+0",
        "+repage",
        "-blur",
        f"0x{BLUR_SIGMA}",
        # Pixelate after blurring.
        "-scale",
        f"{OUTPUT_WIDTH // MOSAIC_SIZE}x{OUTPUT_HEIGHT // MOSAIC_SIZE}!",
        "-scale",
        f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}!",
        "-modulate",
        f"100,{DESATURATE_PERCENT},100",
        # Reserve the centered game-screen area.
        "(",
        "-size",
        f"{MASK_WIDTH}x{MASK_HEIGHT}",
        "xc:black",
        ")",
        "-gravity",
        "center",
        "-composite",
        "-strip",
        str(destination_path),
    ]
    return run_magick(cmd) is not None


def main():
    args = parse_args()

    input_path = Path(os.path.normpath(args.input))
    output_dir = Path(os.path.normpath(args.output))
    failed_dir = output_dir / "_pngquant_failed"
    ensure_input_dir(input_path)

    files = collect_images(input_path, VALID_EXTENSIONS)
    collisions = validate_flat_name_collisions(files)
    if collisions:
        print("[Error] Flat output would overwrite files due to duplicate names:")
        for first, second in collisions:
            print(f"  - {first} <-> {second}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    print(f"Input:  {input_path}")
    print(f"Output: {output_dir}")
    print(
        "Effect: "
        f"NN-upscale+crop={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}, blur=0x{BLUR_SIGMA}, mosaic={MOSAIC_SIZE}px, "
        f"desaturate={DESATURATE_PERCENT}%, mask={MASK_WIDTH}x{MASK_HEIGHT}, dither=o4x4"
    )
    print(f"Processing {len(files)} image(s)...\n")

    processed = 0
    failed = 0
    total = len(files)
    for index, source_path in enumerate(files, start=1):
        print(f"[{index}/{total}] {source_path.name}")

        destination_path = output_dir / build_output_filename(source_path)
        with tempfile.NamedTemporaryFile(prefix="bg_depth_", suffix=".png", delete=False) as effect_tmp:
            effect_path = Path(effect_tmp.name)

        try:
            if not apply_background_effect(source_path, effect_path):
                print(f"  [Skip] Effect stage failed: {source_path.name}")
                continue
            if not apply_rgb565_o4x4_dither(effect_path, destination_path):
                print(f"  [Skip] Dither stage failed: {source_path.name}")
                continue

            if args.lossless:
                recompress_lossless(destination_path)
            elif compress_png(destination_path, source_path.name, quality_steps=[PNGQUANT_QUALITY]) == "failed":
                if recompress_lossless(destination_path):
                    print(f"  [Lossless] pngquant missed {PNGQUANT_QUALITY}, kept lossless")
                else:
                    failed += 1
                    handle_compression_failure(
                        destination_path=destination_path,
                        working_path=effect_path,
                        failed_dir=failed_dir,
                        source_name=source_path.name,
                        suffix_label="effect",
                    )
                    continue

            processed += 1
        finally:
            if effect_path.exists():
                effect_path.unlink()

    print(f"\n[Done] Processed {processed}/{total} background(s) to {output_dir}")
    if failed:
        print(f"[Done] Moved {failed} compression-failed background(s) to {failed_dir}")
    elif not any(failed_dir.iterdir()):
        failed_dir.rmdir()


if __name__ == "__main__":
    main()
