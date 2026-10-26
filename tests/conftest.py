import struct
import pytest
from xbox_port_mcp.formats import MAGIC, SECTOR

def make_xbe():
    data=bytearray(1024);data[:4]=b'XBEH'
    for at,value in [(0x104,0x10000),(0x118,0x10180),(0x11C,1),(0x120,0x10240),(0x124,7)]:
        struct.pack_into('<I',data,at,value)
    struct.pack_into('<I',data,0x188,0x45410043)
    data[0x18C:0x19C]='Test Sim'.encode('utf-16le')
    return bytes(data)

def make_iso(path,name=b'default.xbe',payload=None):
    payload=make_xbe() if payload is None else payload
    data=bytearray(36*SECTOR+len(payload));descriptor=32*SECTOR
    data[descriptor:descriptor+20]=MAGIC
    data[descriptor+SECTOR-20:descriptor+SECTOR]=MAGIC
    struct.pack_into('<II',data,descriptor+20,33,SECTOR)
    struct.pack_into('<HHIIBB',data,33*SECTOR,0,0,35,len(payload),0,len(name))
    data[33*SECTOR+14:33*SECTOR+14+len(name)]=name
    data[35*SECTOR:35*SECTOR+len(payload)]=payload
    path.write_bytes(data)
    return path

@pytest.fixture
def image(tmp_path):return make_iso(tmp_path/'test.iso')
