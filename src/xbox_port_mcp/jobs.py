"""In-process job ownership, bounded logs, and owned child-process cancellation."""
from __future__ import annotations
import ctypes
from dataclasses import dataclass, field
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import uuid

@dataclass
class Job:
    id: str
    workspace: str
    step: str
    state: str = 'queued'
    result: dict | None = None
    error: str | None = None
    tail: str = ''
    cancelled: threading.Event = field(default_factory=threading.Event)
    process: subprocess.Popen | None = None
    win_job: int | None = None
    thread: threading.Thread | None = None
    process_lock: threading.RLock = field(default_factory=threading.RLock)

    def log(self, text: str): self.tail = (self.tail + text)[-65536:]

def windows_job(process: subprocess.Popen) -> int | None:
    if os.name != 'nt': return None
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_ = [('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
                    ('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',w.DWORD),
                    ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class Extended(ctypes.Structure):
        _fields_ = [('basic',Basic),('io',ctypes.c_uint64 * 6),('process_memory',ctypes.c_size_t),
                    ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE,w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateJobObjectW(None,None)
    limits = Extended(); limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE
    if not handle or not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,int(process._handle)):
        if handle: kernel.CloseHandle(handle)
        process.terminate()
        process.wait(timeout=10)
        raise RuntimeError('Cannot track the Windows child process; refusing to leave an unmanaged build')
    return handle

def run_process(job: Job, argv: list[str], cwd: Path, env: dict | None = None):
    if job.cancelled.is_set(): raise InterruptedError('Job cancelled')
    job.log('$ ' + ' '.join(argv) + '\n')
    kwargs = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    try:
        with job.process_lock:
            job.process = process
            job.win_job = windows_job(process)
            if job.cancelled.is_set(): terminate(job)
        assert process.stdout
        while block := process.stdout.read(4096):
            job.log(block.decode('utf-8', errors='replace'))
        while True:
            with job.process_lock:
                code = process.poll()
            if code is not None: break
            time.sleep(.02)
        if job.cancelled.is_set(): raise InterruptedError('Job cancelled')
        if code: raise RuntimeError(f'Process exited with code {code}; inspect the job log')
    finally:
        with job.process_lock:
            if process.returncode is None:
                terminate(job)
                process.wait(timeout=10)
            if job.win_job:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(job.win_job))
            job.win_job = None
            job.process = None

def terminate(job: Job):
    with job.process_lock:
        process = job.process
        if not process: return
        if os.name == 'nt':
            if job.win_job:
                ctypes.windll.kernel32.TerminateJobObject(ctypes.c_void_p(job.win_job),1)
            elif process.returncode is None: process.terminate()
        elif process.returncode is None:
            # Keep the root PID owned; do not reap it before killing its group.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass

class Jobs:
    def __init__(self):
        self.items: dict[str, Job] = {}
        self.lock = threading.Lock()

    def start(self, workspace: str, step: str, action, root: Path) -> dict:
        with self.lock:
            if any(j.workspace == workspace and j.state in ('queued','running') for j in self.items.values()):
                raise ValueError('Another job is active in this workspace')
            job = Job(uuid.uuid4().hex, workspace, step)
            self.items[job.id] = job
        def worker():
            job.state = 'running'
            terminal = 'failed'
            try:
                job.result = action(job)
                terminal = 'cancelled' if job.cancelled.is_set() else 'succeeded'
            except InterruptedError as exc:
                job.error = str(exc); terminal = 'cancelled'
            except Exception as exc:
                job.error = str(exc); terminal = 'cancelled' if job.cancelled.is_set() else 'failed'
            finally:
                try:
                    (root / f'job-{job.id}.log').write_text(job.tail, encoding='utf-8')
                except OSError as exc:
                    job.error = f'Could not persist job log: {exc}'
                    terminal = 'failed'
                job.state = terminal
        job.thread = threading.Thread(target=worker, daemon=True)
        job.thread.start()
        return {'job_id': job.id, 'state': 'queued', 'step': step}

    def status(self, identifier: str) -> dict:
        if identifier not in self.items: raise ValueError('Unknown job id; jobs are owned by this server session')
        job = self.items[identifier]
        return {'job_id': job.id, 'workspace_id':job.workspace, 'step':job.step, 'state':job.state,
                'result':job.result, 'error':job.error, 'log_tail':job.tail[-16384:]}

    def cancel(self, identifier: str) -> dict:
        self.status(identifier)
        job = self.items[identifier]
        if job.state in ('queued','running'):
            job.cancelled.set(); terminate(job)
        return self.status(identifier)

    def close(self):
        for job in list(self.items.values()):
            if job.state in ('queued','running'):
                job.cancelled.set(); terminate(job)
        for job in list(self.items.values()):
            if job.thread: job.thread.join(timeout=10)
