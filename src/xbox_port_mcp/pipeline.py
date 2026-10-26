from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
from importlib.resources import files

from .formats import Xdvdfs, inspect_xbe
from .jobs import Job, run_process
from .profiles import profile, require_match
from .workspaces import Workspaces

def tool(name: str) -> str:
    setting = 'XBOX_PORT_' + name.upper().replace('-', '_')
    value = os.environ.get(setting) or shutil.which(name)
    if not value or not Path(value).is_file():
        raise ValueError(f'Missing tool: {name}; configure {setting} or PATH')
    return str(Path(value).resolve())

def execution_allowed():
    if os.environ.get('XBOX_PORT_ALLOW_EXECUTION') != '1':
        raise ValueError('External tools disabled. Set XBOX_PORT_ALLOW_EXECUTION=1 only for trusted port sources/tools')

def doctor() -> dict:
    available = {}
    for name in ('git','cmake','ninja','clang','clang++','ffmpeg','iscc','powershell'):
        try: available[name] = tool(name)
        except ValueError: available[name] = None
    return {'platform':os.name, 'tools':available,
            'execution_enabled':os.environ.get('XBOX_PORT_ALLOW_EXECUTION') == '1',
            'network_enabled':os.environ.get('XBOX_PORT_ALLOW_NETWORK') == '1',
            'msvc_environment_present':bool(os.environ.get('INCLUDE') and os.environ.get('LIB')),
            'notes':['Windows builds need the x64 MSVC development environment and a compatible LLVM toolchain.',
                     'ISO creation and installer packaging require Windows, PowerShell IMAPI and Inno Setup.',
                     'No tools are downloaded/installed automatically; a build may fetch dependencies when network is enabled.']}

class Pipeline:
    def __init__(self, workspaces: Workspaces): self.workspaces = workspaces

    def context(self, identifier):
        root = self.workspaces.get(identifier)
        return root, profile(self.workspaces.metadata(identifier)['profile'])

    def run(self, identifier: str, step: str, job: Job, input_path: str | None = None) -> dict:
        root, item = self.context(identifier)
        if step == 'extract':
            if not input_path: raise ValueError('extract requires an ISO input_path')
            source = self.workspaces.read_path(input_path)
            with Xdvdfs(source) as iso:
                result = iso.extract(self.workspaces.child(identifier,'assets'),job.cancelled.is_set)
            return {**result, 'identity':inspect_xbe(root/'assets'/item['xbe'])}
        execution_allowed()
        actions = {'fixes':lambda identifier,root,item,job:self.apply_fixes(identifier,job), 'prepare':self.prepare, 'configure':self.configure, 'compile':self.compile,
                   'artwork':self.artwork, 'installer':self.installer, 'iso':self.iso, 'verify_iso':self.verify_iso}
        if step not in actions: raise ValueError('Unknown pipeline step')
        identity = inspect_xbe(self.workspaces.child(identifier,'assets/'+item['xbe'],must_exist=True))
        require_match(item,identity)
        return actions[step](identifier, root, item, job)

    def prepare(self, identifier, root, item, job):
        if os.environ.get('XBOX_PORT_ALLOW_NETWORK') != '1':
            raise ValueError('Pinned source checkout needs XBOX_PORT_ALLOW_NETWORK=1')
        source = self.workspaces.child(identifier,'source')
        if source.exists(): raise ValueError('Sources already exist; refusing reset or overwrite')
        git = tool('git')
        run_process(job,[git,'clone','--no-checkout',item['repository'],str(source)],root)
        run_process(job,[git,'-C',str(source),'checkout','--detach',item['commit']],root)
        run_process(job,[git,'-C',str(source),'submodule','update','--init','--recursive'],root)
        sdk = self.workspaces.child(identifier,'source/sdk',must_exist=True)
        actual = subprocess.run([git,'-C',str(sdk),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
        if actual != item['sdk_commit']: raise ValueError('Pinned SDK commit mismatch; refusing profile patches')
        destination = self.workspaces.child(identifier,'source/assets')
        destination.mkdir(exist_ok=True)
        for path in self.workspaces.tree_files(identifier,'assets'):
            target = destination / path.relative_to(root/'assets')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists(): raise ValueError('Upstream assets collide with extracted data')
            try: os.link(path,target)
            except OSError: shutil.copy2(path,target)
        self.apply_fixes(identifier,job)
        return {'source_commit':item['commit'],'sdk_commit':actual,'path':str(source),'playability':'not_assessed'}

    def apply_fixes(self, identifier: str, job: Job) -> dict:
        root, item = self.context(identifier)
        require_match(item,inspect_xbe(self.workspaces.child(identifier,'assets/'+item['xbe'],must_exist=True)))
        sdk = self.workspaces.child(identifier,'source/sdk',must_exist=True)
        patch = Path(str(files('xbox_port_mcp').joinpath('resources/sdk-storage.patch')))
        git = tool('git')
        already = subprocess.run([git,'apply','--reverse','--check',str(patch)],cwd=sdk,capture_output=True).returncode == 0
        if not already:
            run_process(job,[git,'apply','--check',str(patch)],sdk)
            run_process(job,[git,'apply',str(patch)],sdk)
        metadata = self.workspaces.metadata(identifier)
        if metadata.get('language','en') == 'es':
            kernel = self.workspaces.child(identifier,'source/sdk/runtime/kernel/xboxkrnl.cpp',must_exist=True)
            text = kernel.read_text(encoding='utf-8')
            replacements = [('case 7: v = 1; break;','case 7: v = 5; break;'),
                            ('W32(value + 0xE8, 1);','W32(value + 0xE8, 5);')]
            for before, after in replacements:
                if before not in text and after not in text: raise ValueError('Unrecognized language-setting source')
                text = text.replace(before,after)
            kernel.write_text(text,encoding='utf-8')
            hooks = self.workspaces.child(identifier,'source/src/game/hooks.cpp',must_exist=True)
            text = hooks.read_text(encoding='utf-8')
            marker = '// xbox-port-mcp: shipped Spanish resources'
            if marker not in text:
                text += '\n' + marker + '\n#include "core/log.h"\nX86_FUNC(__imp__sub_000133F0);\nX86_FUNC(sub_000133F0) {\n    __imp__sub_000133F0(ctx, base);\n    X86_MEM32(0x35D860u) = 6;\n    X86_MEM8(0x310CFCu) = 6;\n    LOGI("xbox-port-mcp: Spanish resources selected");\n}\n'
                hooks.write_text(text,encoding='utf-8')
        return {'storage_patch':'already_applied' if already else 'applied','language':metadata.get('language','en')}

    def configure(self, identifier, root, item, job):
        source = self.workspaces.child(identifier,'source',must_exist=True)
        self.apply_fixes(identifier,job)
        args = [tool('cmake'),'--preset',item['preset']]
        if os.environ.get('XBOX_PORT_ALLOW_NETWORK') != '1': args.append('-DFETCHCONTENT_FULLY_DISCONNECTED=ON')
        llvm = os.environ.get('XBOX_PORT_LLVM_BIN')
        if llvm:
            folder = Path(llvm).resolve(strict=True)
            extension = '.exe' if os.name == 'nt' else ''
            for key, binary in [('CMAKE_C_COMPILER','clang'),('CMAKE_CXX_COMPILER','clang++'),
                                ('CMAKE_LINKER','lld-link'),('CMAKE_AR','llvm-ar'),('CMAKE_RANLIB','llvm-ranlib')]:
                path = folder / (binary + extension)
                if not path.is_file(): raise ValueError(f'Incomplete LLVM directory: {binary}')
                args.append(f'-D{key}={path.as_posix()}')
        args += ['-DCMAKE_C_FLAGS_RELEASE=-O2','-DCMAKE_CXX_FLAGS_RELEASE=-O2']
        run_process(job,args,source)
        return {'configured':True,'preset':item['preset'],'playability':'not_assessed'}

    def compile(self, identifier, root, item, job):
        source = self.workspaces.child(identifier,'source',must_exist=True)
        run_process(job,[tool('cmake'),'--build','--preset',item['preset'],'--parallel','2'],source)
        executable = self.workspaces.child(identifier,f'source/out/build/{item["preset"]}/{item["executable"]}',must_exist=True)
        from .formats import sha256_file
        return {'executable':str(executable),'sha256':sha256_file(executable),'playability':'not_assessed'}

    def artwork(self, identifier, root, item, job):
        from .packaging import create_artwork
        return create_artwork(self.workspaces,identifier,item,job,tool('ffmpeg'))

    def installer(self, identifier, root, item, job):
        from .packaging import create_installer
        return create_installer(self.workspaces,identifier,item,job,tool('iscc'))

    def iso(self, identifier, root, item, job):
        from .packaging import create_disc
        return create_disc(self.workspaces,identifier,item,job,tool('powershell'))

    def verify_iso(self, identifier, root, item, job):
        from .packaging import verify_disc
        return verify_disc(self.workspaces.child(identifier,'game-windows.iso',must_exist=True),
                           self.workspaces.child(identifier,'disc/Instalar.exe',must_exist=True))
