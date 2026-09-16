"""Build 3DS thumbnail caches or preview atlases.

Input folders are scanned recursively:

  python3 scripts/build-cache.py -i <gameplay> --dither checks,32,64,32
  python3 scripts/build-cache.py -i <title> --dither checks,32,64,32
  python3 scripts/build-cache.py -i <boxart_us-style> -b <1g1r covers>
  python3 scripts/build-cache.py -i <boxart_japan-style> -b <1g1r covers>
  python3 scripts/build-cache.py -i <boxart_pal-style> -b <1g1r covers>

The default output is dist/thumbnails/<first-input-dir>.cache.gz; use -o to set a
different output path. Repeat -i to combine cover folders. Use -b to fill
missing input titles from a fallback folder.

Use -p to render a preview atlas instead of a cache. Example with a custom font:
python3 scripts/build-cache.py -i <boxart_us-style> -p -f <path/to/my-custom-font.ttf>

All box-art variants are 1G1R. Each prefers its regional style and uses official artwork for remaining titles.
PAL-style also includes custom-made PAL-style covers for titles without a PAL-region release.
"""

import argparse
import collections
import concurrent.futures
import gzip
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_OUTPUT_DIR = os.path.join("dist", "thumbnails")

# Keep in sync with thumbMaxCount in 3dsui_img.cpp.
MAX_ENTRIES = 1024

_BUNDLED_FONT = Path(__file__).resolve().with_name("Minecraftia.ttf")
PREVIEW_FONT = str(_BUNDLED_FONT) if _BUNDLED_FONT.exists() else None

# TMB1: little-endian 20-byte header followed by 12-byte index entries.
# Its fourth byte is the format version; bump it for incompatible changes.
CACHE_MAGIC = b"TMB1"
CACHE_HEADER_SIZE = 20
CACHE_INDEX_ENTRY_SIZE = 12

# Match the emulator's maximum thumbnail dimension.
THUMB_BOX = 128

def compute_game_id(name):
    hash_val = 5381
    for char in name:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
        hash_val = hash_val & 0xFFFFFFFF
    return hash_val

def trim_name(filename):
    clean_name = os.path.splitext(filename)[0]
    cut = min(
        (clean_name.index(c) for c in ("(", "[") if c in clean_name),
        default=len(clean_name)
    )
    return clean_name[:cut].strip()

def resolve_layout(source_size):
    """Fit the source into the thumbnail box, keeping its aspect."""
    if not source_size:
        return None
    width, height = source_size
    if width >= height:
        return {
            "size": (THUMB_BOX, max(1, round(THUMB_BOX * height / width))),
            "axis": "x",
        }
    return {
        "size": (max(1, round(THUMB_BOX * width / height)), THUMB_BOX),
        "axis": "y",
    }

def add_fallbacks(fallback_root, files, image_exts):
    """Append fallback images for titles absent from files."""
    if not fallback_root.is_dir():
        raise RuntimeError(f"fallback folder not found: {fallback_root}")

    # Cache IDs are computed from trim_name(), not the full filename.  Use the
    # same key here so a Japanese cover named after its equivalent (for example
    # a different region/revision suffix) correctly suppresses its fallback.
    existing_titles = {trim_name(path.name) for path in files}
    by_title = {}
    errors = []
    for path in sorted(fallback_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in image_exts:
            continue
        title = trim_name(path.name)
        if title in existing_titles:
            continue
        if title in by_title:
            errors.append(f"ambiguous fallback: {title}")
        by_title[title] = path

    if errors:
        raise RuntimeError(
            f"Could not resolve fallbacks from {fallback_root}:\n  " + "\n  ".join(errors)
        )

    files.extend(by_title.values())
    print(f"Added {len(by_title)} fallbacks from {fallback_root}")

def source_sizes(files, chunk=200):
    """path -> (width, height), in as few magick calls as possible."""
    sizes = {}
    for start in range(0, len(files), chunk):
        batch = files[start:start + chunk]
        result = subprocess.run(
            ["magick", "identify", "-format", "%w %h %i\n", *[str(p) for p in batch]],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            width, height, name = line.split(" ", 2)
            sizes[name.strip()] = (int(width), int(height))
    return sizes


def report_odd_sources(files, sizes):
    """Report sources that differ from the dominant dimensions."""
    counts = collections.Counter(sizes[str(p)] for p in files if str(p) in sizes)
    if len(counts) < 2:
        return
    common, _ = counts.most_common(1)[0]
    odd = [p for p in files if sizes.get(str(p)) not in (common, None)]
    print(f"[Warning] {len(odd)} source(s) differ from the dominant "
          f"{common[0]}x{common[1]} and get their own thumbnail size:")
    for path in sorted(odd)[:10]:
        width, height = sizes[str(path)]
        print(f"  {width}x{height}  {path.name}")
    if len(odd) > 10:
        print(f"  ... and {len(odd) - 10} more")


def build_process_command(filepath, layout, dither):
    cmd = ["magick", filepath]

    width, height = layout["size"]
    cmd.extend([
        "-filter", "Lanczos",
        "-resize", f"{width}x{height}!",
        "-unsharp", "0x0.5+0.7+0"
    ])

    if dither:
        cmd.extend(["-ordered-dither", dither])

    cmd.extend([
        "-depth", "8",
        "RGB:-"
    ])
    return cmd

def get_raw_pixels(cmd, filepath):
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_data, stderr = process.communicate()
        if process.returncode != 0:
            print(f"  [Error] {filepath}: {stderr.decode().strip()}")
            return None
        return raw_data
    except FileNotFoundError:
        print("  [Error] ImageMagick not found. Please install it.")
        sys.exit(1)

def generate_labeled_tile(args):
    i, rgb_data, name, width, height, font_path, tmpdir = args
    out_png = os.path.join(tmpdir, f"tile_{i:04d}.png")

    label_height = 15
    pad_x = 4
    pad_y = 1

    cmd = [
        "magick",
        "(",
        "-size", f"{width}x{height}",
        "-depth", "8",
        "RGB:-",
        ")",
        "(",
        "-size", f"{width}x{label_height}", "xc:black",
        "-fill", "white"
    ]

    if font_path:
        cmd.extend(["-font", font_path])

    cmd.extend([
        "-pointsize", "8",
        "-gravity", "NorthWest",
        "-annotate", f"+{pad_x}{pad_y:+}", name,
        "-fill", "black",
        "-draw", f"rectangle {width-pad_x},0 {width},{label_height}",
        ")",
        "-append",
        out_png
    ])

    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate(input=rgb_data)
        if process.returncode != 0:
            print(f"  [Tile Error] {name}: {stderr.decode().strip()}")
    except Exception as e:
        print(f"  [Tile Error] {name}: {e}")

    return out_png

def run_montage(tile_files, output_file, columns):
    list_file = f"{output_file}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for tf in sorted(tile_files):
            f.write(f"{tf}\n".replace("\\", "/"))

    cmd = [
        "magick", "montage",
        f"@{list_file}",
        "-tile", f"{columns}x",
        "-geometry", "+2+0",
        "-background", "black",
        output_file
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = process.communicate()
    if process.returncode != 0:
        print(f"  [Preview Error] {stderr.decode().strip()}")
        return False
    return True

def create_preview_atlas(tiles, output_file, font_path=None):
    """Render display-ordered tiles in same-size montage sections."""
    print(f"Generating individual labeled tiles ({len(tiles)} images)...")

    runs = []
    for tile in tiles:
        size = (tile[2], tile[3])
        if not runs or runs[-1][0] != size:
            runs.append((size, []))
        runs[-1][1].append(tile)

    with tempfile.TemporaryDirectory() as tmpdir:
        tasks = []
        run_indexes = []
        for size, run_tiles in runs:
            idxs = []
            for rgb_data, name, width, height in run_tiles:
                idxs.append(len(tasks))
                tasks.append((len(tasks), rgb_data, name, width, height, font_path, tmpdir))
            run_indexes.append((size, idxs))

        rendered = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for i, out_png in zip((t[0] for t in tasks),
                                  executor.map(generate_labeled_tile, tasks)):
                if os.path.exists(out_png):
                    rendered[i] = out_png

        print("Stitching tiles into the final atlas grid...")

        sections = []
        for gi, (size, idxs) in enumerate(run_indexes):
            tile_files = [rendered[i] for i in idxs if i in rendered]
            if not tile_files:
                continue
            columns = preview_columns_for(len(tile_files))
            print(f"  {size[0]}x{size[1]}: {len(tile_files)} tiles, {columns} columns")
            section = os.path.join(tmpdir, f"section_{gi:02d}.png")
            if run_montage(tile_files, section, columns):
                sections.append(section)

        if not sections:
            return

        if len(sections) == 1:
            shutil.copyfile(sections[0], output_file)
        else:
            cmd = ["magick"] + sections + ["-background", "black", "-gravity", "West",
                                           "-append", output_file]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = process.communicate()
            if process.returncode != 0:
                print(f"  [Preview Error] {stderr.decode().strip()}")
                return

        print(f"  [Preview] Saved to {os.path.abspath(output_file)}")

def rotate_cw_rgb(data, w, h):
    """Rotate row-major RGB data 90 degrees clockwise."""
    out = bytearray(len(data))
    nw = h
    for r in range(w):
        base = r * nw * 3
        for c in range(nw):
            si = ((h - 1 - c) * w + r) * 3
            di = base + c * 3
            out[di:di+3] = data[si:si+3]
    return bytes(out)

def pack_rgb565(r, g, b):
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack('<H', val)

def swizzle_rgb565(raw_rgb, width, height):
    """Pre-swizzle to the 3DS framebuffer layout: column-major, bottom-to-top."""
    out = bytearray()
    for x in range(width):
        for y in range(height - 1, -1, -1):
            src_idx = (y * width + x) * 3
            r, g, b = raw_rgb[src_idx:src_idx+3]
            out.extend(pack_rgb565(r, g, b))
    return bytes(out)

def simulate_rgb565_loss(raw_bytes):
    data = bytearray(raw_bytes)
    total_pixels = len(data) // 3
    for i in range(total_pixels):
        idx = i * 3
        data[idx]   = data[idx]   & 0xF8
        data[idx+1] = data[idx+1] & 0xFC
        data[idx+2] = data[idx+2] & 0xF8
    return data

def preview_columns_for(image_count):
    return 24 if image_count % 25 != 0 else 25

def write_cache(output_cache_file, records):
    """records: list of (game_id, width, height, pixel_bytes) in blob order."""
    header_w = max(w for _, w, _, _ in records)
    header_h = max(h for _, _, h, _ in records)

    # Offsets follow the complete index table.
    offset = CACHE_HEADER_SIZE + len(records) * CACHE_INDEX_ENTRY_SIZE
    index_data = []
    blob_data = bytearray()
    for game_id, w, h, pixels in records:
        index_data.append((game_id, offset, w, h))
        blob_data.extend(pixels)
        offset += len(pixels)

    count = len(index_data)
    print(f"Writing cache... format={CACHE_MAGIC.decode()} "
          f"({count} entries, {CACHE_INDEX_ENTRY_SIZE} byte index, "
          f"max {header_w}x{header_h})")
    # mtime=0 keeps the output byte-identical for an unchanged cache, so git sees no change.
    name = Path(output_cache_file).name.removesuffix(".gz")
    with open(output_cache_file, "wb") as raw, \
            gzip.GzipFile(filename=name, fileobj=raw, mode="wb", compresslevel=9, mtime=0) as f:
        f.write(CACHE_MAGIC)
        f.write(struct.pack('<HH', 0, 0))
        f.write(struct.pack('<II', count, count))
        f.write(struct.pack('<HH', header_w, header_h))
        for gid, off, w, h in index_data:
            f.write(struct.pack('<IIHH', gid, off, w, h))
        f.write(blob_data)

def main():
    parser = argparse.ArgumentParser(description="3DS Thumbnail Cache Builder")
    parser.add_argument("--input", "-i", required=True, action="append", metavar="DIR",
                        help="Input folder of PNGs; repeat to combine folders")
    parser.add_argument("--dither", help="ImageMagick ordered-dither map")
    parser.add_argument("--preview", "-p", action="store_true", help="Generate only a preview atlas PNG (no cache file)")
    parser.add_argument("--font", "-f", default=PREVIEW_FONT, help="TTF font for preview labels (optional)")
    parser.add_argument("--output", "-o", metavar="PATH",
                        help="Output path of the gzipped cache (default: dist/thumbnails/<first-input-dir>.cache.gz)")
    parser.add_argument("--fallback-dir", "-b",
                        help="Second folder; its images fill titles the input folder lacks")

    args = parser.parse_args()

    font_path = args.font
    if font_path and not os.path.exists(font_path):
        print(f"[Warning] Font not found, using ImageMagick default: {font_path}")
        font_path = None

    clean_input_paths = [os.path.normpath(input_path) for input_path in args.input]
    folder_name = ", ".join(os.path.basename(input_path) for input_path in clean_input_paths)
    primary_input_name = Path(os.path.abspath(clean_input_paths[0])).name
    default_output = Path(DEFAULT_OUTPUT_DIR) / f"{primary_input_name}.cache.gz"
    output_cache_file = Path(args.output) if args.output else default_output
    output_cache_file.parent.mkdir(parents=True, exist_ok=True)
    output_preview_file = Path(f"{str(output_cache_file).removesuffix('.gz')}.preview.png")

    dither = args.dither

    missing_inputs = [input_path for input_path in clean_input_paths
                      if not os.path.isdir(input_path)]
    if missing_inputs:
        for input_path in missing_inputs:
            print(f"[Error] Input folder not found: {input_path}")
        sys.exit(1)

    input_roots = [Path(input_path) for input_path in clean_input_paths]
    image_exts = {".png", ".webp"}

    # Keep preferred images before fallback images in previews.
    files = [p for input_root in input_roots for p in input_root.rglob("*")
             if p.is_file() and p.suffix.lower() in image_exts]
    source_priority = {str(path): 0 for path in files}
    if args.fallback_dir:
        try:
            input_count = len(files)
            add_fallbacks(Path(args.fallback_dir), files, image_exts)
            for path in files[input_count:]:
                source_priority[str(path)] = 1
        except RuntimeError as error:
            print(f"[Error] {error}")
            sys.exit(1)

    sizes = source_sizes(files)
    unmeasured = [p for p in files if resolve_layout(sizes.get(str(p))) is None]
    if unmeasured:
        print(f"[Warning] Skipping {len(unmeasured)} unreadable source(s):")
        for path in unmeasured[:10]:
            print(f"  {path}")
        files = [p for p in files if p not in set(unmeasured)]

    def preview_size(path):
        layout = resolve_layout(sizes.get(str(path)))
        width, height = layout["size"]
        return (height, width) if layout.get("axis") == "y" else (width, height)

    def sort_key(path):
        width, height = preview_size(path)
        return (source_priority[str(path)], -height, -width,
                trim_name(path.name).lower(),
                path.name.lower())

    files.sort(key=sort_key)
    if len(files) > MAX_ENTRIES:
        print(f"[Error] Found {len(files)} images, but a cache holds at most {MAX_ENTRIES}. "
              f"The emulator would reject the whole file, so nothing was built.")
        sys.exit(1)

    mode = "preview-only" if args.preview else "cache"
    print(f"Processing '{folder_name}' ({len(files)} images) [{mode}]...")
    print(f"Config: fit into {THUMB_BOX}x{THUMB_BOX} px | Dither: {dither}")

    report_odd_sources(files, sizes)

    records = []
    preview_tiles = []
    layout_counts = {}

    for path in files:
        trimmed_name = trim_name(path.name)

        layout = resolve_layout(sizes.get(str(path)))
        width, height = layout["size"]
        key = f"{width}x{height}"
        layout_counts[key] = layout_counts.get(key, 0) + 1

        cmd = build_process_command(str(path), layout, dither)
        raw_rgb = get_raw_pixels(cmd, str(path))

        expected_size = width * height * 3
        if not raw_rgb or len(raw_rgb) != expected_size:
            print(f"  [Skip] Bad data for {path.name}")
            continue

        if args.preview:
            tile_rgb = simulate_rgb565_loss(raw_rgb)
            tile_w, tile_h = width, height
            # Keep portrait preview tiles landscape; cache pixels stay unchanged.
            if layout.get("axis") == "y":
                tile_rgb = rotate_cw_rgb(tile_rgb, width, height)
                tile_w, tile_h = height, width
            preview_tiles.append((tile_rgb, trimmed_name, tile_w, tile_h))
        else:
            records.append((
                compute_game_id(trimmed_name),
                width,
                height,
                swizzle_rgb565(raw_rgb, width, height),
            ))

    print("Layouts used:")
    for key, count in sorted(layout_counts.items()):
        print(f"  {count:5d} x  {key}")

    if not args.preview:
        if not records:
            print("[Error] No images processed.")
            sys.exit(1)
        write_cache(output_cache_file, records)
        print(f"Saved to {os.path.abspath(output_cache_file)}")

    if args.preview and preview_tiles:
        create_preview_atlas(preview_tiles, output_preview_file, font_path)

    print("Done.")

if __name__ == "__main__":
    main()
