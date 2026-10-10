"""Boot a patched disc with only a GameCube pad (and/or a Wii Remote + extension) and check the hook over GDB."""
import os, sys, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *
STATE = 0x80002A00
MGR = 0x8069e040 - 0x60f8     # r13 - 0x60f8 -> Remocon manager pointer

class Probe:
    def __init__(self):
        self.g = None
    def conn(self):
        for _ in range(20):
            try:
                self.g = Gdb(timeout=8); return
            except Exception:
                time.sleep(2)
        raise RuntimeError('no gdb')
    def read(self, a, n):
        for _ in range(12):
            try:
                if self.g is None: self.conn()
                self.g.halt()
                d = self.g.read(a, n)
                return d
            except Exception as e:
                try: self.g.close()
                except Exception: pass
                self.g = None; time.sleep(1)
        raise RuntimeError('read failed')
    def go(self):
        try: self.g.resume()
        except Exception: pass
    def snap(self):
        """-> dict of hook + game state for channel 0"""
        st = self.read(STATE, 0x60)
        magic, prev_hold, px, py = struct.unpack('>IIii', st[:16])
        sw = struct.unpack('>II', st[16:24]); src, frames = struct.unpack('>II', st[0x20:0x28])
        mgr = struct.unpack('>I', self.read(MGR, 4))[0]
        out = dict(magic=magic, hold=prev_hold, ptr=(px, py), swing=sw, src=src, frames=frames, mgr=mgr)
        if mgr:
            arr = struct.unpack('>I', self.read(mgr + 0x1c, 4))[0]
            r0 = struct.unpack('>I', self.read(arr, 4))[0]
            b = self.read(r0, 0x900)
            u = lambda o: struct.unpack('>I', b[o:o+4])[0]
            f = lambda o: struct.unpack('>f', b[o:o+4])[0]
            out.update(r0=r0, ch=u(4), count=u(0x854), mode=b[0x70], rhold=u(0x14), acc=(f(0x20), f(0x24), f(0x28)),
                       nacc=(f(0x7C), f(0x80), f(0x84)), pos=(f(0x34), f(0x38)))
        self.go()
        return out

if __name__ == '__main__':
    disc = sys.argv[1]
    wm = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    L = Lab('pad').setup(wiimotes=wm, ext=os.environ.get('LAB_EXT','Nunchuk')); L.start(disc, log='shots/pad.log')
    P = Probe()
    try:
        t0 = time.time()
        while time.time() - t0 < 200:
            time.sleep(8)
            s = P.snap()
            print(int(time.time() - t0), {k: (hex(v) if isinstance(v, int) and k in ('magic', 'mgr', 'r0', 'rhold', 'hold') else v) for k, v in s.items()}, flush=True)
            if s.get('magic') and s.get('mgr') and s.get('count', 0) > 0: break
        pp = os.environ.get('LAB_PIPE', 'gc1')
        for label, act in (('A', lambda: L.send(pp, 'PRESS A')), ('A+Z', lambda: L.send(pp, 'PRESS Z')),
                           ('release', lambda: (L.send(pp, 'RELEASE A'), L.send(pp, 'RELEASE Z'))),
                           ('L', lambda: L.send(pp, 'PRESS L')), ('L up', lambda: L.send(pp, 'RELEASE L')),
                           ('R', lambda: L.send(pp, 'PRESS R')), ('R up', lambda: L.send(pp, 'RELEASE R'))):
            act(); time.sleep(0.4); s = P.snap()
            print(label, hex(s.get('rhold', 0)), 'src', s['src'], 'swing', s['swing'], 'acc', s.get('acc'), 'nacc', s.get('nacc'), flush=True)
    finally:
        L.stop()
