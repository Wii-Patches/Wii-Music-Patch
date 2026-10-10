import sys,subprocess,struct
sys.path.insert(0,'.')
from dolread import Dol
d=Dol('ex/sys/main.dol')
a=int(sys.argv[1],16);n=int(sys.argv[2],16)
b=d.read(a,n)
open('/tmp/_b.bin','wb').write(b) if False else None
import os
p=os.environ.get('TMPDIR','/tmp')+'/_b.bin'
open(p,'wb').write(b)
print(subprocess.run(['/opt/devkitpro/devkitPPC/bin/powerpc-eabi-objdump','-D','-EB','-b','binary','-m','powerpc:750','--adjust-vma=0x%x'%a,p],capture_output=True,text=True).stdout.split('<.data>:')[-1])
