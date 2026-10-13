"""Log what a real (emulated) Wii Remote + Nunchuk reports during a shake / swing, with a -DLOGACC build.

    python3 lab/t_log.py logacc.iso
"""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *
from t_pad import Probe
STATE = 0x80002A00
N = 24
L = Lab('log').setup(wiimotes=1, ext='Nunchuk'); os.makedirs('shots', exist_ok=True); L.start(sys.argv[1], log='shots/log.log')
P = Probe()
def ring():
    idx = struct.unpack('>I', P.read(STATE + 0x1FC, 4))[0]
    f = struct.unpack('>%df' % (N * 10), P.read(STATE + 0x200, N * 40)); P.go()
    return idx, [f[((idx - N + i) % N) * 10:((idx - N + i) % N) * 10 + 10] for i in range(N)]
try:
    time.sleep(8); P.conn()
    t0 = time.time()
    while time.time() - t0 < 150:
        time.sleep(5)
        try:
            idx, fr = ring()
            print('idx', idx, flush=True)
            if idx > 20: break
        except Exception as e: print('wait', e, flush=True)
    print('ready idx', idx)
    print('cols: acc xyz, acc_value, acc_speed | nacc xyz, nacc_value, nacc_speed')
    for label, btn in (('wiimote Shake Z', 'D_DOWN'), ('wiimote Swing Down', 'D_UP'), ('nunchuk Shake Z', 'Z'), ('nunchuk Swing Down', 'START')):
        L.send('wm1', 'PRESS ' + btn); time.sleep(0.12)
        idx, fr = ring()
        print(label, 'idx', idx)
        for f in fr: print('  ', ' '.join('%7.2f' % x for x in f[:5]), '|', ' '.join('%7.2f' % x for x in f[5:]))
        L.send('wm1', 'RELEASE ' + btn); time.sleep(1.5)
finally:
    L.stop()
