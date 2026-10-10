"""Boot a patched disc of any region with a GC pad only; check the hook state over GDB."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *
from t_pad import Probe, STATE
L = Lab('reg').setup(wiimotes=0, ext='Nunchuk'); L.start(sys.argv[1], log='shots/reg.log')
P = Probe()
try:
    t0 = time.time(); ok = False
    while time.time() - t0 < 150:
        time.sleep(8)
        st = P.read(STATE, 0x60); P.go()
        magic, = struct.unpack('>I', st[:4])
        print(int(time.time()-t0), hex(magic), flush=True)
        if magic == 0x574d5031: ok = True; break
    if ok:
        L.send(os.environ.get('LAB_PIPE', 'gc1'), 'PRESS A'); time.sleep(1)
        st = P.read(STATE, 0x60); P.go()
        magic, prev_hold = struct.unpack('>II', st[:8]); src, frames = struct.unpack('>II', st[0x20:0x28])
        print('RESULT hold', hex(prev_hold), 'src', src, 'frames', frames)
finally:
    L.stop()
