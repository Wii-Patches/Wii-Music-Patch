import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *
def u32(g,a): return struct.unpack('>I', g.read(a,4))[0]
L = Lab('base').setup(ext=sys.argv[2] if len(sys.argv)>2 else 'Nunchuk'); L.start(sys.argv[1], log='shots/base.log')
try:
    time.sleep(8)
    g = Gdb()
    time.sleep(40)
    for i in range(8):
        g.halt()
        mgr = u32(g, 0x8069e040 - 0x60f8)
        print('t', i, 'mgr %08x' % mgr, end=' ')
        if mgr:
            arr = u32(g, mgr + 0x1c)
            r0 = u32(g, arr)
            print('remocon0 %08x' % r0, 'ch', u32(g, r0+4), 'count', u32(g, r0+0x854), 'mode %02x' % g.read(r0+0x70,1)[0], 'hold %08x' % u32(g, r0+0x14))
        else: print()
        g.resume()
        L.press('wm1', 'A', 0.3); time.sleep(4)
finally:
    L.stop()
