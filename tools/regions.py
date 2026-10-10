"""Per-release addresses of the game functions and SI variables the hook uses.

USA (R64E01) was read in Ghidra.  Other releases are found by matching the surrounding code
(tools/sig.py) against the USA DOL; see find_region().
"""
import struct


class Region:
    def __init__(self, disc_id, name, kpad_read, wpad_probe, si_get_type, os_disable, os_restore, si_busy):
        self.disc_id, self.name = disc_id, name
        self.kpad_read, self.wpad_probe, self.si_get_type = kpad_read, wpad_probe, si_get_type
        self.os_disable, self.os_restore = os_disable, os_restore
        self.si_busy = si_busy              # si:: transfer state; poll shadow is +4, device-type table is +0x18

    @property
    def consts(self):
        return dict(FN_KPADREAD=self.kpad_read, FN_WPADPROBE=self.wpad_probe, FN_SIGETTYPE=self.si_get_type,
                    FN_OSDISABLE=self.os_disable, FN_OSRESTORE=self.os_restore,
                    SI_BUSY=self.si_busy, SI_SHADOW=self.si_busy + 4, SI_TYPES=self.si_busy + 0x18)

    def __repr__(self):
        return '%s (%s)' % (self.name, self.disc_id)


# kpad_read, wpad_probe, si_get_type, os_disable, os_restore, si_busy.  Europe and Japan were found by
# signature (tools/find_regions.py); Korea's KPADRead has a different stack frame, so it was located by its
# WPADProbe call (same offset, +0x84) and the 0x538-byte per-channel stride.
REGIONS = {
    'R64E01': Region('R64E01', 'USA', 0x80151BF4, 0x8017320C, 0x80168EEC, 0x8015EB9C, 0x8015EBC4, 0x80559480),
    'R64P01': Region('R64P01', 'Europe', 0x80151CF0, 0x80173308, 0x80168FE8, 0x8015EC98, 0x8015ECC0, 0x80559680),
    'R64J01': Region('R64J01', 'Japan', 0x80151BF4, 0x8017320C, 0x80168EEC, 0x8015EB9C, 0x8015EBC4, 0x80556160),
    'R64K01': Region('R64K01', 'Korea', 0x801BDFD0, 0x801AA32C, 0x801A000C, 0x80195CBC, 0x80195CE4, 0x805413A8),
}


def call_sites(dol, target):
    """Addresses of every `bl target` in the DOL's text sections."""
    out = []
    for off, addr, size, idx in dol.secs:
        if idx >= 7:
            continue
        words = struct.unpack('>%dI' % (size // 4), bytes(dol.data[off:off + size]))
        for k, w in enumerate(words):
            if w >> 26 == 18 and (w & 3) == 1:
                d = w & 0x03FFFFFC
                if d & 0x02000000:
                    d -= 0x04000000
                if addr + 4 * k + d == target:
                    out.append(addr + 4 * k)
    return out


def types_table(dol, si_get_type):
    """The device-type table SIGetType indexes: its lis/addi pair loads &Type[0]."""
    w = [struct.unpack('>I', dol.read(si_get_type + 4 * i, 4))[0] for i in range(24)]
    for i, x in enumerate(w):
        if x >> 26 == 15 and (x >> 16) & 31 == 0:           # lis rD, hi
            rd = (x >> 21) & 31
            for y in w[i + 1:i + 14]:
                if y >> 26 == 14 and (y >> 21) & 31 == rd and (y >> 16) & 31 == rd:   # addi rD, rD, lo
                    lo = y & 0xFFFF
                    lo -= 0x10000 if lo & 0x8000 else 0
                    return ((x & 0xFFFF) << 16) + lo
    return None


def matches(region, dol):
    """True when `dol` really is this release: the SI type table SIGetType loads is where the region says."""
    if dol.read(region.si_get_type, 4) is None:
        return False
    return types_table(dol, region.si_get_type) == region.si_busy + 0x18
