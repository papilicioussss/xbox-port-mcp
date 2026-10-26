import hashlib
import os
from pathlib import Path
import struct
import pytest
from xbox_port_mcp.jobs import Job
from xbox_port_mcp.packaging import require_x64_pe,verify_disc
from xbox_port_mcp.pipeline import Pipeline
from xbox_port_mcp.profiles import profile,require_match
from xbox_port_mcp.formats import inspect_xbe_bytes
from xbox_port_mcp.workspaces import Workspaces
from conftest import make_xbe

def test_unknown_hash_does_not_get_address_fixes():
    with pytest.raises(ValueError,match='Unsupported'):require_match(profile('sims-bustin-out-usa'),inspect_xbe_bytes(make_xbe()))

def test_compile_fixed_arguments_and_output_proof(tmp_path,monkeypatch):
    ws=Workspaces(tmp_path/'work',[]);created=ws.create('sims-bustin-out-usa')
    root=Path(created['path']);(root/'source').mkdir()
    called=[]
    monkeypatch.setattr('xbox_port_mcp.pipeline.tool',lambda name:'/trusted/cmake')
    def run(job,argv,cwd):
        called.append((argv,cwd))
        out=root/'source/out/build/release/SimsBustinOut.exe';out.parent.mkdir(parents=True);out.write_bytes(b'fake-build-output')
    monkeypatch.setattr('xbox_port_mcp.pipeline.run_process',run)
    item=profile('sims-bustin-out-usa')
    result=Pipeline(ws).compile(created['id'],root,item,Job('id',created['id'],'compile'))
    assert called[0][0]==['/trusted/cmake','--build','--preset','release','--parallel','2']
    assert result['playability']=='not_assessed'
    assert result['sha256']==hashlib.sha256(b'fake-build-output').hexdigest()

def test_pe_architecture(tmp_path):
    path=tmp_path/'fake.exe';data=bytearray(128);data[:2]=b'MZ';struct.pack_into('<I',data,60,80);data[80:86]=b'PE\0\0\x64\x86';path.write_bytes(data)
    require_x64_pe(path)
    data[84:86]=b'\x4c\x01';path.write_bytes(data)
    with pytest.raises(ValueError):require_x64_pe(path)

def test_iso_verifier_rejects_wrong_bytes(tmp_path):
    path=tmp_path/'bad.iso';path.write_bytes(b'not-an-iso')
    with pytest.raises(ValueError):verify_disc(path,tmp_path/'missing.exe')


def test_iso_verifier_accepts_exact_installer_and_rejects_tamper(tmp_path):
    installer=tmp_path/'installer.exe';installer.write_bytes(b'synthetic-installer-only')
    data=bytearray(24*2048);pvd=16*2048
    data[pvd:pvd+7]=b'\x01CD001\x01'
    struct.pack_into('<I',data,pvd+158,20);struct.pack_into('<I',data,pvd+166,2048)
    name=b'INSTALAR.EXE;1';at=20*2048
    data[at]=len(name)+33;struct.pack_into('<I',data,at+2,21)
    struct.pack_into('<I',data,at+10,installer.stat().st_size)
    data[at+32]=len(name);data[at+33:at+33+len(name)]=name
    data[21*2048:21*2048+installer.stat().st_size]=installer.read_bytes()
    image=tmp_path/'synthetic.iso';image.write_bytes(data)
    assert verify_disc(image,installer)['installer_verified']
    data[21*2048]^=1;image.write_bytes(data)
    with pytest.raises(ValueError,match='SHA-256'):verify_disc(image,installer)


@pytest.mark.skipif(os.name!='nt',reason='Windows packaging only')
def test_disc_failure_is_retryable(tmp_path,monkeypatch):
    from xbox_port_mcp.packaging import create_disc
    ws=Workspaces(tmp_path/'work',[]);created=ws.create('sims-bustin-out-usa')
    root=Path(created['path']);(root/'package/build').mkdir(parents=True)
    (root/'package/build/Instalar.exe').write_bytes(b'fake')
    (root/'artwork').mkdir();(root/'artwork/game.ico').write_bytes(b'fake')
    def fail(*args):raise RuntimeError('writer failed')
    monkeypatch.setattr('xbox_port_mcp.packaging.run_process',fail)
    for _ in range(2):
        with pytest.raises(RuntimeError,match='writer failed'):
            create_disc(ws,created['id'],profile('sims-bustin-out-usa'),Job('id',created['id'],'iso'),'powershell')
        assert not (root/'disc').exists()
        assert not list(root.glob('.disc-*'))

@pytest.mark.skipif(os.name!='nt',reason='Windows packaging only')
def test_iso_writer_artifacts_are_staged_and_removed_on_cancel(tmp_path,monkeypatch):
    from xbox_port_mcp.packaging import create_disc
    ws=Workspaces(tmp_path/'work',[]);meta=ws.create('sims-bustin-out-usa')
    root=Path(meta['path']);(root/'package/build').mkdir(parents=True)
    (root/'package/build/Instalar.exe').write_bytes(b'fake')
    (root/'artwork').mkdir();(root/'artwork/game.ico').write_bytes(b'fake')
    def cancel(job,argv,cwd):
        dest=Path(argv[argv.index('-OutputPath')+1])
        dest.with_suffix('.partial').write_bytes(b'partial')
        raise InterruptedError('cancelled')
    monkeypatch.setattr('xbox_port_mcp.packaging.run_process',cancel)
    with pytest.raises(InterruptedError):
        create_disc(ws,meta['id'],profile('sims-bustin-out-usa'),Job('id',meta['id'],'iso'),'powershell')
    assert not list(root.rglob('*.partial'))
    assert not (root/'game-windows.iso').exists()
    assert not (root/'disc').exists()
