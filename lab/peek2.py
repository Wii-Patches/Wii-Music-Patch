import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *
from t_pad import Probe
MGR = 0x8069e040 - 0x60f8
L = Lab('peek').setup(wiimotes=int(os.environ.get('LAB_WM', 1)), ext=os.environ.get('LAB_EXT', 'Nunchuk')); L.start(sys.argv[1], log='shots/peek.log')
P = Probe()
try:
    time.sleep(8); P.conn()
    t0 = time.time()
    while time.time() - t0 < int(sys.argv[2]):
        time.sleep(6)
        try:
            mgr = struct.unpack('>I', P.read(MGR, 4))[0]
            if mgr:
                arr = struct.unpack('>I', P.read(mgr + 0x1c, 4))[0]; r0 = struct.unpack('>I', P.read(arr, 4))[0]
                b = P.read(r0, 0x90)
                print(int(time.time() - t0) + 8, 'count', struct.unpack('>I', P.read(r0 + 0x854, 4))[0], 'mode', b[0x70], 'hold %08x' % struct.unpack('>I', b[0x14:0x18])[0], flush=True)
            else: print(int(time.time() - t0) + 8, 'no mgr', flush=True)
        except Exception as e: print('err', e, flush=True)
        P.go()
finally:
    L.stop()
