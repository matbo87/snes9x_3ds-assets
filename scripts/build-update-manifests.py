"""Build emulator update manifests from committed dist assets."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

CACHE_MANIFEST = DIST / "thumbnail-caches.txt"
GAME_MANIFEST = DIST / "game-assets.txt"

# In picker order. The emulator inflates each download and stores it at the path
# without .gz; it only offers paths it has a thumbnail type for.
CACHE_VARIANTS = [
    "thumbnails/boxart_us-style.cache.gz",
    "thumbnails/boxart_japan-style.cache.gz",
    "thumbnails/boxart_pal-style.cache.gz",
    "thumbnails/title.cache.gz",
    "thumbnails/gameplay.cache.gz",
]

# Must match UpdaterAssetGroup in the emulator.
GAME_ASSETS = [
    ("backgrounds/game_screen", ".png"),
    ("backgrounds/second_screen_cover_art", ".png"),
    ("backgrounds/second_screen_console/eu_jp", ".png"),
    ("backgrounds/second_screen_console/us", ".png"),
    ("cheats", ".chx"),
]

# These outputs are intentionally uncommitted while being generated.
GENERATED_MANIFESTS = {CACHE_MANIFEST, GAME_MANIFEST}


def parse_args():
    parser = argparse.ArgumentParser(description="Update Manifest Builder")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated files are up to date without writing (exit 1 on drift)",
    )
    return parser.parse_args()


def git(*args):
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


def commit_times():
    """dist-relative path -> unix time its current content first appeared under its file name.

    Keyed on (file name, blob) so a file moved to another directory keeps its date.
    """
    first_seen = {}
    stamp = None
    log = git("log", "--format=%ct", "--raw", "--no-abbrev", "--no-renames", "--", "dist")
    for line in log.splitlines():
        if not line.strip():
            continue
        if not line.startswith(":"):
            stamp = int(line)
            continue
        meta, path = line.split("\t", 1)
        blob = meta.split()[3]
        if set(blob) == {"0"}:  # Deletion.
            continue
        key = (Path(path).name, blob)
        first_seen[key] = min(stamp, first_seen.get(key, stamp))

    times = {}
    for line in git("ls-tree", "-r", "HEAD", "--", "dist").splitlines():
        meta, path = line.split("\t", 1)
        blob = meta.split()[2]
        times[path[len("dist/"):]] = first_seen[(Path(path).name, blob)]
    return times


def status_codes():
    """dist-relative path -> porcelain status; absent means clean and committed."""
    codes = {}
    for line in git("status", "--porcelain", "--ignored=matching", "--", "dist").splitlines():
        code, path = line[:2], line[3:]
        if " -> " in path:  # Porcelain rename: old -> new.
            path = path.split(" -> ", 1)[1]
        codes[path.strip('"')[len("dist/"):]] = code
    return codes


STATUS_REASONS = {
    "!!": "ignored by git, so it would never reach the server",
    "??": "untracked",
}


class Publisher:
    def __init__(self):
        self.times = commit_times()
        self.codes = status_codes()
        for path in GENERATED_MANIFESTS:
            self.codes.pop(path.relative_to(DIST).as_posix(), None)
        self.problems = []

    def published(self, relative):
        code = self.codes.get(relative)
        if code is not None:
            reason = STATUS_REASONS.get(code)
            if reason is None:
                reason = "staged but not committed" if code.startswith("A") \
                    else "modified since its last commit"
            self.problems.append(f"  {reason}: {relative}")
            return 0
        stamp = self.times.get(relative)
        if stamp is None:
            self.problems.append(f"  not committed: {relative}")
            return 0
        return stamp

    def report(self):
        if not self.problems:
            return
        shown = self.problems[:10]
        extra = len(self.problems) - len(shown)
        if extra > 0:
            shown.append(f"  ... and {extra} more")
        sys.exit(
            "publish times come from git, so every asset must be committed first.\n"
            + "\n".join(shown)
        )


def build_cache_manifest(publisher):
    rows = [
        "# source\tpublished",
        "# published is the asset's git commit time in epoch seconds",
    ]
    for source in CACHE_VARIANTS:
        path = DIST / source
        if not path.is_file():
            sys.exit(f"missing cache variant: {path}")
        rows.append(f"{source}\t{publisher.published(source)}")
    return "\n".join(rows) + "\n"


def build_game_manifest(publisher):
    # Include games with at least one asset; missing columns use 0.
    found = []
    for directory, suffix in GAME_ASSETS:
        base = DIST / directory
        found.append({
            p.stem: publisher.published(f"{directory}/{p.name}")
            for p in sorted(base.glob("*" + suffix))
        })

    names = sorted(set().union(*(f.keys() for f in found)))
    header = "# game\t" + "\t".join(d for d, _ in GAME_ASSETS)
    rows = [header]
    for name in names:
        if "\t" in name:
            sys.exit(f"game name contains a tab: {name!r}")
        rows.append(name + "\t" + "\t".join(str(f.get(name, 0)) for f in found))
    return "\n".join(rows) + "\n"


def write(path, content, check):
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if check:
        if current != content:
            print(f"out of date: {path.relative_to(ROOT)}")
            return False
        return True
    if current != content:
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    else:
        print(f"unchanged {path.relative_to(ROOT)}")
    return True


def main():
    args = parse_args()
    publisher = Publisher()
    cache = build_cache_manifest(publisher)
    games = build_game_manifest(publisher)
    publisher.report()

    ok = write(CACHE_MANIFEST, cache, args.check)
    ok = write(GAME_MANIFEST, games, args.check) and ok
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
