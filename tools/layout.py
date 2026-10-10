"""Where the pad hook lives.

0x80001800-0x80003000 is the Wii's boot-time scratch area.  Every access to
0x8000xxxx in the retail DOLs is at 0x80003000 or above (checked by
tools/verify.py), so the patcher adds one text section there.  The first 0x20
bytes are skipped: the word at 0x80001800 is overwritten by the OS early on.

    0x80001820  the hook routine
    0x80002800  tuning tables (CFG) -- orientation vectors, thresholds, button maps
    0x80002A00  per-channel state (0x40 bytes x 4)
"""
CAVE_BASE = 0x80001820
CAVE_LIMIT = 0x80003000

CFG = 0x80002800
STATE = 0x80002A00
STATE_END = 0x80002C00
