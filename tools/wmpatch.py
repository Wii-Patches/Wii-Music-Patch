#!/usr/bin/env python3
"""Add GameCube controller and Classic Controller support to Wii Music (Wii).

    wmpatch.py dol  <main.dol> <out.dol>        patch an extracted main.dol
    wmpatch.py disc <game.iso|wbfs|rvz> <out>   patch a whole disc (needs wit)

The hook is one extra DOL text section at 0x80001820 plus every `bl KPADRead` / `bl WPADProbe`
rewritten to call it (src/gcpad.c).
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_hook                                      # noqa: E402
from dol import Dol                                    # noqa: E402
from layout import CAVE_BASE, CFG, STATE, STATE_END    # noqa: E402
from ops import Blob, Feature, Patch, apply_static, b_insn   # noqa: E402
from regions import REGIONS, call_sites, matches                # noqa: E402

PREBUILT = os.path.join(HERE, 'prebuilt', 'hook.json')
CHOICES = (('GameCube controller + Classic Controller', 'both', 3),
           ('GameCube controller', 'gc', 1),
           ('Classic Controller', 'cc', 2))


def hook_blob(region, rebuild=False):
    """(code bytes, {symbol: address}) for a region: the shipped words, or a fresh devkitPPC build."""
    key = region.disc_id
    if not rebuild and os.path.exists(PREBUILT):
        j = json.load(open(PREBUILT))
        if key in j and key != '_src':
            e = j[key]
            return bytes.fromhex(e['code']), {k: int(v, 16) for k, v in e['syms'].items()}
    return build_hook.build(region.consts)


def feature(region, dol, flags=3):
    code, syms = hook_blob(region)
    assert CAVE_BASE + len(code) <= CFG, 'hook too big: 0x%X' % len(code)
    ops = []
    for target, sym, note in ((region.kpad_read, 'hook_kpad', 'KPADRead call'), (region.wpad_probe, 'hook_probe', 'WPADProbe call')):
        sites = call_sites(dol, target)
        assert sites, 'no call sites for %s' % note
        for site in sites:
            ops.append(Patch(site, struct.pack('>I', b_insn(syms[sym], site, link=True)),
                             struct.pack('>I', b_insn(target, site, link=True)), note))
    ops.append(Blob(CAVE_BASE, code, 'pad hook'))
    ops.append(Blob(CFG, struct.pack('>I', flags) + bytes(STATE_END - CFG - 4), 'hook flags and state'))
    return Feature('pads', 'GameCube / Classic Controller', region.disc_id, ops)


def detect_region(dol, disc_id=None):
    for r in ([REGIONS[disc_id]] if disc_id else REGIONS.values()):
        try:
            if matches(r, dol) and not feature(r, dol).check_pristine(dol):
                return r
        except AssertionError:
            continue
    raise SystemExit('not a clean retail Wii Music main.dol (other build, or already patched)')


def patch_dol(src, dst, disc_id=None, flags=3):
    dol = Dol(src)
    region = detect_region(dol, disc_id)
    size = apply_static(dol, [feature(region, dol, flags)])
    dol.save(dst)
    return region, size


def patch_disc(src, dst, flags=3):
    wit = shutil.which('wit') or sys.exit('wit (Wiimms ISO Tools) is required for disc patching')
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as t:
        ex = os.path.join(t, 'x')
        subprocess.run([wit, 'extract', src, ex, '--psel', 'data', '-q'], check=True)
        d = os.path.join(ex, 'sys', 'main.dol')
        region, size = patch_dol(d, d, flags=flags)
        kind = os.path.splitext(dst)[1].lstrip('.').lower()
        fmt = {'wbfs': '--wbfs', 'iso': '--iso'}.get(kind) or sys.exit('output must be .iso or .wbfs')
        subprocess.run([wit, 'copy', ex, dst, fmt, '--overwrite', '-q'], check=True)
    return region, size


def src_hash():
    """Digest of everything the prebuilt words are compiled from (tools/check.py compares it)."""
    h = hashlib.sha256()
    for p in (os.path.join(HERE, '..', 'src', 'gcpad.c'), os.path.join(HERE, '..', 'src', 'link.ld'),
              os.path.join(HERE, 'regions.py'), os.path.join(HERE, 'layout.py')):
        h.update(open(p, 'rb').read())
    return h.hexdigest()


def write_prebuilt():
    out = {'_src': src_hash()}
    for k, r in REGIONS.items():
        code, syms = build_hook.build(r.consts)
        out[k] = dict(code=code.hex(), syms={a: '0x%X' % b for a, b in syms.items()})
    os.makedirs(os.path.dirname(PREBUILT), exist_ok=True)
    json.dump(out, open(PREBUILT, 'w'), indent=1)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['dol'] and len(a) == 3:
        print('%s: injected %d bytes' % patch_dol(a[1], a[2]))
    elif a[:1] == ['disc'] and len(a) == 3:
        print('%s: injected %d bytes' % patch_disc(a[1], a[2]))
    elif a == ['prebuilt']:
        write_prebuilt()
    else:
        sys.exit(__doc__)
