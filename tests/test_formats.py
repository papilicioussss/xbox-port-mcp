import struct
import pytest
from xbox_port_mcp.formats import Xdvdfs,inspect_iso,inspect_xbe,inspect_xbe_bytes,safe_name,SECTOR
from conftest import make_iso,make_xbe

def test_inspect_extract_preserves_iso(image,tmp_path):
    before=image.read_bytes();info=inspect_iso(image)
    assert info['file_count']==1 and info['xbe']['title_id']=='45410043'
    assert info['xbe']['title']=='Test Sim'
    with Xdvdfs(image) as iso:assert iso.extract(tmp_path/'assets')['files']==1
    assert (tmp_path/'assets/default.xbe').read_bytes()==make_xbe()
    assert image.read_bytes()==before
    assert inspect_xbe(tmp_path/'assets/default.xbe')['sha1']==info['xbe']['sha1']

@pytest.mark.parametrize('name',['..','../escape','a\\b','AUX.txt','COM1','a:stream','tail.','tail ','bad\0name'])
def test_unsafe_names(name):
    with pytest.raises(ValueError):safe_name(name)

def test_unsafe_image_never_publishes(tmp_path):
    path=make_iso(tmp_path/'bad.iso',b'../outside')
    with Xdvdfs(path) as iso,pytest.raises(ValueError):iso.extract(tmp_path/'assets')
    assert not (tmp_path/'assets').exists() and not list(tmp_path.glob('.extract-*'))

def test_cycle(image):
    data=bytearray(image.read_bytes());struct.pack_into('<H',data,33*SECTOR+2,8)
    struct.pack_into('<HHIIBB',data,33*SECTOR+32,0,8,35,4,0,1)
    data[33*SECTOR+46]=ord('b');image.write_bytes(data)
    with Xdvdfs(image) as iso,pytest.raises(ValueError,match='Cyclic'):iso.entries()

def test_file_outside_image(image):
    data=bytearray(image.read_bytes());struct.pack_into('<I',data,33*SECTOR+4,0xFFFFFF00);image.write_bytes(data)
    with Xdvdfs(image) as iso,pytest.raises(ValueError,match='outside'):iso.entries()

def test_cancelled_extraction_is_transactional(image,tmp_path):
    with Xdvdfs(image) as iso,pytest.raises(InterruptedError):iso.extract(tmp_path/'assets',lambda:True)
    assert not (tmp_path/'assets').exists() and not list(tmp_path.glob('.extract-*'))

def test_never_overwrites_existing(image,tmp_path):
    target=tmp_path/'assets';target.mkdir();(target/'save').write_text('keep')
    with Xdvdfs(image) as iso,pytest.raises(ValueError):iso.extract(target)
    assert (target/'save').read_text()=='keep'

def test_xbe_invalid_certificate():
    data=bytearray(make_xbe());struct.pack_into('<I',data,0x118,0xFFFFFFFF)
    with pytest.raises(ValueError,match='certificate'):inspect_xbe_bytes(data)

def test_case_collision(image):
    data=bytearray(image.read_bytes());struct.pack_into('<H',data,33*SECTOR+2,8)
    struct.pack_into('<HHIIBB',data,33*SECTOR+32,0,0,35,4,0,11)
    data[33*SECTOR+46:33*SECTOR+57]=b'DEFAULT.XBE';image.write_bytes(data)
    with Xdvdfs(image) as iso,pytest.raises(ValueError,match='collision'):iso.entries()

def test_aggregate_extent_amplification_rejected(tmp_path):
    import struct
    from conftest import make_iso
    from xbox_port_mcp.formats import SECTOR
    path=make_iso(tmp_path/'amplification.iso',name=b'one',payload=b'x'*4096)
    data=bytearray(path.read_bytes())
    struct.pack_into('<HHIIBB',data,33*SECTOR,0,8,35,4096,0,3)
    data[33*SECTOR+14:33*SECTOR+17]=b'one'
    struct.pack_into('<HHIIBB',data,33*SECTOR+32,0,0,0,len(data),0,3)
    data[33*SECTOR+46:33*SECTOR+49]=b'two'
    path.write_bytes(data)
    with Xdvdfs(path) as image:
        with pytest.raises(ValueError,match='[Bb]yte budget'):
            image.extract(tmp_path/'output')
    assert not (tmp_path/'output').exists()
