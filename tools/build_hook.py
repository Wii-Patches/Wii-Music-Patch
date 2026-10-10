"""Compiles src/gcpad.c for one release (devkitPPC) and returns (code words, {symbol: address})."""
import os, re, subprocess, tempfile
from layout import CAVE_BASE, CFG, STATE

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'src')
DKP = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')


def build(consts, base=CAVE_BASE, extra=()):
    gcc = os.path.join(DKP, 'bin', 'powerpc-eabi-gcc')
    ld = os.path.join(DKP, 'bin', 'powerpc-eabi-ld')
    objcopy = os.path.join(DKP, 'bin', 'powerpc-eabi-objcopy')
    nm = os.path.join(DKP, 'bin', 'powerpc-eabi-nm')
    macros = dict(consts, CFG=CFG, STATE=STATE, POINTER_DEADZONE=15, POINTER_SPEED='0.47f')
    with tempfile.TemporaryDirectory() as t:
        o, elf, binf = (os.path.join(t, n) for n in ('g.o', 'g.elf', 'g.bin'))
        cmd = [gcc, '-c', os.path.join(SRC, 'gcpad.c'), '-o', o, '-O2', '-mbig-endian', '-mcpu=750', '-mhard-float',
               '-msdata=none', '-ffreestanding', '-fno-pic', '-fno-builtin', '-nostdlib', '-fno-asynchronous-unwind-tables']
        cmd += list(extra)
        for k, v in macros.items():
            cmd.append('-D%s=%s' % (k, ('0x%X' % v) if isinstance(v, int) and k not in ('POINTER_DEADZONE',) else v))
        subprocess.run(cmd, check=True)
        subprocess.run([ld, '-T', os.path.join(SRC, 'link.ld'), '--defsym', 'BASE=0x%X' % base, '-o', elf, o], check=True)
        subprocess.run([objcopy, '-O', 'binary', elf, binf], check=True)
        data = open(binf, 'rb').read()
        syms = {}
        for line in subprocess.run([nm, elf], capture_output=True, text=True, check=True).stdout.splitlines():
            m = re.match(r'([0-9a-f]+) [Tt] (\w+)', line)
            if m:
                syms[m.group(2)] = int(m.group(1), 16)
    return data, syms
