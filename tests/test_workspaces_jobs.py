from pathlib import Path
import sys
import time
import pytest
from xbox_port_mcp.workspaces import Workspaces
from xbox_port_mcp.jobs import Jobs,run_process
from xbox_port_mcp.pipeline import execution_allowed

def wait(jobs,identifier):
    for _ in range(300):
        result=jobs.status(identifier)
        if result['state'] not in ('running','queued'):return result
        time.sleep(.02)
    raise AssertionError('job did not finish')

def test_boundaries_and_link_escape(tmp_path):
    allowed=tmp_path/'input';allowed.mkdir()
    outside=tmp_path/'outside';outside.mkdir();(outside/'secret').write_text('private')
    ws=Workspaces(tmp_path/'work',[allowed]);meta=ws.create('sims-bustin-out-usa')
    assert ws.get(meta['id']).is_relative_to(ws.root)
    with pytest.raises(ValueError):ws.read_path(str(outside/'secret'))
    with pytest.raises(ValueError):ws.get('../outside')
    with pytest.raises(ValueError):ws.child(meta['id'],'../outside/file')
    link=Path(meta['path'])/'linked'
    try:link.symlink_to(outside,target_is_directory=True)
    except OSError:pytest.skip('Symlink creation needs platform privilege')
    with pytest.raises(ValueError):ws.child(meta['id'],'linked/secret')

def test_execution_requires_opt_in(monkeypatch):
    monkeypatch.delenv('XBOX_PORT_ALLOW_EXECUTION',raising=False)
    with pytest.raises(ValueError,match='disabled'):execution_allowed()

def test_jobs_capture_failure_and_bound_logs(tmp_path):
    jobs=Jobs()
    def action(job):run_process(job,[sys.executable,'-c','import sys;print("x"*100000);sys.exit(7)'],tmp_path)
    identifier=jobs.start('work','test',action,tmp_path)['job_id'];result=wait(jobs,identifier)
    assert result['state']=='failed' and 'code 7' in result['error']
    assert len(result['log_tail'])<=16384
    assert len((tmp_path/f'job-{identifier}.log').read_text())<=65536
    jobs.close()

def test_cancel_owns_process_and_unknown_id(tmp_path):
    jobs=Jobs()
    def action(job):run_process(job,[sys.executable,'-c','import time;time.sleep(20)'],tmp_path)
    identifier=jobs.start('work','test',action,tmp_path)['job_id']
    for _ in range(100):
        if jobs.items[identifier].process is not None:break
        time.sleep(.01)
    with pytest.raises(ValueError):jobs.cancel('1234')
    jobs.cancel(identifier)
    assert wait(jobs,identifier)['state']=='cancelled'
    jobs.close()

def test_workspace_exclusivity(tmp_path):
    jobs=Jobs()
    def action(job):
        while not job.cancelled.wait(.01):pass
        raise InterruptedError('cancelled')
    identifier=jobs.start('work','first',action,tmp_path)['job_id']
    with pytest.raises(ValueError,match='active'):jobs.start('work','second',action,tmp_path)
    jobs.cancel(identifier);wait(jobs,identifier);jobs.close()

def test_cancel_after_child_closes_output(tmp_path):
    jobs=Jobs()
    code='import os,time;os.close(1);os.close(2);time.sleep(3)'
    identifier=jobs.start('work','test',lambda j:run_process(j,[sys.executable,'-c',code],tmp_path),tmp_path)['job_id']
    time.sleep(.6)
    started=time.monotonic();jobs.cancel(identifier);elapsed=time.monotonic()-started
    try:
        assert elapsed<1
        assert wait(jobs,identifier)['state']=='cancelled'
    finally:jobs.close()


def test_recursive_tree_rejects_reparse_point(tmp_path,monkeypatch):
    ws=Workspaces(tmp_path/'work',[]);meta=ws.create('sims-bustin-out-usa')
    root=Path(meta['path']);(root/'assets/nested').mkdir(parents=True)
    (root/'assets/nested/private').write_text('do not publish')
    original=Path.lstat
    class Reparse:
        st_file_attributes=0x400
    def fake(path,*args,**kwargs):
        return Reparse() if path.name=='nested' else original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',fake)
    with pytest.raises(ValueError,match='[Rr]eparse'):
        list(ws.tree_files(meta['id'],'assets'))
