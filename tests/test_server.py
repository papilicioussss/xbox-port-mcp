import asyncio
import json
import time
import pytest
from mcp import Client
from xbox_port_mcp.server import create_server
from xbox_port_mcp.workspaces import Workspaces
from conftest import make_iso

def test_protocol_roundtrip_and_errors(tmp_path):
    source=tmp_path/'inputs';source.mkdir();image=make_iso(source/'synthetic.iso')
    server,jobs=create_server(Workspaces(tmp_path/'work',[source]))
    async def scenario():
        async with Client(server) as client:
            listed=await client.list_tools()
            names={tool.name for tool in listed.tools}
            assert {'list_profiles','doctor','inspect_iso','create_workspace','start_step','get_job','cancel_job'}<=names
            result=await client.call_tool('inspect_iso',{'path':str(image)})
            assert not result.is_error and result.structured_content['file_count']==1
            invalid=await client.call_tool('inspect_iso',{'path':str(tmp_path/'not-allowed.iso')})
            assert invalid.is_error
            result=await client.call_tool('create_workspace',{'profile_id':'sims-bustin-out-usa'})
            assert not result.is_error
            identifier=result.structured_content['id']
            started=await client.call_tool('start_step',{'workspace_id':identifier,'step':'extract','input_path':str(image)})
            job_id=started.structured_content['job_id']
            for _ in range(200):
                response=await client.call_tool('get_job',{'job_id':job_id})
                if response.structured_content['state'] not in ['running','queued']:break
                await asyncio.sleep(.01)
            assert response.structured_content['state']=='succeeded'
            unsupported=await client.call_tool('start_step',{'workspace_id':identifier,'step':'run-anything'})
            assert unsupported.is_error
            read=await client.read_resource('xbox-port://profiles')
            assert read
    try:asyncio.run(scenario())
    finally:jobs.close()


def test_stdio_transport(tmp_path):
    import os,sys
    from mcp.client.stdio import StdioServerParameters
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join(sys.path)
    env.pop('XBOX_PORT_ALLOW_EXECUTION',None)
    env['XBOX_PORT_WORKSPACE_ROOT']=str(tmp_path/'stdio-work')
    env['XBOX_PORT_INPUT_ROOTS']='[]'
    async def scenario():
        params=StdioServerParameters(command=sys.executable,args=['-m','xbox_port_mcp'],env=env)
        async with Client(params,mode='legacy') as client:
            result=await client.list_tools()
            assert len(result.tools)==9
            report=await client.call_tool('doctor',{})
            assert not report.is_error
            assert report.structured_content['execution_enabled'] is False
    asyncio.run(scenario())
