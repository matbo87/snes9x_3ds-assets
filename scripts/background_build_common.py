import re
import shutil
import subprocess
import sys
from pathlib import Path

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def ensure_input_dir(input_path):
    if not input_path.exists():
        print(f"[Error] Input folder not found: {input_path}")
        sys.exit(1)
    if not input_path.is_dir():
        print(f"[Error] Input path is not a directory: {input_path}")
        sys.exit(1)


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


def collect_images(input_root, valid_extensions=VALID_EXTENSIONS):
    return sorted(
        [p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() in valid_extensions],
        key=lambda p: str(p.relative_to(input_root)),
    )


def build_output_filename(source_path):
    clean_name = source_path.stem.strip()
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


def compress_png(filepath, image_name, quality_steps=None):
    if quality_steps is None:
        quality_steps = ["80-100", "50-79", "40-79"]

    if not shutil.which("pngquant"):
        print("  [Error] pngquant not found. Compression is required.")
        return "failed"

    for idx, quality in enumerate(quality_steps, start=1):
        try:
            subprocess.run(
                [
                    "pngquant",
                    "--force",
                    "--ext",
                    ".png",
                    f"--quality={quality}",
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
            return f"tier{idx}"
        except subprocess.CalledProcessError:
            if idx < len(quality_steps):
                print(
                    f"  [Info] pngquant tier {idx} failed for {image_name}, "
                    f"retrying with quality {quality_steps[idx]}..."
                )

    print("  [Warning] pngquant failed at lower quality.")
    return "failed"


def apply_rgb565_o4x4_dither(source_path, target_path):
    cmd = [
        "magick",
        str(source_path),
        "-channel",
        "R",
        "-ordered-dither",
        "o4x4,32",
        "-channel",
        "G",
        "-ordered-dither",
        "o4x4,64",
        "-channel",
        "B",
        "-ordered-dither",
        "o4x4,32",
        "+channel",
        "-strip",
        str(target_path),
    ]
    return run_magick(cmd) is not None


def handle_compression_failure(destination_path, working_path, failed_dir, source_name, suffix_label):
    failed_output_path = failed_dir / f"{destination_path.stem}.{suffix_label}.png"
    if destination_path.exists():
        destination_path.unlink()
    shutil.move(str(working_path), str(failed_output_path))
    print(
        f"  [Moved] Compression failed for {source_name}; "
        f"moved {suffix_label} image to {failed_output_path}"
    )
