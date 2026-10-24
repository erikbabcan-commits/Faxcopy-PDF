"""Generate local Docker pilot secrets without printing them or overwriting files."""
from pathlib import Path
import os
import secrets

root=Path(__file__).resolve().parents[1]
target=root/'.env'
if target.exists():raise SystemExit('.env already exists; it was not changed.')
text=(root/'.env.example').read_text(encoding='utf-8')
text=text.replace('REPLACE_WITH_RANDOM_DATABASE_PASSWORD',secrets.token_hex(32))
text=text.replace('REPLACE_WITH_RANDOM_MIGRATION_PASSWORD',secrets.token_hex(32))
text=text.replace('REPLACE_WITH_RANDOM_RUNTIME_PASSWORD',secrets.token_hex(32))
text=text.replace('REPLACE_WITH_RANDOM_SCANNER_TOKEN',secrets.token_hex(32))
fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text)
print('Created .env for the loopback-only Docker pilot. Secrets were not printed.')
