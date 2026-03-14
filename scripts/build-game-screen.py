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
    run_magick,
    validate_flat_name_collisions,
)

VALID_EXTENSIONS = {".png"}
BLUR_RADIUS = "0x4"
DESATURATE_PERCENT = "70"
OUTPUT_WIDTH = 400
OUTPUT_HEIGHT = 240

MASK_WIDTH = 240
MASK_HEIGHT = 208

def parse_args():
    parser = argparse.ArgumentParser(description="Background Builder")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input folder containing source images",
    )
    return parser.parse_args()

def apply_background_effect(source_path, destination_path):
    cmd = [
        "magick",
        str(source_path),
        "-resize",
        f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}^",
        "-gravity",
        "center",
        "-crop",
        f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}+0+0",
        "+repage",
        "-blur",
        BLUR_RADIUS,
        "-modulate",
        f"100,{DESATURATE_PERCENT},100",
    ]
    cmd.extend(
        [
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
    )
    return run_magick(cmd) is not None


def main():
    args = parse_args()

    clean_input_path = Path(os.path.normpath(args.input))
    output_dir = Path("dist") / "backgrounds" / "game_screen"
    failed_dir = output_dir / "_pngquant_failed"

    ensure_input_dir(clean_input_path)

    files = collect_images(clean_input_path, VALID_EXTENSIONS)
    collisions = validate_flat_name_collisions(files)

    if collisions:
        print("[Error] Flat output would overwrite files due to duplicate names:")
        for first, second in collisions:
            print(f"  - {first} <-> {second}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output folder: {output_dir}")
    print(f"Compression failures folder: {failed_dir}")
    print(
        "Effect: "
        f"scale+crop={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}, blur={BLUR_RADIUS}, "
        f"desaturate={DESATURATE_PERCENT}%, "
        f"center mask={MASK_WIDTH}x{MASK_HEIGHT}, dither=o4x4"
    )
    print(f"Starting processing for '{clean_input_path.name}' ({len(files)} images) as 'game_screen'...")

    processed = 0
    failed = 0
    total = len(files)
    for index, source_path in enumerate(files, start=1):
        print(f"[{index}/{total}] {source_path.name}")
        destination_path = output_dir / build_output_filename(source_path)
        with tempfile.NamedTemporaryFile(prefix="bg_game_", suffix=".png", delete=False) as effect_tmp:
            effect_path = Path(effect_tmp.name)

        try:
            if not apply_background_effect(source_path, effect_path):
                print(f"  [Skip] Effect stage failed: {source_path.name}")
                continue

            if not apply_rgb565_o4x4_dither(effect_path, destination_path):
                print(f"  [Skip] Dither stage failed: {source_path.name}")
                continue

            compression_result = compress_png(
                destination_path,
                source_path.name,
                quality_steps=["80-100", "50-79"],
            )
            if compression_result == "failed":
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

    print(f"[Done] Processed {processed} background(s) to {output_dir}")
    if failed:
        print(f"[Done] Moved {failed} compression-failed background(s) to {failed_dir}")
    elif not any(failed_dir.iterdir()):
        failed_dir.rmdir()
        print(f"[Done] Removed empty failures folder: {failed_dir}")


if __name__ == "__main__":
    main()
