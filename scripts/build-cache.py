import os
import struct
import subprocess
import argparse
import sys
import tempfile
import concurrent.futures
from pathlib import Path

# --- Configuration Presets ---
PRESETS = {
    "screenshot": {
        "width": 128,
        "height": 112,
        "crop": None,
        "dither": "checks,32,64,32"
    },
    "boxart": {
        "width": 128,
        "height": 96,
        "crop": "722x542+30+0",
        "dither": None
    }
}

MAX_GAMES = 1000 
PREVIEW_COLUMNS = 25
PREVIEW_FONT = str(Path(__file__).resolve().with_name("Minecraftia.ttf"))
OUTPUT_KINDS = {"gameplay", "boxart", "title"}

def compute_game_id(name):
    hash_val = 5381
    for char in name:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
        hash_val = hash_val & 0xFFFFFFFF
    return hash_val

def build_process_command(filepath, config):
    cmd = ["magick", filepath]
    
    if config.get("crop"):
        cmd.extend(["-crop", config["crop"], "+repage"])

    cmd.extend([
        "-filter", "Lanczos",
        "-resize", f"{config['width']}x{config['height']}!",
        "-unsharp", "0x0.5+0.7+0"
    ])

    if config.get("dither"):
        cmd.extend(["-ordered-dither", config["dither"]])

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

def create_preview_atlas(all_rgb_data, names, output_file, width, height, columns):
    print(f"Generating individual labeled tiles ({len(names)} images)...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tasks = []
        for i, (rgb_data, name) in enumerate(zip(all_rgb_data, names)):
            tasks.append((i, rgb_data, name, width, height, PREVIEW_FONT, tmpdir))
            
        tile_files = []
        
        # Process images in parallel for a massive speed boost
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for out_png in executor.map(generate_labeled_tile, tasks):
                if os.path.exists(out_png):
                    tile_files.append(out_png)
                
        print("Stitching tiles into the final atlas grid...")
        
        list_file = os.path.join(tmpdir, "files.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for tf in sorted(tile_files):
                clean_path = tf.replace("\\", "/") 
                f.write(f"{clean_path}\n")
                
        cmd = [
            "magick", "montage",
            f"@{list_file}",              
            "-tile", f"{columns}x",
            "-geometry", "+2+0",          
            "-background", "black",
            output_file
        ]

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = process.communicate()
            if process.returncode != 0:
                print(f"  [Preview Error] {stderr.decode().strip()}")
            else:
                print(f"  [Preview] Saved to {os.path.abspath(output_file)}")
        except Exception as e:
            print(f"  [Preview Error] Failed to run magick: {e}")

def pack_rgb565(r, g, b):
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack('<H', val)

def simulate_rgb565_loss(raw_bytes):
    data = bytearray(raw_bytes)
    total_pixels = len(data) // 3
    for i in range(total_pixels):
        idx = i * 3
        data[idx]   = data[idx]   & 0xF8
        data[idx+1] = data[idx+1] & 0xFC
        data[idx+2] = data[idx+2] & 0xF8
    return data

def detect_output_kind(input_path):
    path_parts = [p.lower() for p in Path(input_path).parts]
    for part in reversed(path_parts):
        if part in OUTPUT_KINDS:
            return part
    return Path(input_path).name.lower()

def preview_columns_for(kind, image_count):
    return 24 if image_count % 25 != 0 else 25

def main():
    parser = argparse.ArgumentParser(description="3DS Thumbnail Cache Builder")
    parser.add_argument("--type", "-t", required=True, choices=["screenshot", "boxart"], help="Type of images to process")
    parser.add_argument("--input", "-i", required=True, help="Input folder of PNGs")
    parser.add_argument("--preview", "-p", action="store_true", help="Generate only a preview atlas PNG (no cache file)")
    
    args = parser.parse_args()
    
    # --- Path Calculation ---
    clean_input_path = os.path.normpath(args.input)
    folder_name = os.path.basename(clean_input_path)
    output_kind = detect_output_kind(clean_input_path)
    output_dir = os.path.join("dist", "thumbnails")
    os.makedirs(output_dir, exist_ok=True)

    output_cache_file = os.path.join(output_dir, f"{output_kind}.cache")
    output_preview_file = os.path.join(output_dir, f"{output_kind}.cache.preview.png")

    config = PRESETS[args.type]
    
    if not os.path.exists(clean_input_path):
        print(f"[Error] Input folder not found: {clean_input_path}")
        sys.exit(1)

    # Collect image files recursively so region subfolders (e.g., Europe/USA/Japan) are included
    input_root = Path(clean_input_path)
    image_exts = {".png", ".webp"}
    files = sorted(
        [p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() in image_exts],
        key=lambda p: str(p.relative_to(input_root))
    )
    if len(files) > MAX_GAMES:
        print(f"[Warning] Found {len(files)} images, but limit is {MAX_GAMES}. Truncating list.")
        files = files[:MAX_GAMES]

    mode = "preview-only" if args.preview else "cache"
    print(f"Processing '{folder_name}' ({len(files)} images) as '{args.type}' [{mode}]...")
    print(f"Config: {config['width']}x{config['height']} px | Crop: {config.get('crop')} | Dither: {config.get('dither')}")

    index_data = []
    blob_data = bytearray()
    preview_blobs = [] 
    preview_names = []  
    
    header_size = 12
    index_size = len(files) * 8
    current_offset = header_size + index_size

    for path in files:
        filename = path.name
        clean_name = os.path.splitext(filename)[0]
        cut = min(
            (clean_name.index(c) for c in ("(", "[") if c in clean_name),
            default=len(clean_name)
        )
        trimmed_name = clean_name[:cut].strip()
        cmd = build_process_command(str(path), config)
        raw_rgb = get_raw_pixels(cmd, str(path))
        
        expected_size = config['width'] * config['height'] * 3
        if not raw_rgb or len(raw_rgb) != expected_size:
            print(f"  [Skip] Bad data for {filename}")
            continue

        if args.preview:
            preview_blobs.append(simulate_rgb565_loss(raw_rgb))
            preview_names.append(trimmed_name)  

        if not args.preview:
            game_id = compute_game_id(trimmed_name)
            for x in range(config['width']):
                for y in range(config['height'] - 1, -1, -1):
                    src_idx = (y * config['width'] + x) * 3
                    r, g, b = raw_rgb[src_idx:src_idx+3]
                    blob_data.extend(pack_rgb565(r, g, b))

            index_data.append((game_id, current_offset))
            current_offset += (config['width'] * config['height'] * 2)

    if not args.preview:
        index_data.sort()
        print(f"Writing cache...")
        with open(output_cache_file, "wb") as f:
            f.write(b'IMGZ')
            f.write(struct.pack('<I', len(index_data)))
            f.write(struct.pack('<HH', config['width'], config['height']))
            for gid, off in index_data:
                f.write(struct.pack('<II', gid, off))
            f.write(blob_data)
        print(f"Saved to {os.path.abspath(output_cache_file)}")

    if args.preview and preview_blobs:
        preview_columns = preview_columns_for(output_kind, len(preview_blobs))
        print(f"Preview grid columns: {preview_columns}")
        create_preview_atlas(
            preview_blobs, 
            preview_names, 
            output_preview_file, 
            config['width'], 
            config['height'],
            preview_columns
        )

    print("Done.")

if __name__ == "__main__":
    main()
