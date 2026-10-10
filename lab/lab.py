"""Dolphin test lab for Samba Patch.

A private, resettable Dolphin: its own user folder (config, NAND, saves), input
pipes that scripts write button / stick commands to, and the GDB stub for
reading game memory while the game runs.  Nothing here touches the real Dolphin
user folder.
"""
import os
import shutil
import signal
import socket
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DOLPHIN = '/Applications/Dolphin.app/Contents/MacOS/Dolphin'
GDB_PORT = int(os.environ.get('LAB_GDB', 2371))

DOLPHIN_INI = """[General]
GDBPort = %(gdb)d
[Interface]
ConfirmStop = False
UsePanicHandlers = False
OnScreenDisplayMessages = False
[Core]
CPUCore = %(cpu)d
CPUThread = False
MMU = True
SIDevice0 = %(si0)d
SIDevice1 = %(si1)d
SIDevice2 = 0
SIDevice3 = 0
WiimoteContinuousScanning = False
WiimoteEnableSpeaker = False
OverrideRegionSettings = False
EnableCheats = True
SyncOnSkipIdle = True
AudioBackend = Null
GFXBackend = %(gfx)s
[DSP]
Backend = No Audio Output
DumpAudio = True
[Display]
Fullscreen = False
RenderToMain = False
[Movie]
DumpFrames = True
DumpFramesAsImages = True
[Analytics]
Enabled = False
PermissionAsked = True
[Input]
BackgroundInput = True
"""

GFX_INI = """[Settings]
InternalResolution = 1
ShowFPS = False
Backend = Metal
[Hacks]
EFBToTextureEnable = True
"""

# A GC pad driven entirely by one pipe.
GCPAD = """[GCPad%(n)d]
Device = Pipe/0/gc%(n)d
Buttons/A = `Button A`
Buttons/B = `Button B`
Buttons/X = `Button X`
Buttons/Y = `Button Y`
Buttons/Z = `Button Z`
Buttons/Start = `Button START`
Main Stick/Up = `Axis MAIN Y +`
Main Stick/Down = `Axis MAIN Y -`
Main Stick/Left = `Axis MAIN X -`
Main Stick/Right = `Axis MAIN X +`
C-Stick/Up = `Axis C Y +`
C-Stick/Down = `Axis C Y -`
C-Stick/Left = `Axis C X -`
C-Stick/Right = `Axis C X +`
Triggers/L = `Button L`
Triggers/R = `Button R`
D-Pad/Up = `Button D_UP`
D-Pad/Down = `Button D_DOWN`
D-Pad/Left = `Button D_LEFT`
D-Pad/Right = `Button D_RIGHT`
"""

# Wii Remote 1: emulated, with a Nunchuk plugged in, driven from its own pipe
# (IR pointer from the C stick, A and B as buttons).
WIIMOTE = """[Wiimote%(n)d]
Device = Pipe/0/wm%(n)d
Source = %(src)d
Extension = %(ext)s
Buttons/A = `Button A`
Buttons/B = `Button B`
Buttons/1 = `Button X`
Buttons/2 = `Button Y`
Buttons/+ = `Button START`
Buttons/- = `Button Z`
Buttons/Home = `Button L`
D-Pad/Up = `Button D_UP`
D-Pad/Down = `Button D_DOWN`
D-Pad/Left = `Button D_LEFT`
D-Pad/Right = `Button D_RIGHT`
IR/Up = `Axis C Y +`
IR/Down = `Axis C Y -`
IR/Left = `Axis C X -`
IR/Right = `Axis C X +`
Nunchuk/Buttons/C = `Button R`
Shake/X = `Button D_LEFT`
Shake/Y = `Button D_RIGHT`
Shake/Z = `Button D_DOWN`
Swing/Down = `Button D_UP`
Nunchuk/Shake/Z = `Button Z`
Nunchuk/Swing/Down = `Button START`
Classic/Buttons/A = `Button A`
Classic/Buttons/B = `Button B`
Classic/Buttons/X = `Button X`
Classic/Buttons/Y = `Button Y`
Classic/Buttons/ZL = `Button Z`
Classic/Buttons/ZR = `Button START`
Classic/Triggers/L = `Button L`
Classic/Triggers/R = `Button R`
Classic/D-Pad/Up = `Button D_UP`
Classic/D-Pad/Down = `Button D_DOWN`
Classic/D-Pad/Left = `Button D_LEFT`
Classic/D-Pad/Right = `Button D_RIGHT`
Classic/Left Stick/Up = `Axis MAIN Y +`
Classic/Left Stick/Down = `Axis MAIN Y -`
Classic/Left Stick/Left = `Axis MAIN X -`
Classic/Left Stick/Right = `Axis MAIN X +`
Classic/Right Stick/Up = `Axis C Y +`
Classic/Right Stick/Down = `Axis C Y -`
Classic/Right Stick/Left = `Axis C X -`
Classic/Right Stick/Right = `Axis C X +`
Nunchuk/Stick/Up = `Axis MAIN Y +`
Nunchuk/Stick/Down = `Axis MAIN Y -`
Nunchuk/Stick/Left = `Axis MAIN X -`
Nunchuk/Stick/Right = `Axis MAIN X +`
"""

PIPES = ['gc1', 'gc2', 'wm1', 'wm2', 'hk']


class Lab:
    def __init__(self, name='main', cpu=4):
        self.name = name
        self.root = os.path.join(HERE, 'user-' + name)
        self.cpu = cpu
        self.proc = None
        self.pipes = {}

    # ---- setup -------------------------------------------------------
    def setup(self, wiimotes=1, ext='Nunchuk', fresh=True):
        if fresh and os.path.isdir(self.root):
            shutil.rmtree(self.root)
        cfg = os.path.join(self.root, 'Config')
        os.makedirs(cfg, exist_ok=True)
        os.makedirs(os.path.join(self.root, 'Pipes'), exist_ok=True)
        with open(os.path.join(cfg, 'Dolphin.ini'), 'w') as f:
            f.write(DOLPHIN_INI % dict(gdb=GDB_PORT, cpu=self.cpu, gfx=os.environ.get("LAB_GFX", "Software Renderer"), si0=int(os.environ.get("LAB_SI0", 6)), si1=int(os.environ.get("LAB_SI1", 6))))
        with open(os.path.join(cfg, 'GFX.ini'), 'w') as f:
            f.write(GFX_INI)
        with open(os.path.join(cfg, 'GCPadNew.ini'), 'w') as f:
            f.write(GCPAD % dict(n=1) + GCPAD % dict(n=2))
        with open(os.path.join(cfg, 'WiimoteNew.ini'), 'w') as f:
            for n in range(1, 5):
                f.write(WIIMOTE % dict(n=n, src=1 if n <= wiimotes else 0, ext=ext))
        with open(os.path.join(cfg, 'Hotkeys.ini'), 'w') as f:
            f.write('[Hotkeys]\nDevice = Pipe/0/hk\nGeneral/Take Screenshot = `Button A`\n')
        for p in PIPES:
            path = os.path.join(self.root, 'Pipes', p)
            if not os.path.exists(path):
                os.mkfifo(path)
        return self

    # ---- running -----------------------------------------------------
    def start(self, disc, log=None):
        args = [DOLPHIN, '-u', self.root, '-b', '-e', disc]
        out = open(log, 'w') if log else subprocess.DEVNULL
        self.proc = subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=True)
        for p in PIPES:
            path = os.path.join(self.root, 'Pipes', p)
            for _ in range(200):
                if self.proc.poll() is not None:
                    raise RuntimeError('Dolphin exited early (see log)')
                try:
                    self.pipes[p] = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError('pipe %s never opened by Dolphin' % p)
        return self

    def stop(self):
        for fd in self.pipes.values():
            try:
                os.close(fd)
            except OSError:
                pass
        self.pipes = {}
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def windows(self):
        import Quartz
        res = []
        for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll,
                                                    Quartz.kCGNullWindowID):
            if w.get('kCGWindowOwnerPID') == self.proc.pid:
                b = w['kCGWindowBounds']
                res.append((w['kCGWindowNumber'], w.get('kCGWindowName', ''), b['Width'], b['Height'],
                            w.get('kCGWindowIsOnscreen', 0)))
        return res

    def shot(self, path):
        """Capture just this Dolphin's render window."""
        wins = [w for w in self.windows() if w[2] > 200 and w[3] > 200 and '|' in w[1]]
        if not wins:
            return False
        subprocess.run(['screencapture', '-x', '-o', '-l', str(wins[0][0]), path], check=False)
        return os.path.exists(path)

    def snap(self, path, wait=2.0):
        """Dolphin's own screenshot hotkey (reads the GPU framebuffer, so works with the window hidden)."""
        import glob
        before = set(glob.glob(os.path.join(self.root, 'ScreenShots', '**', '*.png'), recursive=True))
        self.press('hk', 'A', 0.3)
        end = time.time() + wait + 3
        while time.time() < end:
            new = set(glob.glob(os.path.join(self.root, 'ScreenShots', '**', '*.png'), recursive=True)) - before
            if new:
                time.sleep(0.3)
                shutil.copy(sorted(new)[0], path)
                return True
            time.sleep(0.3)
        return False

    # ---- input -------------------------------------------------------
    def send(self, pipe, line):
        os.write(self.pipes[pipe], (line + '\n').encode())

    def press(self, pipe, button, hold=0.1):
        self.send(pipe, 'PRESS ' + button)
        time.sleep(hold)
        self.send(pipe, 'RELEASE ' + button)

    def stick(self, pipe, which, x, y):
        """x, y in -1..1 (right / up positive)."""
        self.send(pipe, 'SET %s %.3f %.3f' % (which, (x + 1) / 2, (y + 1) / 2))


class Gdb:
    """Minimal GDB remote client for Dolphin's stub: halt, read memory, resume."""

    def __init__(self, port=GDB_PORT, timeout=5):
        self.s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        self.buf = b''
        self.packet(b'?')

    def _recv_packet(self, timeout=5):
        self.s.settimeout(timeout)
        while True:
            # drop acks / noise before '$'
            s = self.buf.find(b'$')
            if s >= 0:
                self.buf = self.buf[s:]
                e = self.buf.find(b'#')
                if e >= 0 and len(self.buf) >= e + 3:
                    pkt = self.buf[1:e]
                    self.buf = self.buf[e + 3:]
                    self.s.sendall(b'+')
                    return pkt
            else:
                self.buf = b''
            d = self.s.recv(65536)
            if not d:
                raise EOFError
            self.buf += d

    def packet(self, data):
        cs = sum(data) & 0xff
        self.s.sendall(b'$' + data + b'#%02x' % cs)
        return self._recv_packet()

    def read(self, addr, n):
        out = b''
        while n:
            k = min(n, 0x400)
            r = self.packet(b'm%x,%x' % (addr, k))
            out += bytes.fromhex(r.decode())
            addr += k
            n -= k
        return out

    def write(self, addr, data):
        return self.packet(b'M%x,%x:' % (addr, len(data)) + data.hex().encode())

    def halt(self):
        self.s.sendall(b'\x03')
        time.sleep(0.3)
        self.drain()

    def drain(self):
        self.s.settimeout(0.2)
        try:
            while self.s.recv(65536):
                pass
        except (socket.timeout, BlockingIOError):
            pass
        self.buf = b''

    def resume(self):
        self.s.sendall(b'$c#63')

    def close(self):
        self.s.close()


def gdb_regs(g):
    """General registers + pc from a halted stub: dict r0..r31, pc."""
    r = g.packet(b'g').decode()
    words = [int(r[i:i + 8], 16) for i in range(0, len(r), 8)]
    out = {'r%d' % i: words[i] for i in range(32)}
    # Dolphin's layout: 32 GPR, 32 FPR (64-bit each = 2 words), then pc, msr, ...
    out['pc'] = words[32 + 64] if len(words) > 96 else None
    return out


def inject(g, feature):
    """Write a Feature's static view into the running game over the GDB stub.

    Code first, the redirected instruction last, so a half-written hook is never live.
    """
    writes = feature.writes()
    writes.sort(key=lambda w: w[0] < 0x80001820 or w[0] >= 0x80003000)   # cave first
    for addr, data in writes:
        for i in range(0, len(data), 0x200):
            r = g.write(addr + i, data[i:i + 0x200])
            assert r == b'OK', (hex(addr + i), r)
    for addr, data in writes:
        assert g.read(addr, len(data)) == data, hex(addr)
