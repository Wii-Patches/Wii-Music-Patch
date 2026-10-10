"""Wrap a DOL's sections in a bare big-endian PowerPC ELF so headless Ghidra can load it."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dolread import Dol
d = Dol(sys.argv[1])
bss_a, bss_s = struct.unpack('>II', d.d[0xD8:0xE0])
segs = []
for i, o, a, s in d.secs():
    segs.append((a, d.d[o:o + s], 5 if i < 7 else 6, s))
if bss_s:
    segs.append((bss_a, b'', 6, bss_s))
n = len(segs); phoff = 52; dataoff = phoff + 32 * n
ph = bytearray(); body = bytearray()
for a, data, fl, memsz in segs:
    body += b'\0' * ((-(dataoff + len(body))) % 16)
    ph += struct.pack('>8I', 1, dataoff + len(body), a, a, len(data), memsz, fl, 16)
    body += data
hdr = b'\x7fELF' + bytes([1, 2, 1, 0]) + bytes(8) + struct.pack('>HHIIIIIHHHHHH', 2, 20, 1, d.entry, phoff, 0, 0, 52, 32, n, 0, 0, 0)
open(sys.argv[2], 'wb').write(hdr + ph + body)
