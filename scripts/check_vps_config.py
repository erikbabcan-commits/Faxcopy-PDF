"""Validate the rendered VPS topology without starting containers or exposing secrets."""
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def main():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['docker','compose','-p','presspilot-vps','--env-file','.env.vps','-f','compose.yaml','-f','compose.vps.yaml','config','--format','json'],cwd=root,capture_output=True,text=True,check=True)
    config=json.loads(result.stdout)
    assert config['name']=='presspilot-vps'
    services=config['services'];api=services['api'];edge=services['edge']
    for name in ('api','db','scanner','worker','migrate'):
        assert not services[name].get('ports'), 'Only the TLS proxy may publish ports'
    assert {str(p['published']) for p in edge['ports']}=={'80','443'}
    for name in ('api','worker','migrate'):
        environment=services[name]['environment']
        assert environment['APP_ENV']=='production' and str(environment['SECURE_COOKIES']).lower()=='true'
        assert environment['APP_ORIGIN']=='https://'+edge['environment']['APP_DOMAIN']
    assert urlsplit(api['environment']['DATABASE_URL']).username=='presspilot_runtime'
    assert urlsplit(services['migrate']['environment']['DATABASE_URL']).username=='presspilot_migrator'
    assert set(api['networks'])=={'proxy','database'}
    assert set(edge['networks'])=={'proxy'}
    assert set(services['worker']['networks'])=={'database','scan'}
    assert set(services['scanner']['networks'])=={'scan'}
    assert config['networks']['database']['internal'] and config['networks']['scan']['internal']
    proxy_ip=edge['networks']['proxy']['ipv4_address']
    command=api['command']
    assert command[command.index('--forwarded-allow-ips')+1]==proxy_ip and proxy_ip!='*'
    assert edge['read_only'] and edge['user']=='10001:10001'
    print('VPS topology validated: private services, production origin/cookies, exact trusted proxy and separate DB roles')


if __name__=='__main__':
    main()
