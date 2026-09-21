# snes9x_3ds-assets

Cheats and image assets for the [snes9x_3ds emulator](https://github.com/matbo87/snes9x_3ds/releases).

The sets follow a 1G1R-style selection:
- No hacks, betas, prototypes or unlicensed games
- Region preference: **USA > Europe > Japan**

Main focus is USA + PAL titles. Japanese exclusives are only partially covered.

## Download
Download the latest release packages [here](https://github.com/matbo87/snes9x_3ds-assets/releases).

You can also download individual files directly from the [`dist`](dist) folder.

## Current status and scope
Base list for the current set: [`src/file-list.txt`](src/file-list.txt)

Per-game asset coverage: [`ASSET_OVERVIEW.md`](ASSET_OVERVIEW.md)

### Asset variants
| Variant | Count | Notes |
| --- | ---: | --- |
| Gameplay | 1000 | Used for `thumbnails/gameplay.cache` and `backgrounds/game_screen` |
| Title | 1000 | Used for `thumbnails/title.cache` |
| Boxart (1g1r) | 1000 | Used for `thumbnails/boxart_1g1r.cache`<br>Original regional covers, full coverage |
| Boxart (pal-style) | 1000 | Used for `thumbnails/boxart_pal-style.cache` and `backgrounds/second_screen_boxart`<br>PAL-style covers where available; titles in [`src/fallback/boxart_pal-style.cache.txt`](src/fallback/boxart_pal-style.cache.txt) use their original cover instead |
| Console (EU/JP) | 840 | Used for `backgrounds/second_screen_console/eu_jp`<br>Missing titles: [`src/missing/console_eu_jp.txt`](src/missing/console_eu_jp.txt) |
| Console (USA) | 723 | Used for `backgrounds/second_screen_console/us`<br>Missing titles: [`src/missing/console_us.txt`](src/missing/console_us.txt) |
| Cheats | 861 | Used for `cheats` (`.chx` format)<br>Missing titles: [`src/missing/cheats.txt`](src/missing/cheats.txt) |

### Regional scope
- USA + PAL total set: **785 / 785** -> [`src/file-list_USA.txt`](src/file-list_USA.txt), [`src/file-list_Europe.txt`](src/file-list_Europe.txt)
- Japanese exclusives: **215 / 977** covered -> [`src/file-list_Japan.txt`](src/file-list_Japan.txt)

### Overlays
Overlays are currently provided as demo examples only (`_default.png` and `Super Mario World.png`).

Broad overlay coverage is not planned.

## Usage
Each set is optional. You can use only the parts you want.

Copy the unzipped files to `3ds/snes9x_3ds` on your SD card. The final structure should look like this:

```text
3ds/
  └── snes9x_3ds/
      ├── backgrounds/
      │   ├── game_screen/
      │   │   ├── _default.png
      │   │   ├── Super Mario World.png
      │   │   └── ...
      │   └── second_screen/
      │       ├── _default.png
      │       ├── Super Mario World.png
      │       └── ...
      ├── cheats/
      │   └── Super Mario World.chx
      │   └── ...
      ├── overlays/
      │   ├── _default.png
      │   ├── Super Mario World.png
      │   └── ...
      └── thumbnails/
          ├── boxart.cache
          ├── gameplay.cache
          └── title.cache
```

When present, `_default.png` overrides the built-in default image in `snes9x_3ds` for that category.

### Second screen option
For `backgrounds/second_screen`, you can choose one of these styles:

- `second_screen_boxart`
- `second_screen_console/eu_jp`
- `second_screen_console/us`

Pick the style you prefer, then copy/rename it to:

- `backgrounds/second_screen`

## Add your own images
If you want to add or replace images:

- Use PNG format
- Keep image dimensions small (use existing files as reference)
- Pre-dither background images for best visual quality (RGB565 texture)
- Use the trimmed game name as filename (no region/revision tags)

Example:

- ROM: `Donkey Kong Country (USA) (V1.2) [!].sfc`
- Image filename: `Donkey Kong Country.png`

This lets one file match multiple ROM variants (for example USA/EU revisions).

## Add your own cheat files
Both `.cht` and `.chx` are supported. `.chx` is easier to edit manually.

chx format (one line per cheat):

```text
[Y/N],[CheatCode],[Name]
```

- `[Y/N]`: enabled (`Y`) or disabled (`N`)
- `[CheatCode]`: Game Genie (example: `F38B-6DA4`) or Pro Action Replay (example: `7E00DC04`)
- `[Name]`: short cheat label shown in the emulator

Cheat filenames should also use the trimmed basename.

- `Donkey Kong Country.chx` matches `Donkey Kong Country (USA) (V1.2) [!].sfc`
- `Donkey Kong Country (USA) (V1.2) [!].chx` will **not** match

If both `.cht` and `.chx` exist for the same game, `.chx` is used.

## Licensing
The repository [`LICENSE`](LICENSE) (MIT) applies to repository-authored code
and documentation.

Third-party images/cheats keep their original source terms. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Credits
- [nailbomb-rb](https://github.com/nailbomb-rp) for [pal-snes-covers](https://github.com/nailbomb-rp/pal-snes-covers)
- [ScreenScraper](https://screenscraper.fr) and [LaunchBox Games Database](https://gamesdb.launchbox-app.com/) for title, gameplay, cart and additional boxart images
- HarkOn for the [CHX collection](https://gbatemp.net/threads/chx-file-collection-for-the-snes9x_3ds.591137/)
- dohclude for the [legacy CHT cheat collection](https://gbatemp.net/threads/cheats-for-snes9x-gx.149024/)
- [libretro-database](https://github.com/libretro/libretro-database/tree/master/cht/Nintendo%20-%20Super%20Nintendo%20Entertainment%20System) for additional cheat sources
