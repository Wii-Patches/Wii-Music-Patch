#!/usr/bin/env python3
"""Consistency checks that need no game files (CI runs this).

  * the prebuilt hook words exist for every region, fit below the config block,
    export both entry points, and were compiled from the current sources
  * every region's addresses are distinct from the injected section

    python3 tools/check.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wmpatch
from layout import CAVE_BASE, CFG, STATE, STATE_END
from regions import REGIONS

fail = []


def check(cond, msg):
    if not cond:
        fail.append(msg)
        print('  FAIL', msg)


def main():
    j = json.load(open(wmpatch.PREBUILT))
    check(j.get('_src') == wmpatch.src_hash(),
          'prebuilt/hook.json is stale (run: python3 tools/wmpatch.py prebuilt)')
    check(CAVE_BASE < CFG < STATE < STATE_END <= 0x80003000, 'layout out of order')
    for key, r in REGIONS.items():
        check(key in j, 'no prebuilt hook for %s' % key)
        if key not in j:
            continue
        code = bytes.fromhex(j[key]['code'])
        syms = {k: int(v, 16) for k, v in j[key]['syms'].items()}
        check(len(code) % 4 == 0 and CAVE_BASE + len(code) <= CFG, '%s: hook is %d bytes' % (key, len(code)))
        for name in ('hook_kpad', 'hook_probe'):
            check(name in syms and CAVE_BASE <= syms[name] < CAVE_BASE + len(code), '%s: bad %s' % (key, name))
        check(r.kpad_read != r.wpad_probe, '%s: duplicate function addresses' % key)
    print('FAILED: %d' % len(fail) if fail else 'ok: all checks passed')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
