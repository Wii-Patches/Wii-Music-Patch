"""Finds the hook's anchors in another release's main.dol by matching USA code (tools/sig.py)."""
import struct
import sys
from dol import Dol
from sig import find_unique
from regions import REGIONS, call_sites, types_table

USA = REGIONS['R64E01']
# (name, USA address, instructions to match from the entry)
ANCHORS = (('kpad_read', USA.kpad_read, 48), ('wpad_probe', USA.wpad_probe, 36), ('si_get_type', USA.si_get_type, 28),
           ('os_disable', USA.os_disable, 10), ('os_restore', USA.os_restore, 10))


def find_region(path):
    usa = Dol('%s' % USA_DOL)
    dol = Dol(path)
    out = {}
    for name, addr, n in ANCHORS:
        out[name] = find_unique(usa, dol, addr, 0, n)
    out['si_busy'] = types_table(dol, out['si_get_type']) - 0x18
    return out


USA_DOL = None

if __name__ == '__main__':
    USA_DOL = sys.argv[1]
    for p in sys.argv[2:]:
        r = find_region(p)
        d = Dol(p)
        print(p.split('/')[-3], {k: '0x%08X' % v for k, v in r.items()},
              'kpad sites', len(call_sites(d, r['kpad_read'])), 'probe sites', len(call_sites(d, r['wpad_probe'])))
