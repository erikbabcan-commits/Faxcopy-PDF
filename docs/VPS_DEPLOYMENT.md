# Whole application on a Docker VPS: pdf.vorkei.com

This is an opt-in deployment candidate, not an automatic production deployment.
The Vercel project/domain reservation is not used by this topology. Do not add
the previously proposed Vercel CNAME to WebSupport.

## Required owner inputs

Supply the VPS public IP/hostname, SSH username, approved access method and target
path/account. Never paste a private key, password or token into a chat or commit.
Confirm OS/Docker/Compose support, free disk and a backup destination/budget.
Suggested starting capacity is 4 vCPU, 8 GiB RAM and separately backed-up storage;
this is not a measured load-capacity guarantee. Do not treat shared web hosting
at the registrar as an existing Docker VPS without checking the actual service.

## Prepare and review

Use Docker Compose >= 2.24.4. Review the exact release SHA and image digests.
Choose an unused RFC1918 /24 through /29 Docker subnet; check it against host,
VPN and existing Docker routes. Reserve its second usable address for Caddy.
The values below illustrate the required arguments; verify subnet availability
on the actual VPS before using them.

```sh
python scripts/make_vps_env.py --domain pdf.vorkei.com \
  --proxy-subnet 172.30.250.0/29 --proxy-ip 172.30.250.2
python scripts/check_vps_config.py
docker compose --env-file .env.vps -f compose.yaml -f compose.vps.yaml build
```

The generator creates a new mode-0600 `.env.vps` with independent random DB
passwords and scanner token. Existing files are never overwritten. Protect it
with a secret manager/encrypted backup. `check_vps_config.py` inspects rendered
configuration internally without printing connection strings or secrets.

API/worker/migrator use production mode and secure cookies for the exact HTTPS
origin. Only Caddy publishes 80/443. API has no host port; DB and scanner stay on
internal networks. Uvicorn trusts only Caddy's fixed internal IP and Caddy
replaces incoming forwarding claims, preserving per-client login limiting.
Existing upstream proxies/CDNs require a separately reviewed trusted-hop plan.

PostgreSQL, documents, Caddy certificates and Caddy configuration use persistent
volumes. Caddy runs as UID 10001 with a read-only root, a writable temporary
directory and only NET_BIND_SERVICE capability. There is no Docker socket mount.
The body cap is 27 MiB for the default 25 MiB PDF limit plus multipart overhead;
changing the app upload limit requires reviewing the proxy limit too.

## Owner-approved first launch

First launch initializes a **fresh** database and runs migrations. Existing DB
volumes need the separate grant/migration/legacy-preview plan in RELEASE_GATES.md
and a verified backup before any change. Do not run this blindly on an existing
installation or use `down -v`.

After target/release/migration approval, allow inbound 80/443 for HTTP challenge
and HTTPS, restrict SSH to the administrator's approved source, and keep DB,
scanner and API ports closed. Do not replace SSH/firewall rules automatically.
Verify provider firewall rules and Docker's actual published ports separately.

WebSupport DNS must point to the **verified VPS address**:

| Type | Host | Value |
|---|---|---|
| A | pdf | The supplied VPS public IPv4 |
| AAAA | pdf | Only the supplied working public IPv6, if supported |

Remove/replace only conflicting exact `pdf` records, including a previous CNAME.
Preserve apex, wildcard, mail records and nameservers. Do not keep an inherited
or explicit old IPv6 answer if it sends clients to the previous host. If a
wildcard AAAA remains elsewhere in the zone, verify the effective `pdf` answer
after adding its explicit A record; do not delete the entire wildcard by default.
No concrete A/AAAA value can be given until the VPS address is supplied.

```sh
docker compose --env-file .env.vps -f compose.yaml -f compose.vps.yaml up -d --no-build
docker compose --env-file .env.vps -f compose.yaml -f compose.vps.yaml ps
```

Caddy obtains/renews the public certificate once DNS and inbound challenge ports
work. Verify HTTPS using normal certificate validation, never an insecure flag.
Test health, login with synthetic data, full PDF processing, wrong-origin/CSRF
rejection, tenant isolation and resource limits at the release SHA. Only then
record `https://pdf.vorkei.com` as a working production URL. Do not log the owner
password or create a public default account.

## Operations and remaining gates

Configure monitoring, disk alerts, retained/encrypted off-host backups and a
target-specific restore drill. The separate synthetic recovery PR is evidence
for its test scenario, not proof of this VPS's backup/restore. Preserve DB,
document and certificate volumes during rollbacks and do not drop a schema
column while newer workers run. Stop writers for a consistent snapshot.

The proxy adds body/header/time bounds; Caddy core here does not add an upload
burst limiter or DDoS protection. Configure and validate those controls for the
actual provider/edge before opening to untrusted users. Scanner egress isolation
and access to the host/DB must be checked on the actual server. Real certificate
issuance, SSH/firewall, disk persistence, provider limits and production backup
restoration remain NOT TESTED until that authorized target exists.
