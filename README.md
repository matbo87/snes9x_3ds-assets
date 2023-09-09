# snes9x_3ds-assets

Cheats and images for [snes9x_3ds Emulator](https://github.com/matbo87/snes9x_3ds/releases).

- Sets are already trimmed. I tried to filter out any hacks, betas, prototypes or unlicensed games.
- Focus was primarily on usa and europe games, so you won't find many japanese exclusive titles here.
- Boxarts are in PAL-style (including US exclusives), to keep it more consistent
- Providing missing content or any kind of feedback is welcome


## Download
You can find most recent versions for each set [here](https://github.com/matbo87/snes9x_3ds-assets/releases).


## Usage
Each set is optional. For example you can only use thumbnails/boxarts and just skip the other ones. 
Put your unzipped set to **3ds/snes9x_3ds** on your SD card.

Make sure, your folder structure ends up looking something like this:
```
3ds/
  └── snes9x_3ds/
      ├── borders/
      │   └── ...
      └── cheats/
          └── ...
      └── thumbnails/
          └── boxart
          		└── ...

```

### Add your own images

If you would like to add or replace images, there are some things you may consider for best results:
- Images must be PNG format (8Bit/256 colors for best performance, use tools like tinypng)
- Keep image dimensions small (see provided sets for orientation)
- Use **trimmed** basename -> no region, revision or similar metadata
  - Example: For the game **Donkey Kong Country (USA) (V1.2) [!].sfc** you would name your image **Donkey Kong Country.png**. This ensures that the image can also be assigned for other game versions such as **Donkey Kong Country (E).smc**.

```
3ds/
  └── snes9x_3ds/
      ├── borders/
      │   └── Donkey Kong Country.png
      ├── cheats/
      │   └── Donkey Kong Country.chx
      ├── covers/
      │   └── Donkey Kong Country.png
      └── thumbnails/
          ├── boxart/
          │   └── D/
          │       └── Donkey Kong Country.png
          ├── gameplay/
          │   └── D/
          │       └── Donkey Kong Country.png
          └── title/
              └── D/
                  └── Donkey Kong Country.png
```

### Add your own cheat files
.cht and chx format is supported. The latter is probably more suitable for you because you can edit it easily with any text editor. Each line in the .chx cheat file corresponds to one cheat, and is of the following format:

    [Y/N],[CheatCode],[Name]

- [Y/N] represents whether the cheat is enabled. Whenever you enable/disable it in the emulator, the .chx file will be modified to save your changes.
- [CheatCode] must be a Game Genie or a Pro Action Replay code. A Game Genie code looks like this: **F38B-6DA4**. A Pro-Action Replay code looks like this: **7E00DC04**.
- [Name] is a short name that represents this cheat. Since this will appear as a single line in the emulator, keep it short.

Please consider that the cheat filename is also a shortened version of the actual ROM filename. 
If you have the same cheat file in .cht and .chx format, only the .chx file will be effective. 

**Donkey Kong Country.chx** will match for **Donkey Kong Country (USA) (V1.2) [!].sfc**

**Donkey Kong Country (USA) (V1.2) [!].chx** won't match for **Donkey Kong Country (USA) (V1.2) [!].sfc** 


## Credits
- HarkOn for his [chx collection](https://gbatemp.net/threads/chx-file-collection-for-the-snes9x_3ds.591137/) 
- dohclude for his [cht cheat file collection](https://gbatemp.net/threads/cheats-for-snes9x-gx.149024/)
- nailbomb-rb for his [pal-snes-covers](https://github.com/nailbomb-rp/pal-snes-covers)
- emumovies for title and gameplay thumbnails
