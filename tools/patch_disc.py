#!/usr/bin/env python3
"""Command-line twin of the GUI: patch a .wbfs/.iso in place.

    python3 tools/patch_disc.py "Wii Music (USA).wbfs" [--no-gc] [--no-cc]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument('image')
    ap.add_argument('--no-gc', action='store_true', help='leave out GameCube controller support')
    ap.add_argument('--no-cc', action='store_true', help='leave out Classic Controller support')
    a = ap.parse_args()
    flags = (0 if a.no_gc else 1) | (0 if a.no_cc else 2)
    ok = []
    disc.run_patch(a.image, print, lambda good, msg: ok.append(good), flags)
    sys.exit(0 if ok and ok[0] else 1)


if __name__ == '__main__':
    main()
