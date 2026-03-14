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

# Source boxart size is expected to be 782x547.
BACKGROUND_CROP_W, BACKGROUND_CROP_H = 562, 385
BACKGROUND_CROP_X, BACKGROUND_CROP_Y = 186, 23
BACKGROUND_W, BACKGROUND_H = 350, 240


def parse_args():
    parser = argparse.ArgumentParser(description="Background Builder")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input folder containing source images",
    )
    return parser.parse_args()


def crop_and_resize(source_path, temp_path):
    cmd = [
        "magick",
        str(source_path),
        "-crop",
        f"{BACKGROUND_CROP_W}x{BACKGROUND_CROP_H}+{BACKGROUND_CROP_X}+{BACKGROUND_CROP_Y}",
        "+repage",
        "-resize",
        f"{BACKGROUND_W}x{BACKGROUND_H}!",
        str(temp_path),
    ]
    return run_magick(cmd) is not None


def main():
    args = parse_args()
    input_root = Path(os.path.normpath(args.input))
    output_dir = Path("dist") / "backgrounds" / "second_screen_boxart"
    failed_dir = output_dir / "_pngquant_failed"

    ensure_input_dir(input_root)
    if "boxart" not in {part.lower() for part in input_root.parts}:
        print("[Error] Input path must include a 'boxart' folder for second-screen background crop logic.")
        sys.exit(1)

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
    print(
        f"Crop: {BACKGROUND_CROP_W}x{BACKGROUND_CROP_H}+{BACKGROUND_CROP_X}+{BACKGROUND_CROP_Y} | "
        f"Resize: {BACKGROUND_W}x{BACKGROUND_H}"
    )
    print(f"Starting processing for '{input_root.name}' ({len(files)} images) for second_screen_boxart...")

    processed = 0
    failed = 0
    total = len(files)
    for index, source_path in enumerate(files, start=1):
        print(f"[{index}/{total}] {source_path.name}")
        destination_path = output_dir / build_output_filename(source_path)
        with tempfile.NamedTemporaryFile(prefix="bg_", suffix=".png", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            if not crop_and_resize(source_path, tmp_path):
                print(f"  [Skip] Crop/resize failed: {source_path.name}")
                continue

            print(f"[DITHER   ] {source_path.name[:25].ljust(27)} -> o4x4")
            if not apply_rgb565_o4x4_dither(tmp_path, destination_path):
                print(f"  [Skip] Dither failed: {source_path.name}")
                continue

            compression_result = compress_png(destination_path, source_path.name)
            if compression_result == "failed":
                failed += 1
                handle_compression_failure(
                    destination_path=destination_path,
                    working_path=tmp_path,
                    failed_dir=failed_dir,
                    source_name=source_path.name,
                    suffix_label="resized",
                )
                continue
            processed += 1
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    print(f"[Done] Compressed {processed} second-screen background(s) to {output_dir}")
    if failed:
        print(f"[Done] Moved {failed} compression-failed cover(s) to {failed_dir}")
    elif not any(failed_dir.iterdir()):
        failed_dir.rmdir()
        print(f"[Done] Removed empty failures folder: {failed_dir}")


if __name__ == "__main__":
    main()
