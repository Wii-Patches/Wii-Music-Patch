import struct,sys
class Dol:
    def __init__(s,path):
        s.d=open(path,'rb').read()
        h=struct.unpack('>18I18I18II I I',s.d[:0x100][:0xE4]) if False else None
        s.off=struct.unpack('>18I',s.d[0:0x48]);s.addr=struct.unpack('>18I',s.d[0x48:0x90]);s.size=struct.unpack('>18I',s.d[0x90:0xD8])
        s.entry=struct.unpack('>I',s.d[0xE0:0xE4])[0]
    def secs(s):
        return [(i,s.off[i],s.addr[i],s.size[i]) for i in range(18) if s.size[i]]
    def read(s,a,n):
        for i,o,ad,sz in s.secs():
            if ad<=a<ad+sz: return s.d[o+a-ad:o+a-ad+n]
    def w32(s,a):return struct.unpack('>I',s.read(a,4))[0]
if __name__=='__main__':
    d=Dol(sys.argv[1])
    for x in d.secs(): print("sec%d off=%x addr=%x size=%x end=%x"%(x[0],x[1],x[2],x[3],x[2]+x[3]))
    print(hex(d.entry))
