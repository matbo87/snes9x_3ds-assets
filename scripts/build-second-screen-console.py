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

# Sources are pre-composited console-and-cartridge images in a 5:3 aspect ratio.
BACKGROUND_W, BACKGROUND_H = 400, 240
DEFAULT_OUTPUT_ROOT = Path("dist") / "backgrounds" / "second_screen_console"
CONSOLE_VARIANTS = {"eu_jp", "us"}


def parse_args():
    parser = argparse.ArgumentParser(description="Second-screen console background builder")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input folder containing source images",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output folder (defaults to dist/backgrounds/second_screen_console/<input variant>)",
    )
    return parser.parse_args()


def resize_console_background(source_path, temp_path):
    cmd = [
        "magick",
        str(source_path),
        "-resize",
        f"{BACKGROUND_W}x{BACKGROUND_H}!",
        str(temp_path),
    ]
    return run_magick(cmd) is not None


def main():
    args = parse_args()
    input_root = Path(os.path.normpath(args.input))

    ensure_input_dir(input_root)
    if args.output:
        output_dir = Path(os.path.normpath(args.output))
    else:
        variant = input_root.name.lower()
        if variant not in CONSOLE_VARIANTS:
            print("[Error] Input folder must be named 'eu_jp' or 'us' when --output is omitted.")
            sys.exit(1)
        output_dir = DEFAULT_OUTPUT_ROOT / variant
    failed_dir = output_dir / "_pngquant_failed"

    files = collect_images(input_root)
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
    print(f"Resize: {BACKGROUND_W}x{BACKGROUND_H}")
    print(f"Starting processing for '{input_root.name}' ({len(files)} images) for second_screen_console...")

    processed = 0
    failed = 0
    total = len(files)
    for index, source_path in enumerate(files, start=1):
        print(f"[{index}/{total}] {source_path.name}")
        destination_path = output_dir / build_output_filename(source_path)
        with tempfile.NamedTemporaryFile(prefix="bg_console_", suffix=".png", delete=False) as crop_tmp:
            crop_path = Path(crop_tmp.name)
        try:
            if not resize_console_background(source_path, crop_path):
                print(f"  [Skip] Resize failed: {source_path.name}")
                continue

            print(f"[DITHER   ] {source_path.name[:25].ljust(27)} -> o4x4")
            if not apply_rgb565_o4x4_dither(crop_path, destination_path):
                print(f"  [Skip] Dither failed: {source_path.name}")
                continue

            compression_result = compress_png(destination_path, source_path.name)
            if compression_result == "failed":
                failed += 1
                handle_compression_failure(
                    destination_path=destination_path,
                    working_path=crop_path,
                    failed_dir=failed_dir,
                    source_name=source_path.name,
                    suffix_label="resized",
                )
                continue

            processed += 1
        finally:
            if crop_path.exists():
                crop_path.unlink()

    print(f"[Done] Compressed {processed} second-screen console background(s) to {output_dir}")
    if failed:
        print(f"[Done] Moved {failed} compression-failed console background(s) to {failed_dir}")
    elif not any(failed_dir.iterdir()):
        failed_dir.rmdir()
        print(f"[Done] Removed empty failures folder: {failed_dir}")


if __name__ == "__main__":
    main()
