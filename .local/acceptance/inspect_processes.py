import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path

k=c.WinDLL('kernel32',use_last_error=True); n=c.WinDLL('ntdll')
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; k.OpenProcess.restype=w.HANDLE
k.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
k.CloseHandle.argtypes=[w.HANDLE]
class P(c.Structure):
    _fields_=[('a',c.c_void_p),('peb',c.c_void_p),('b',c.c_void_p*2),('pid',c.c_void_p),('d',c.c_void_p)]
n.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
results=[]
for pid in (11656,26200):
    h=k.OpenProcess(0x410,False,pid)
    if not h: raise OSError(c.get_last_error(), 'Read-only process open failed')
    def read(a,size):
        b=c.create_string_buffer(size); count=c.c_size_t()
        if not k.ReadProcessMemory(h,a,b,size,c.byref(count)): raise OSError(c.get_last_error())
        return b.raw[:count.value]
    def ptr(a): return int.from_bytes(read(a,8),'little')
    try:
        p=P(); l=w.ULONG()
        if n.NtQueryInformationProcess(h,0,c.byref(p),c.sizeof(p),c.byref(l)): raise RuntimeError('Query failed')
        params=ptr(p.peb+0x20)
        cwd=read(ptr(params+0x40),int.from_bytes(read(params+0x38,2),'little')).decode('utf-16-le')
        assert Path(cwd).resolve()==Path.cwd().resolve(), 'Unexpected working directory'
        env=ptr(params+0x80); data=bytearray()
        for i in range(0,131072,2):
            data.extend(read(env+i,2))
            if len(data)>=4 and data[-4:]==b'\0\0\0\0': break
        else: raise RuntimeError('Environment terminator missing')
        selected={}
        for entry in bytes(data).decode('utf-16-le').split('\0'):
            key,sep,value=entry.partition('=')
            if sep and key.upper() in ('DATABASE_URL','JWT_SECRET_KEY'): selected[key.upper()]=value
        results.append({'pid':pid,'cwd':cwd,'DATABASE_URL_present':bool(selected.get('DATABASE_URL')),
                        'JWT_SECRET_KEY_present':bool(selected.get('JWT_SECRET_KEY'))})
    finally: k.CloseHandle(h)
Path('.local/acceptance/processes-before.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
