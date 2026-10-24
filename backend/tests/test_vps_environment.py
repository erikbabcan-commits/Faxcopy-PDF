import importlib.util
from pathlib import Path
import stat
import pytest

spec=importlib.util.spec_from_file_location('make_vps_env',Path(__file__).resolve().parents[2]/'scripts/make_vps_env.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_vps_configuration_is_private_unique_and_never_overwritten(tmp_path):
    target=tmp_path/'configuration'
    module.generate('pdf.vorkei.com','172.30.250.0/29','172.30.250.2',target)
    before=target.read_bytes()
    assert stat.S_IMODE(target.stat().st_mode)==0o600
    fields=dict(line.split('=',1) for line in before.decode().splitlines())
    assert fields['APP_ORIGIN']=='https://pdf.vorkei.com' and fields['SECURE_COOKIES']=='true'
    assert len({fields[name] for name in ('POSTGRES_PASSWORD','MIGRATION_PASSWORD','RUNTIME_PASSWORD','SCANNER_TOKEN')})==4
    with pytest.raises(FileExistsError):module.generate('pdf.vorkei.com','172.30.250.0/29','172.30.250.2',target)
    assert target.read_bytes()==before


@pytest.mark.parametrize('domain,subnet,ip',[
    ('https://pdf.vorkei.com','172.30.250.0/29','172.30.250.2'),
    ('pdf.vorkei.com\nINJECT=x','172.30.250.0/29','172.30.250.2'),
    ('localhost','172.30.250.0/29','172.30.250.2'),
    ('pdf.vorkei.com','8.8.8.0/24','8.8.8.2'),
    ('pdf.vorkei.com','172.30.250.0/29','*'),
    ('pdf.vorkei.com','172.30.250.0/29','172.30.251.2'),
    ('pdf.vorkei.com','172.30.250.0/29','172.30.250.1'),
    ('pdf.vorkei.com','172.30.250.0/29','172.30.250.7'),
])
def test_invalid_vps_input_does_not_create_file(tmp_path,domain,subnet,ip):
    target=tmp_path/'configuration'
    with pytest.raises(ValueError):module.generate(domain,subnet,ip,target)
    assert not target.exists()


@pytest.mark.parametrize('peer,expected,scheme',[
    ('172.30.250.2','198.51.100.7','https'),
    ('198.51.100.9','198.51.100.9','http'),
])
def test_forwarded_client_claims_are_accepted_only_from_the_proxy(peer,expected,scheme):
    from fastapi.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    async def echo(request):
        return JSONResponse({'client':request.client.host,'scheme':request.url.scheme})
    app=Starlette(routes=[Route('/',echo)])
    with TestClient(ProxyHeadersMiddleware(app,trusted_hosts='172.30.250.2'),client=(peer,12345)) as client:
        response=client.get('/',headers={'X-Forwarded-For':'198.51.100.7','X-Forwarded-Proto':'https'})
    assert response.json()=={'client':expected,'scheme':scheme}
