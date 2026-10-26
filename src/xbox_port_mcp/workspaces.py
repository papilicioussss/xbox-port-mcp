from __future__ import annotations
import json
import os
from pathlib import Path
import re
import uuid

class Workspaces:
    def __init__(self, root: Path, input_roots: list[Path]):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.inputs = [p.expanduser().resolve(strict=True) for p in input_roots] + [self.root]

    def read_path(self, name: str) -> Path:
        original = Path(name).expanduser()
        path = original.resolve()
        if not any(path.is_relative_to(root) for root in self.inputs):
            raise ValueError('Input is outside XBOX_PORT_INPUT_ROOTS and the workspace root')
        if not path.is_file(): raise ValueError('Input is not a regular file')
        return path

    def get(self, identifier: str) -> Path:
        if not re.fullmatch(r'[0-9a-f]{32}', identifier): raise ValueError('Invalid workspace id')
        original = self.root / identifier
        path = original.resolve(strict=True)
        if original.is_symlink() or getattr(original, "is_junction", lambda: False)() or path.name != identifier or path.parent != self.root or not (path / 'workspace.json').is_file():
            raise ValueError('Invalid workspace boundary')
        return path

    def child(self, identifier: str, relative: str, *, must_exist=False) -> Path:
        root = self.get(identifier)
        path = root / relative
        # Reject all symlink components, including links to another workspace.
        current = root
        for component in Path(relative).parts:
            if component in ('.', '..') or Path(component).is_absolute():
                raise ValueError('Invalid workspace-relative path')
            current /= component
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)(): raise ValueError('Workspace symlinks are not allowed')
        resolved = path.resolve(strict=must_exist)
        if not resolved.is_relative_to(root): raise ValueError('Path escapes workspace')
        return resolved

    def tree_files(self, identifier: str, relative: str) -> list[Path]:
        root = self.child(identifier,relative,must_exist=True)
        result = []
        pending = [root]
        while pending:
            current = pending.pop()
            info = current.lstat()
            if getattr(info,'st_file_attributes',0) & 0x400:
                raise ValueError('Asset reparse points are not allowed')
            if current.is_symlink():
                raise ValueError('Asset symlinks are not allowed')
            resolved = current.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise ValueError('Asset path escapes its root')
            if current.is_dir():
                pending.extend(current.iterdir())
            elif current.is_file():
                result.append(current)
            else:
                raise ValueError('Assets must be regular files or directories')
        return result

    def create(self, profile: str, language: str = "en") -> dict:
        identifier = uuid.uuid4().hex
        root = self.root / identifier
        root.mkdir()
        data = {'id': identifier, 'profile': profile, 'format_version': 1, 'language': language}
        (root / 'workspace.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
        return {**data, 'path': str(root)}

    def metadata(self, identifier: str) -> dict:
        return json.loads((self.get(identifier) / 'workspace.json').read_text(encoding='utf-8'))

def from_environment() -> Workspaces:
    default = Path.home() / 'XboxPorts' if os.name == 'nt' else Path.home() / '.local' / 'share' / 'xbox-port-mcp' / 'workspaces'
    root = Path(os.environ.get('XBOX_PORT_WORKSPACE_ROOT', str(default)))
    inputs = json.loads(os.environ.get('XBOX_PORT_INPUT_ROOTS', '[]'))
    if not isinstance(inputs, list) or not all(isinstance(x, str) for x in inputs):
        raise ValueError('XBOX_PORT_INPUT_ROOTS must be a JSON array of absolute directories')
    return Workspaces(root, [Path(p) for p in inputs])
