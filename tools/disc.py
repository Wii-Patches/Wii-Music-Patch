"""Patch a whole disc image: extract with wit, patch sys/main.dol, rebuild.

The rebuilt image replaces the original in place, keeping its filename and
folder (USB loaders key off the `/wbfs/<Title> [ID6]/` layout); the untouched
original is kept next to it as `<name>.bak`.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wmpatch
from disc_ids import match_disc_id
from regions import REGIONS


def find_wit():
    """A wit bundled with this app (PyInstaller build) wins over PATH.

    --add-binary'd files land next to sys._MEIPASS: a plain onedir build puts
    them in _internal/, and a windowed macOS .app puts them in
    Contents/Frameworks/ instead of Contents/MacOS/ alongside the binary.
    """
    name = 'wit.exe' if os.name == 'nt' else 'wit'
    if getattr(sys, 'frozen', False):
        for base in (getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable)):
            if base:
                bundled = os.path.join(base, name)
                if os.path.isfile(bundled):
                    return bundled
    return shutil.which('wit')


def find_file(root, name):
    for r, _, files in os.walk(root):
        if name in files:
            return os.path.join(r, name)
    return None


def run_patch(image_path, log, done, flags=3):
    """Patch `image_path` in place.  `flags`: bit0 GameCube controller, bit1 Classic Controller."""
    try:
        wit = find_wit()
        if wit is None:
            raise RuntimeError('wit (Wiimms ISO Tool) not found: not bundled with this '
                               'build and not on PATH')
        if not flags & 3:
            raise RuntimeError('nothing selected: tick at least one controller type')
        fmt = '--iso' if image_path.lower().endswith('.iso') else '--wbfs'

        with tempfile.TemporaryDirectory(prefix='wii_music_patch_') as tmp:
            fst = os.path.join(tmp, 'fst')
            log('extracting %s...' % os.path.basename(image_path))
            r = subprocess.run([wit, 'extract', image_path, '--dest', fst, '--psel', 'data',
                                '--overwrite', '-q'], capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError('extract failed:\n' + (r.stderr or r.stdout))

            boot = find_file(fst, 'boot.bin')
            if not boot:
                raise RuntimeError('could not read sys/boot.bin from the extracted disc')
            with open(boot, 'rb') as f:
                disc_id = f.read(6).decode('ascii', 'replace')
            key = match_disc_id(disc_id, REGIONS)
            if key is None:
                raise RuntimeError('%s is not a Wii Music release this patcher knows.\n\nSupported: %s'
                                   % (disc_id, ', '.join(repr(r) for r in REGIONS.values())))
            log('disc: %r' % REGIONS[key])

            dol_path = find_file(fst, 'main.dol')
            if not dol_path or os.path.basename(os.path.dirname(dol_path)) != 'sys':
                raise RuntimeError('could not find sys/main.dol in the extracted disc')
            try:
                region, size = wmpatch.patch_dol(dol_path, dol_path, key, flags)
            except SystemExit as e:
                raise RuntimeError('the main.dol does not match the retail %s -- already patched, or '
                                   'not an unmodified dump. Not patching it.' % REGIONS[key].name) from e
            log('  patched main.dol (%d bytes added)' % size)

            staged = os.path.join(tmp, 'patched.img')
            log('rebuilding...')
            r = subprocess.run([wit, 'copy', fst, '--dest', staged, fmt, '--overwrite', '-q'],
                               capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError('rebuild failed:\n' + (r.stderr or r.stdout))

            # Only touch the user's file once the rebuild has actually succeeded.
            backup = image_path + '.bak'
            if os.path.exists(backup):
                log('  backup already exists, keeping it: %s' % os.path.basename(backup))
            else:
                shutil.copyfile(image_path, backup)
                log('  backed up original -> %s' % os.path.basename(backup))
            shutil.move(staged, image_path)
            log('done: patched in place, %s' % os.path.basename(image_path))
            done(True, image_path)
    except Exception as e:
        log('ERROR: %s' % e)
        done(False, str(e))
