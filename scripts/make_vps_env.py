"""Create a new private VPS configuration; never deploy, print secrets or overwrite."""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import secrets


def generate(domain, subnet, proxy_ip, target):
    domain = domain.lower()
    labels = domain.split('.')
    if len(domain) > 253 or len(labels) < 2 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
        raise ValueError('Supply a DNS hostname without scheme, path or port')
    network = ipaddress.IPv4Network(subnet, strict=True)
    address = ipaddress.IPv4Address(proxy_ip)
    private = [ipaddress.IPv4Network(s) for s in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
    if not 24 <= network.prefixlen <= 29 or not any(network.subnet_of(n) for n in private):
        raise ValueError('Use an unused RFC1918 /24 through /29 subnet')
    if address not in network or address in (network.network_address, network.broadcast_address, network.network_address + 1):
        raise ValueError('Proxy IP must be usable and not the Docker gateway')
    values = {'APP_DOMAIN': domain, 'APP_ENV':'production', 'APP_ORIGIN':'https://'+domain,
              'SECURE_COOKIES':'true','PROXY_SUBNET':str(network),'PROXY_IP':str(address),
              'MAX_UPLOAD_MB':'25','SCAN_TIMEOUT_SECONDS':'45','LLM_BASE_URL':'','LLM_MODEL':''}
    for name in ('POSTGRES_PASSWORD','MIGRATION_PASSWORD','RUNTIME_PASSWORD','SCANNER_TOKEN'):
        values[name] = secrets.token_hex(32)
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as output:
        output.write('\n'.join(k+'='+v for k,v in values.items())+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain',required=True)
    parser.add_argument('--proxy-subnet',required=True)
    parser.add_argument('--proxy-ip',required=True)
    args = parser.parse_args()
    generate(args.domain,args.proxy_subnet,args.proxy_ip,Path(__file__).resolve().parents[1]/'.env.vps')
    print('Created private .env.vps; values were not printed. Verify subnet availability before starting Docker.')
