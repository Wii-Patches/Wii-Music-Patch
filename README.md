<p align="center"><img src="assets/logo.png" width="360"></p>

# Wii Music – GameCube / Classic Controller patch

Lets Wii Music (USA, Europe, Japan, Korea) be played with a GameCube controller
or a Classic Controller instead of a Wii Remote + Nunchuk.

| Wii Remote | GameCube / Classic |
|---|---|
| A | A |
| B | B |
| 1 | X |
| 2 | Y |
| L / R | swing (left / right hand): light press of the GameCube triggers, or L / R / ZL / ZR on Classic |
| HOME | Z (GameCube) |
| + (pause) | Start (GameCube) |
| − / + | full click of GameCube L / R; − / + (Classic) |
| D-pad | D-pad |
| Nunchuk stick | left stick |
| IR pointer | right stick (C-stick) |

DK Bongos are not supported.

The patcher also points the game's Wii Shop update-server URLs (`wus.wapp.wii.com`) at RiiConnect24 (`wus.wii.rc24.xyz`).

## Use

**GUI** (macOS, Windows, Linux builds come from the *Build GUI patcher* workflow, with `wit` bundled):
drop a `.wbfs` or `.iso` on the window. The image is patched in place and the original is kept as
`<name>.bak`.

**Command line:**

    python3 tools/patch_disc.py "Wii Music (USA).wbfs" [--no-gc] [--no-cc]   # in place, needs wit
    python3 tools/wmpatch.py disc "Wii Music.rvz" "Wii Music (patched).iso"  # to a new file, needs wit
    python3 tools/wmpatch.py dol main.dol main_patched.dol

The patcher detects the region, adds one text section at 0x80001820 and redirects every
`KPADRead` / `WPADProbe` call to it (source: `src/gcpad.c`). It enables SI polling itself,
since the game does not use libpad. Prebuilt code is in `tools/prebuilt/`, so no PowerPC
toolchain is needed to patch; rebuild it with `python3 tools/wmpatch.py prebuilt` (devkitPPC).

`python3 tools/check.py` (run by CI) checks the prebuilt code is present and current.

## Status

Checked in Dolphin over GDB (memory inspection only):
- USA, Europe, Japan, Korea patched builds boot; with only a GameCube pad connected the hook
  activates and A reaches the game's Wii Remote hold word as 0x800.
- USA: Classic Controller path, Nunchuk-mode connection, and real Wii Remote passthrough.

Not verified:
- Whether the synthesized swing motion is recognised by every instrument's gesture detector.
- Menu / pointer navigation with a pad only, and the HOME Menu actually opening.
- Real hardware.
