"""Bounded, read-only XDVDFS/XBE inspection; transactional extraction.

Implemented here from the file layouts, not a vendored game or port tool.
All offsets in a directory record refer to the game partition, not the ISO.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tempfile

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
BASES = (0, 0x18300000, 0xFD90000, 0x2080000, 0x1FB20000)

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

@dataclass(frozen=True)
class Entry:
    path: str
    offset: int
    size: int
    directory: bool

def safe_name(name: str) -> None:
    if not name or name in ('.', '..') or re.search(r'[\\/:*?"<>|\x00-\x1f]', name):
        raise ValueError(f'Unsafe disc filename: {name!r}')
    if name[-1:] in (' ', '.') or name.split('.')[0].upper() in {
        'CON', 'PRN', 'AUX', 'NUL', *(f'COM{x}' for x in range(10)), *(f'LPT{x}' for x in range(10))
    }:
        raise ValueError(f'Nonportable disc filename: {name!r}')

class Xdvdfs:
    def __init__(self, path: Path):
        self.path = path
        self.file = path.open('rb')
        self.length = path.stat().st_size
        self.base = -1
        try:
            for base in BASES:
                if base + 33 * SECTOR > self.length:
                    continue
                data = self.read(base + 32 * SECTOR, SECTOR)
                if data[:20] == MAGIC and data[-20:] == MAGIC:
                    self.base = base
                    self.root_sector, self.root_size = struct.unpack_from('<II', data, 20)
                    break
            if self.base < 0:
                raise ValueError('No supported XDVDFS descriptor; encrypted or unsupported layouts need another reader')
        except BaseException:
            self.file.close()
            raise

    def __enter__(self): return self
    def __exit__(self, *_): self.file.close()

    def read(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > self.length:
            raise ValueError('Disc extent lies outside the image')
        self.file.seek(offset)
        data = self.file.read(size)
        if len(data) != size:
            raise ValueError('Short disc read')
        return data

    def entries(self) -> list[Entry]:
        result: list[Entry] = []
        directories: set[tuple[int, int]] = set()
        names: set[str] = set()
        budget = 64 * 1024 * 1024

        def visit(sector: int, size: int, parent: str, depth: int):
            nonlocal budget
            if depth > 48:
                raise ValueError('Directory nesting limit exceeded')
            if size == 0:
                return
            key = (sector, size)
            if key in directories:
                raise ValueError('Cyclic or repeated directory extent')
            directories.add(key)
            if size > 16 * 1024 * 1024 or size > budget:
                raise ValueError('Directory-table byte limit exceeded')
            budget -= size
            table = self.read(self.base + sector * SECTOR, size)
            pending = [0]
            seen: set[int] = set()
            children = []
            while pending:
                at = pending.pop()
                if at in seen:
                    raise ValueError('Cyclic directory tree')
                seen.add(at)
                if at + 14 > len(table):
                    raise ValueError('Invalid directory node')
                left, right, data_sector, count, attr, length = struct.unpack_from('<HHIIBB', table, at)
                if length == 0 or at + 14 + length > len(table):
                    raise ValueError('Invalid directory filename length')
                name = table[at + 14:at + 14 + length].decode('latin1')
                safe_name(name)
                full = f'{parent}/{name}' if parent else name
                folded = full.casefold()
                if folded in names:
                    raise ValueError('Case-insensitive filename collision')
                names.add(folded)
                offset = self.base + data_sector * SECTOR
                if offset + count > self.length:
                    raise ValueError('File or directory extent lies outside image')
                directory = bool(attr & 0x10)
                result.append(Entry(full, offset, count, directory))
                if len(result) > 100_000:
                    raise ValueError('Entry limit exceeded')
                if directory:
                    children.append((data_sector, count, full, depth + 1))
                for pointer in (right, left):
                    if pointer:
                        pending.append(pointer * 4)
            for child in children:
                visit(*child)

        visit(self.root_sector, self.root_size, '', 0)
        # A file cannot also be a parent of another entry.
        files = {e.path.casefold() for e in result if not e.directory}
        for entry in result:
            if any(str(p).casefold() in files for p in PurePosixPath(entry.path).parents if str(p) != '.'):
                raise ValueError('File/directory path conflict')
        return result

    def extract(self, target: Path, cancelled=lambda: False) -> dict:
        if target.exists() or target.is_symlink():
            raise ValueError('Extraction destination already exists; refusing overwrite')
        entries = self.entries()  # Validate the complete tree before writing.
        total = sum(e.size for e in entries if not e.directory)
        if total > min(self.length,16 * 1024**3):
            raise ValueError('Extracted byte budget exceeded')
        before = self.path.stat()
        staging = Path(tempfile.mkdtemp(prefix='.extract-', dir=target.parent))
        try:
            for entry in sorted(entries, key=lambda e: (len(PurePosixPath(e.path).parts), e.path)):
                if cancelled(): raise InterruptedError('Extraction cancelled')
                dest = staging.joinpath(*PurePosixPath(entry.path).parts)
                if entry.directory:
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                self.file.seek(entry.offset)
                remaining = entry.size
                with dest.open('xb') as output:
                    while remaining:
                        if cancelled(): raise InterruptedError('Extraction cancelled')
                        block = self.file.read(min(remaining, 1024 * 1024))
                        if not block: raise ValueError('Image changed or truncated during extraction')
                        output.write(block)
                        remaining -= len(block)
            after = self.path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('Image changed during extraction')
            staging.rename(target)
        finally:
            if staging.exists(): shutil.rmtree(staging)
        return {'files': sum(not e.directory for e in entries), 'bytes': sum(e.size for e in entries if not e.directory)}

def inspect_xbe_bytes(data: bytes) -> dict:
    if len(data) < 0x178 or data[:4] != b'XBEH':
        raise ValueError('Not an original Xbox XBE')
    u32 = lambda at: struct.unpack_from('<I', data, at)[0]
    base = u32(0x104)
    cert = u32(0x118) - base
    if cert < 0x178 or cert + 0xA0 > len(data):
        raise ValueError('XBE certificate outside file')
    sections = u32(0x11C)
    if sections > 128: raise ValueError('XBE section limit exceeded')
    table = u32(0x120) - base
    if table < 0 or table + sections * 56 > len(data):
        raise ValueError('XBE section table outside file')
    for index in range(sections):
        at = table + index * 56
        raw, size = u32(at + 12), u32(at + 16)
        if raw + size > len(data): raise ValueError('XBE section data outside file')
    return {'format': 'XBE', 'title_id': f'{u32(cert + 8):08X}',
            'title': data[cert + 12:cert + 92].decode('utf-16le', errors='replace').split('\0')[0],
            'image_base': base, 'sections': sections, 'init_flags': u32(0x124),
            'sha1': hashlib.sha1(data).hexdigest(), 'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data)}

def inspect_xbe(path: Path) -> dict:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('XBE inspection limit is 64 MiB')
    return inspect_xbe_bytes(path.read_bytes())

def inspect_iso(path: Path, offset: int = 0, limit: int = 50) -> dict:
    if offset < 0 or not 1 <= limit <= 500: raise ValueError('Invalid pagination')
    with Xdvdfs(path) as image:
        entries = image.entries()
        executable = next((e for e in entries if e.path.casefold() == 'default.xbe' and not e.directory), None)
        xbe = None
        if executable and executable.size <= 64 * 1024 * 1024:
            xbe = inspect_xbe_bytes(image.read(executable.offset, executable.size))
        return {'format': 'XDVDFS', 'partition_base': image.base, 'image_bytes': image.length,
                'entry_count': len(entries), 'file_count': sum(not e.directory for e in entries),
                'entries': [asdict(e) for e in entries[offset:offset + limit]],
                'next_offset': offset + limit if offset + limit < len(entries) else None, 'xbe': xbe}
