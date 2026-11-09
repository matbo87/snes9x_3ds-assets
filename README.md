# snes9x_3ds-assets

Cheats and image assets for the [snes9x_3ds emulator](https://github.com/matbo87/snes9x_3ds/releases).

The current asset packs and instructions are intended for **snes9x_3ds v2.0+**.

For older emulator versions, see the [v1.1.0 asset release](https://github.com/matbo87/snes9x_3ds-assets/releases/tag/v1.1.0) and [its README](https://github.com/matbo87/snes9x_3ds-assets/blob/v1.1.0/README.md).

The asset sets use one version of each game, following a one game, one region (1G1R) selection:

- No hacks, betas, prototypes or unlicensed games
- Region preference: **USA > Europe > Japan**

The focus is on US and European releases, with partial coverage of Japanese exclusives.

## Download

Download the [release packages](https://github.com/matbo87/snes9x_3ds-assets/releases).

You can also download individual files directly from the [`dist`](dist) folder.

## Current status and scope

Game list for the current set: [`src/file-list.txt`](src/file-list.txt)

Per-game asset coverage: [`ASSET_OVERVIEW.md`](ASSET_OVERVIEW.md)

### Asset variants

| Variant | Count | Notes |
| --- | ---: | --- |
| Gameplay | 1000 | Used for `thumbnails/gameplay.cache` and `backgrounds/game_screen` |
| Title | 1000 | Used for `thumbnails/title.cache` |
| Cover (US) | 1000 | Used for `thumbnails/cover_us-style.cache`<br>[`277 entries`](src/fallback/cover_us-style.cache.txt) use the 1G1R cover (Europe > Japan). |
| Cover (Japan) | 1000 | Used for `thumbnails/cover_japan-style.cache`<br>[`305 entries`](src/fallback/cover_japan-style.cache.txt) use the 1G1R cover (USA > Europe). |
| Cover (PAL) | 1000 | Used for `thumbnails/cover_pal-style.cache` and `backgrounds/second_screen_cover_art`<br>[`160 entries`](src/fallback/cover_pal-style.cache.txt) use the 1G1R cover (USA > Japan). |
| Console (EU/JP) | 840 | Used for `backgrounds/second_screen_console/eu_jp`<br>Missing titles: [`src/missing/console_eu_jp.txt`](src/missing/console_eu_jp.txt) |
| Console (USA) | 723 | Used for `backgrounds/second_screen_console/us`<br>Missing titles: [`src/missing/console_us.txt`](src/missing/console_us.txt) |
| Cheats | 882 | Used for `cheats` (`.chx` format)<br>Missing titles: [`src/missing/cheats.txt`](src/missing/cheats.txt) |

### Regional scope

- USA + PAL total set: **785 / 785** -> [`src/file-list_USA.txt`](src/file-list_USA.txt), [`src/file-list_Europe.txt`](src/file-list_Europe.txt)
- Japanese exclusives: **215 / 977** covered -> [`src/file-list_Japan.txt`](src/file-list_Japan.txt)

### Overlays

Two example overlays are available: a [default bezel](dist/defaults/overlay.png) and a [Super Mario World overlay](dist/overlays/Super%20Mario%20World.png).

There are no plans to add overlays for the full game set.

## Usage

Each asset set is optional. Choose backgrounds, overlays, and cheats for the games you play.

Download thumbnails, backgrounds, and cheats from **Emulator > Online Updater**. Load a game first to download its backgrounds or cheats.

For manual installation, place your chosen files in the matching folders under `/3ds/snes9x_3ds` on your SD card, as shown below.
Extract the thumbnail caches before copying them (see [Thumbnails](#thumbnails)).

For second-screen backgrounds, copy images from your chosen variant into `backgrounds/second_screen`. Only one variant can be installed per game; copying a different variant overwrites the existing image.

```text
/3ds/
  └── snes9x_3ds/
      ├── backgrounds/
      │   ├── game_screen/
      │   │   ├── Super Mario World.png
      │   │   └── ...
      │   └── second_screen/
      │       ├── Super Mario World.png
      │       └── ...
      ├── cheats/
      │   ├── Super Mario World.chx
      │   └── ...
      ├── defaults/
      │   ├── overlay.png
      │   ├── game_screen.png
      │   └── second_screen.png
      ├── overlays/
      │   ├── Super Mario World.png
      │   └── ...
      └── thumbnails/
          ├── cover_us-style.cache
          ├── gameplay.cache
          └── ...
```

### Thumbnails

Thumbnail files in `dist/thumbnails` are gzip-compressed. For manual installation, extract each `.cache.gz` file to `.cache` and place it in `thumbnails` as shown above.

You can install several caches and choose one under **Emulator > Game Thumbnail**.

### Display options

In **Settings > On-Screen Display**, choose a mode for **Game Screen Overlay**, **Game Screen BG**, and **Second Screen BG**:

| Mode | What is shown |
| --- | --- |
| Off | No image |
| Default | The image from `defaults`, or the built-in image if no override is present |
| Game or default | The matching game image, or the default if none is available |
| Game only | The matching game image; hidden if none is available |

### Default images

To replace a built-in default, put a PNG at the matching path below, relative to `/3ds/snes9x_3ds` on your SD card:

| Category | Default override path |
| --- | --- |
| Game Screen Overlay | `defaults/overlay.png` |
| Game Screen BG | `defaults/game_screen.png` |
| Second Screen BG | `defaults/second_screen.png` |

Each override is optional.

## Add your own images

If you want to add or replace images:

- Use PNG format
- Use the recommended image sizes below (existing files can serve as templates)

| Image | Recommended size |
| --- | --- |
| Game Screen Overlay | 506 x 256 px for Auto-Fit Bezel |
| Game Screen BG | 400 x 240 px; 448 x 256 px for 3D |
| Second Screen BG | 320 x 240 (top screen: 400 x 240) |

### Game filenames

Name per-game images after the ROM, without region or revision tags.

Example:

- ROM: `Donkey Kong Country (USA) (V1.2) [!].sfc`
- Image filename: `Donkey Kong Country.png`

This lets one image match multiple regions and revisions.

The emulator's [name mappings](src/mappings.txt) let games with different regional titles share the same assets. For example, `Kirby's Fun Pak (Europe).sfc` uses `Kirby Super Star.png`. 

To use a separate image for a mapped regional title, rename the ROM to a name not listed in the mappings and give the image the same name. For example, `Kirby's Fun Pak - PAL.sfc` would use `Kirby's Fun Pak - PAL.png`.

## Add your own cheat files

Use a plain-text `.chx` file with one cheat per line in the format `Y/N,Code,Name`:

```text
N,7E00DC04,Example cheat
```

- `Y/N`: enabled (`Y`) or disabled (`N`)
- `Code`: Game Genie (example: `F38B-6DA4`) or Pro Action Replay (example: `7E00DC04`). Join multiple codes for one cheat with `+` (example: `7E1E6314+7E1E6514`).
- `Name`: short cheat label shown in the emulator

Use codes for your ROM's region and revision. Enable the cheats you want in the emulator's **Cheats** tab.

Put cheat files in `/3ds/snes9x_3ds/cheats` on your SD card, using the same [game filename rules](#game-filenames) as per-game images:

- `Donkey Kong Country.chx` matches `Donkey Kong Country (USA) (V1.2) [!].sfc`
- `Donkey Kong Country (USA) (V1.2) [!].chx` will **not** match

## Licensing

The repository [`LICENSE`](LICENSE) (MIT) applies to repository-authored code
and documentation.

Third-party images/cheats keep their original source terms. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Credits

- [nailbomb-rp](https://github.com/nailbomb-rp) for [pal-snes-covers](https://github.com/nailbomb-rp/pal-snes-covers)
- [ScreenScraper](https://screenscraper.fr) and [LaunchBox Games Database](https://gamesdb.launchbox-app.com/) for title, gameplay, cart and additional boxart images
- [libretro-database](https://github.com/libretro/libretro-database/tree/master/cht/Nintendo%20-%20Super%20Nintendo%20Entertainment%20System) for cheats
- [GameHacking.org](https://gamehacking.org/system/snes/) for additional cheats
