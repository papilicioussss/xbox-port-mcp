"""Build private distribution artifacts. Retail data never belongs in this package."""
from __future__ import annotations
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import uuid

from .formats import sha256_file
from .jobs import run_process

CRT_NAMES = ('concrt140.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll',
             'msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll','vccorlib140.dll',
             'vcruntime140.dll','vcruntime140_1.dll','vcruntime140_threads.dll')

def copy_file(source, target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): raise ValueError('Refusing to replace staged input')
    try: os.link(source,target)
    except OSError: shutil.copy2(source,target)

def require_x64_pe(path):
    with path.open('rb') as stream:
        header=stream.read(64)
        if len(header)<64 or header[:2]!=b'MZ':raise ValueError('Expected Windows executable or DLL')
        stream.seek(struct.unpack_from('<I',header,60)[0])
        if stream.read(6)!=b'PE\0\0\x64\x86':raise ValueError('Expected AMD64 PE')

def create_artwork(ws,identifier,item,job,ffmpeg):
    from PIL import Image,ImageDraw,ImageFont,ImageOps
    root=ws.get(identifier)
    target=ws.child(identifier,'artwork')
    if target.exists():raise ValueError('Artwork already exists; refusing overwrite')
    video=ws.child(identifier,'assets/'+item['art_video'],must_exist=True)
    staging=Path(tempfile.mkdtemp(prefix='.art-',dir=root))
    def font(size):
        candidates=[str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeuib.ttf'),'DejaVuSans.ttf']
        for candidate in candidates:
            try:return ImageFont.truetype(candidate,size)
            except OSError:pass
        return ImageFont.load_default()
    try:
        for index,seconds in enumerate((5,25,45,65)):
            frame=staging/f'frame-{index}.png'
            run_process(job,[ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-i',str(video),
                             '-ss',str(seconds),'-frames:v','1',str(frame)],root)
            if not frame.is_file():raise ValueError('Video decoder produced no frame')
            with Image.open(frame) as source:
                slide=ImageOps.fit(source.convert('RGB'),(1120,448))
            draw=ImageDraw.Draw(slide)
            draw.rectangle((0,350,1120,448),fill='#172c71')
            draw.text((30,370),item['name'],font=font(38),fill='white')
            slide.save(staging/f'slide-{index}.bmp')
        welcome=Image.new('RGB',(492,942),'#172c71')
        with Image.open(staging/'frame-0.png') as source:
            welcome.paste(ImageOps.fit(source.convert('RGB'),(492,430)),(0,360))
        draw=ImageDraw.Draw(welcome)
        words=item['name'].split();line='';lines=[]
        for word in words:
            candidate=(line+' '+word).strip()
            if draw.textlength(candidate,font=font(49))>420 and line:
                lines.append(line);line=word
            else:line=candidate
        lines.append(line)
        for n,line in enumerate(lines):draw.text((34,45+n*70),line,font=font(49),fill='white')
        draw.text((34,830),'PC  /  WINDOWS',font=font(30),fill='#a5f5bd')
        welcome.save(staging/'welcome.png')
        icon=Image.new('RGB',(128,128),'#172c71');d=ImageDraw.Draw(icon)
        d.polygon([(64,10),(103,58),(64,118),(25,58)],fill='#59e880')
        icon.save(staging/'header.png')
        icon.save(staging/'game.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128)])
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return {'artwork':str(target),'source':'frames from local retail video','distributed_in_repository':False}

def create_installer(ws,identifier,item,job,iscc):
    if os.name!='nt':raise ValueError('Installer packaging currently requires Windows')
    root=ws.get(identifier)
    target=ws.child(identifier,'package')
    if target.exists():raise ValueError('Package already exists; refusing overwrite')
    executable=ws.child(identifier,f'source/out/build/{item["preset"]}/{item["executable"]}',must_exist=True)
    require_x64_pe(executable)
    art=ws.child(identifier,'artwork',must_exist=True)
    crt_setting=os.environ.get('XBOX_PORT_CRT_DIR')
    if not crt_setting:raise ValueError('Set XBOX_PORT_CRT_DIR to the licensed Visual Studio x64 CRT redistributable directory')
    crt=Path(crt_setting).resolve(strict=True)
    for name in ('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll'):
        if not (crt/name).is_file():raise ValueError('Incomplete CRT redistributable directory')
    staging=Path(tempfile.mkdtemp(prefix='.package-',dir=root))
    try:
        payload=staging/'payload';payload.mkdir()
        copy_file(executable,payload/item['executable'])
        for path in ws.tree_files(identifier,'assets'):
            copy_file(path,payload/'assets'/path.relative_to(root/'assets'))
        for name in CRT_NAMES:
            if (crt/name).is_file():
                require_x64_pe(crt/name)
                copy_file(crt/name,payload/name)
        sdk=ws.child(identifier,'source/sdk',must_exist=True)
        for source,name in [(sdk/'LICENSE','LICENSE-SDK.txt'),(sdk/'THIRD_PARTY.txt','THIRD_PARTY.txt')]:
            if not source.is_file():raise ValueError('SDK license/attribution file missing')
            copy_file(source,payload/name)
        (payload/'settings.toml').write_text('display_mode = "windowed"\nwidth = 960\nheight = 720\nfps_cap = 60\nvsync = true\nhdr = "off"\n',encoding='utf-8')
        (payload/'LEEME.txt').write_text(item['name']+'\n\nVersión experimental para PC. F1: ajustes y controles. Las partidas se guardan en hdd junto al ejecutable. Actualizar y desinstalar conservan hdd y settings.toml.\nNo se necesitan la ISO ni conexión después de instalar. Guarda una copia de hdd para trasladar tu progreso.\n',encoding='utf-8')
        (staging/'artwork').mkdir()
        for name in ['welcome.png','header.png','game.ico',*(f'slide-{n}.bmp' for n in range(4))]:
            copy_file(art/name,staging/'artwork'/name)
        template=files('xbox_port_mcp').joinpath('resources/installer.iss').read_text(encoding='utf-8')
        values={'__GAME_NAME__':item['name'],'__EXE_NAME__':item['executable'],
                '__APP_ID__':str(uuid.uuid5(uuid.NAMESPACE_URL,'xbox-port-mcp/'+item['id']))}
        for key,value in values.items():
            if any(c in value for c in '"{}\r\n'):raise ValueError('Unsafe profile installer metadata')
            template=template.replace(key,value)
        (staging/'setup.iss').write_text(template,encoding='utf-8')
        manifest=[{'path':str(p.relative_to(payload)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha256_file(p)}
                  for p in payload.rglob('*') if p.is_file()]
        (staging/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        run_process(job,[iscc,str(staging/'setup.iss')],staging)
        setup=staging/'build/Instalar.exe'
        if not setup.is_file():raise ValueError('Compiler returned without creating installer')
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return {'installer':str(target/'build/Instalar.exe'),'sha256':sha256_file(target/'build/Instalar.exe'),
            'personal_saves_included':False,'interactive_test':'not_assessed'}

def create_disc(ws,identifier,item,job,powershell):
    if os.name!='nt':raise ValueError('ISO creation currently requires Windows IMAPI')
    root=ws.get(identifier);dest=ws.child(identifier,'game-windows.iso')
    if dest.exists():raise ValueError('ISO already exists; refusing overwrite')
    disc=ws.child(identifier,'disc')
    if disc.exists():raise ValueError('Disc staging already exists; refusing overwrite')
    staging=Path(tempfile.mkdtemp(prefix='.disc-',dir=root))
    published_disc=False
    try:
        content=staging/'content';content.mkdir()
        copy_file(ws.child(identifier,'package/build/Instalar.exe',must_exist=True),content/'Instalar.exe')
        (content/'LEEME.txt').write_text(item['name']+'\n\nEjecuta Instalar.exe. Puedes desmontar el disco después de instalar. Juego experimental.\n',encoding='utf-8')
        copy_file(ws.child(identifier,'artwork/game.ico',must_exist=True),content/'Game.ico')
        (content/'autorun.inf').write_text('[autorun]\nopen=Instalar.exe\nicon=Game.ico\n',encoding='utf-8')
        script=staging/'create-disc.ps1'
        script.write_text(files('xbox_port_mcp').joinpath('resources/create_iso.ps1').read_text(encoding='utf-8'),encoding='utf-8')
        staged_iso=staging/'game-windows.iso'
        run_process(job,[powershell,'-NoProfile','-ExecutionPolicy','RemoteSigned','-File',str(script),'-SourceDirectory',str(content),'-OutputPath',str(staged_iso)],root)
        if job.cancelled.is_set():raise InterruptedError('ISO creation cancelled')
        if not staged_iso.is_file():raise ValueError('ISO writer returned without an image')
        content.rename(disc);published_disc=True
        staged_iso.rename(dest)
    except BaseException:
        if published_disc and not dest.exists():shutil.rmtree(disc)
        raise
    finally:
        if staging.exists():shutil.rmtree(staging)
    return {'iso':str(dest),'bytes':dest.stat().st_size,'verification':'pending_verify_iso'}


def verify_disc(iso:Path,installer:Path)->dict:
    with iso.open('rb') as stream:
        stream.seek(16*2048);pvd=stream.read(2048)
        if len(pvd)!=2048 or pvd[:7]!=b'\x01CD001\x01':raise ValueError('Invalid ISO9660 primary descriptor')
        record=pvd[156:190];sector=int.from_bytes(record[2:6],'little');size=int.from_bytes(record[10:14],'little')
        if size>1024*1024:raise ValueError('Root-directory limit exceeded')
        stream.seek(sector*2048);directory=stream.read(size)
        at=0;entries={}
        while at<len(directory):
            count=directory[at]
            if not count:at=(at//2048+1)*2048;continue
            data=directory[at:at+count]
            if len(data)<34 or 33+data[32]>len(data):raise ValueError('Invalid ISO directory record')
            name=data[33:33+data[32]].decode('ascii',errors='replace').split(';')[0]
            entries[name]=(int.from_bytes(data[2:6],'little'),int.from_bytes(data[10:14],'little'))
            at+=count
        if 'INSTALAR.EXE' not in entries:raise ValueError('Installer missing inside ISO')
        sector,size=entries['INSTALAR.EXE']
        if size!=installer.stat().st_size:raise ValueError('Installer size mismatch')
        stream.seek(sector*2048);digest=hashlib.sha256();remaining=size
        while remaining:
            block=stream.read(min(remaining,1024*1024))
            if not block:raise ValueError('Truncated ISO installer')
            digest.update(block);remaining-=len(block)
        expected=sha256_file(installer)
        if digest.hexdigest()!=expected:raise ValueError('Installer SHA-256 mismatch')
    return {'installer_verified':True,'installer_sha256':expected,'iso_sha256':sha256_file(iso),
            'iso_bytes':iso.stat().st_size,'mounted_test':'not_assessed'}
