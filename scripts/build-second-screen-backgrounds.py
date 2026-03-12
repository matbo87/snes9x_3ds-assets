import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Source boxart size is expected to be 782x547.
COVER_CROP_W, COVER_CROP_H = 562, 385
COVER_CROP_X, COVER_CROP_Y = 186, 23
COVER_W, COVER_H = 350, 240

THRESH_GRADIENT_STD = 0.15
THRESH_SIZE_KB = 155

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
VALID_MODES = {"o8x8", "o4x4", "checks"}


def parse_args():
    parser = argparse.ArgumentParser(description="Second Screen Background Builder")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input folder containing boxart images",
    )
    parser.add_argument(
        "--force",
        choices=sorted(VALID_MODES),
        help="Force a specific dither mode",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Use automatic dither mode selection heuristic instead of default o4x4",
    )
    return parser.parse_args()


def run_magick(cmd_list):
    try:
        result = subprocess.run(cmd_list, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as error:
        stderr_text = error.stderr.strip() if error.stderr else str(error)
        print(f"  [Magick Error] {stderr_text}")
        return None
    except FileNotFoundError:
        print("  [Error] ImageMagick not found. Please install it.")
        sys.exit(1)


def collect_images(input_root):
    return sorted(
        [p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS],
        key=lambda p: str(p.relative_to(input_root)),
    )


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


def get_stats(filepath):
    dev_cmd = ["magick", str(filepath), "-format", "%[fx:standard_deviation]", "info:"]
    dev_str = run_magick(dev_cmd)
    std_dev = float(dev_str) if dev_str else 0.0
    size_kb = int(os.path.getsize(filepath) / 1024)
    return std_dev, size_kb


def choose_dither_mode(filepath, forced_mode, use_auto):
    if forced_mode:
        return forced_mode, "FORCED", 0.0, 0

    if not use_auto:
        return "o4x4", "DEFAULT", 0.0, 0

    std_dev, size_kb = get_stats(filepath)
    if std_dev < THRESH_GRADIENT_STD:
        return "o8x8", "GRADIENT", std_dev, size_kb
    if size_kb < THRESH_SIZE_KB:
        return "checks", "PHOTO/MIX", std_dev, size_kb
    return "o4x4", "SHARP ART", std_dev, size_kb


def crop_and_resize(source_path, temp_path):
    cmd = [
        "magick",
        str(source_path),
        "-crop",
        f"{COVER_CROP_W}x{COVER_CROP_H}+{COVER_CROP_X}+{COVER_CROP_Y}",
        "+repage",
        "-resize",
        f"{COVER_W}x{COVER_H}!",
        str(temp_path),
    ]
    return run_magick(cmd) is not None


def apply_dither(source_path, target_path, mode):
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
        str(target_path),
    ]
    return run_magick(cmd) is not None


def compress_png(filepath, image_name):
    if not shutil.which("pngquant"):
        print("  [Error] pngquant not found. Compression is required for second-screen backgrounds.")
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
            print(f"  [Info] Mid quality pngquant failed for {image_name}, retrying with quality 40-79...")
            try:
                subprocess.run(
                    [
                        "pngquant",
                        "--force",
                        "--ext",
                        ".png",
                        "--quality=40-79",
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
                return "tier3"
            except subprocess.CalledProcessError:
                print("  [Warning] pngquant failed at lower quality.")
                return "failed"


def main():
    args = parse_args()
    input_root = Path(os.path.normpath(args.input))
    output_dir = Path("dist") / "backgrounds" / "second_screen"
    failed_dir = output_dir / "_pngquant_failed"

    if not input_root.exists():
        print(f"[Error] Input folder not found: {input_root}")
        sys.exit(1)
    if not input_root.is_dir():
        print(f"[Error] Input path is not a directory: {input_root}")
        sys.exit(1)
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
        f"Crop: {COVER_CROP_W}x{COVER_CROP_H}+{COVER_CROP_X}+{COVER_CROP_Y} | "
        f"Resize: {COVER_W}x{COVER_H}"
    )
    print(f"Starting processing for '{input_root.name}' ({len(files)} images) for second_screen...")

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

            mode, reason, std_dev, size_kb = choose_dither_mode(tmp_path, args.force, args.auto)
            if args.force or not args.auto:
                print(f"[{reason.ljust(9)}] {source_path.name[:25].ljust(27)} -> {mode}")
            else:
                print(
                    f"[{reason.ljust(9)}] {source_path.name[:25].ljust(27)} "
                    f"(Dev:{std_dev:.2f} Size:{size_kb}KB) -> {mode}"
                )

            if not apply_dither(tmp_path, destination_path, mode):
                print(f"  [Skip] Dither failed: {source_path.name}")
                continue

            compression_result = compress_png(destination_path, source_path.name)
            if compression_result == "failed":
                failed += 1
                failed_resized_path = failed_dir / f"{destination_path.stem}.resized.png"
                if destination_path.exists():
                    destination_path.unlink()
                shutil.move(str(tmp_path), str(failed_resized_path))
                print(
                    f"  [Moved] Compression failed for {source_path.name}; "
                    f"moved resized image to {failed_resized_path}"
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
