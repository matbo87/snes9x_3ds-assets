import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

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
        help="Input folder containing background images",
    )
    return parser.parse_args()


def collect_images(input_root):
    files = sorted(
        [p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS],
        key=lambda p: str(p.relative_to(input_root)),
    )
    return files


def build_output_filename(source_path):
    clean_name = source_path.stem.strip()
    # Remove trailing metadata groups like " (USA)" / " [!]" while keeping base title intact.
    while True:
        updated = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*$", "", clean_name).strip()
        if updated == clean_name:
            break
        clean_name = updated
    if not clean_name:
        clean_name = source_path.stem.strip()
    return f"{clean_name}.png"


def validate_flat_name_collisions(files):
    seen = {}
    duplicates = []

    for path in files:
        normalized_name = build_output_filename(path).lower()
        if normalized_name in seen:
            duplicates.append((seen[normalized_name], path))
        else:
            seen[normalized_name] = path

    return duplicates


def run_magick(cmd_list):
    try:
        subprocess.run(cmd_list, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as error:
        stderr_text = error.stderr.strip() if error.stderr else str(error)
        print(f"  [Magick Error] {stderr_text}")
        return False
    except FileNotFoundError:
        print("[Error] ImageMagick not found. Please install it.")
        sys.exit(1)


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
    return run_magick(cmd)


def apply_rgb565_dither(source_path, destination_path, mode):
    cmd = [
        "magick",
        str(source_path),
        "-channel",
        "R",
        "-ordered-dither",
        f"{mode},32",
        "-channel",
        "G",
        "-ordered-dither",
        f"{mode},64",
        "-channel",
        "B",
        "-ordered-dither",
        f"{mode},32",
        "+channel",
        "-strip",
        str(destination_path),
    ]
    return run_magick(cmd)


def compress_png(filepath, image_name):
    if not shutil.which("pngquant"):
        print("  [Error] pngquant not found. Compression is required for game-screen backgrounds.")
        return "failed"

    try:
        subprocess.run(
            [
                "pngquant",
                "--force",
                "--ext",
                ".png",
                "--quality=80-100",
                "--speed",
                "1",
                "--nofs",
                "--strip",
                str(filepath),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return "tier1"
    except subprocess.CalledProcessError:
        print(f"  [Info] High quality pngquant failed for {image_name}, retrying with quality 50-79...")
        try:
            subprocess.run(
                [
                    "pngquant",
                    "--force",
                    "--ext",
                    ".png",
                    "--quality=50-79",
                    "--speed",
                    "1",
                    "--nofs",
                    "--strip",
                    str(filepath),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return "tier2"
        except subprocess.CalledProcessError:
            print("  [Warning] pngquant failed at lower quality.")
            return "failed"


def main():
    args = parse_args()

    clean_input_path = Path(os.path.normpath(args.input))
    output_kind = "game_screen"
    output_dir = Path("dist") / "backgrounds" / output_kind
    failed_dir = output_dir / "_pngquant_failed"

    if not clean_input_path.exists():
        print(f"[Error] Input folder not found: {clean_input_path}")
        sys.exit(1)

    if not clean_input_path.is_dir():
        print(f"[Error] Input path is not a directory: {clean_input_path}")
        sys.exit(1)

    files = collect_images(clean_input_path)
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
    print(f"Starting processing for '{clean_input_path.name}' ({len(files)} images) as '{output_kind}'...")

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

            if not apply_rgb565_dither(effect_path, destination_path, "o4x4"):
                print(f"  [Skip] Dither stage failed: {source_path.name}")
                continue

            compression_result = compress_png(destination_path, source_path.name)
            if compression_result == "failed":
                failed += 1
                failed_effect_path = failed_dir / f"{destination_path.stem}.effect.png"
                if destination_path.exists():
                    destination_path.unlink()
                shutil.move(str(effect_path), str(failed_effect_path))
                print(
                    f"  [Moved] Compression failed for {source_path.name}; "
                    f"moved effected image to {failed_effect_path}"
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
