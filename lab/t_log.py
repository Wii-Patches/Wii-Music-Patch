import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *
from t_pad import Probe
STATE = 0x80002A00
L = Lab('log').setup(wiimotes=1, ext='Nunchuk'); L.start(sys.argv[1], log='shots/log.log')
P = Probe()
def ring():
    d = P.read(STATE + 0x1FC, 4 + 0x200 - 4 + 4)
    idx = struct.unpack('>I', d[:4])[0]
    f = struct.unpack('>96f', P.read(STATE + 0x200, 96 * 4)); P.go()
    return idx, [f[((idx - 16 + i) & 15) * 6:((idx - 16 + i) & 15) * 6 + 6] for i in range(16)]
try:
    time.sleep(8); P.conn()
    t0=time.time()
    while time.time()-t0 < 150:
        time.sleep(5)
        try:
            idx, fr = ring()
            print('idx', idx, flush=True)
            if idx > 20: break
        except Exception as e: print('wait', e, flush=True)
    print('ready idx', idx)
    for label, btn in (('wiimote Shake Z', 'D_DOWN'), ('wiimote Swing Down', 'D_UP'), ('nunchuk Shake Z', 'Z'), ('nunchuk Swing Down', 'START')):
        L.send('wm1', 'PRESS ' + btn); time.sleep(0.12)
        idx, fr = ring()
        print(label, 'idx', idx)
        for f in fr: print('  ', ' '.join('%6.2f' % x for x in f))
        L.send('wm1', 'RELEASE ' + btn); time.sleep(1.5)
finally:
    L.stop()
