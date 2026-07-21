# Caddy VPS Reverse Proxy Runbook

Use this as a compact operational recipe for safely making Caddy the public HTTPS entrypoint on a VPS.

## 1. Read-only audit

Run Docker commands through the host's approved privilege mechanism. Do not assume membership in a particular group and do not publish usernames or group assignments.

```bash
hostname
date -Is
. /etc/os-release 2>/dev/null && printf '%s %s\n' "$PRETTY_NAME" "$(uname -r)"
ip -brief addr show scope global
ip route get 1.1.1.1 || true
ss -tulpen
systemctl --type=service --state=running --no-pager | egrep -i 'nginx|caddy|apache|traefik|docker|cloudflared|uvicorn|gunicorn|node|postgres|redis|certbot' || true
ufw status verbose || true
sudo -n iptables -S | head -200 || true
for c in docker docker-compose caddy nginx apache2 certbot cloudflared ufw; do printf '%-15s ' "$c"; command -v "$c" || true; done
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker network ls
```

Find relevant Compose/Caddy/Nginx files without dumping secrets:

```bash
python3 - <<'PY'
import os
for root in ['/home', '/opt', '/srv']:
  if not os.path.exists(root): continue
  for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in {'.git','node_modules','.venv','venv','__pycache__'}]
    if dirpath.count(os.sep)-root.count(os.sep)>4:
      dirnames[:] = []
    for f in filenames:
      lf=f.lower()
      if lf in ('docker-compose.yml','docker-compose.yaml','compose.yml','compose.yaml','caddyfile') or 'nginx' in lf:
        print(os.path.join(dirpath, f))
PY
```

## 2. DNS check

Expected: A points to the VPS IPv4; AAAA either points to the VPS IPv6 or is absent.

```bash
for n in example.com app.example.com; do
  echo "-- $n"
  getent ahostsv4 "$n" | head -5 || true
  getent ahostsv6 "$n" | head -5 || true
done
```

If records point elsewhere, do not claim HTTPS is verified. You can still prepare Caddy and run local Host-header checks.

## 3. Backup

```bash
set -Eeuo pipefail
umask 077
TS=$(date -u +%Y%m%dT%H%M%SZ)
B="$HOME/backups/caddy-setup-$TS"
install -d -m 0700 "$B"
{
  echo "# audit $TS"
  hostname; date -Is; ip -brief addr show scope global || true
  echo '## ss'; ss -tulpen || true
  echo '## docker ps'; docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || true
  echo '## iptables'; sudo -n iptables -S || true
  echo '## ufw'; sudo -n ufw status verbose || true
} > "$B/audit.txt" 2>&1
backup_tree() {
  local source_path="$1" output_name="$2"
  [[ ! -d "/$source_path" ]] || sudo -n tar -C / -czf - "$source_path" > "$B/$output_name"
}
backup_tree etc/caddy etc-caddy.tgz
backup_tree etc/nginx etc-nginx.tgz
backup_tree etc/apache2 etc-apache2.tgz
backup_tree etc/letsencrypt etc-letsencrypt.tgz
printf '%s\n' "$B"
```

Do not continue if an existing configuration directory fails to archive; fix the backup error first.

Back up reviewed configuration files before editing. Handle `.env` and other secret-bearing files through the host's approved encrypted or access-controlled backup process; do not add them to this general audit bundle or print them.

## 4. Resolve `:443` conflicts

If another approved Docker container owns `:443`, record only the non-secret state required for rollback:

```bash
CONFLICTING_CONTAINER="${CONFLICTING_CONTAINER:?set CONFLICTING_CONTAINER to the discovered container name}"
ORIGINAL_RESTART_POLICY=$(docker inspect "$CONFLICTING_CONTAINER" --format '{{.HostConfig.RestartPolicy.Name}}')
ORIGINAL_RESTART_RETRIES=$(docker inspect "$CONFLICTING_CONTAINER" --format '{{.HostConfig.RestartPolicy.MaximumRetryCount}}')
case "$ORIGINAL_RESTART_POLICY" in
  no|always|unless-stopped) ORIGINAL_RESTART_SPEC="$ORIGINAL_RESTART_POLICY" ;;
  on-failure)
    if ((ORIGINAL_RESTART_RETRIES > 0)); then
      ORIGINAL_RESTART_SPEC="on-failure:$ORIGINAL_RESTART_RETRIES"
    else
      ORIGINAL_RESTART_SPEC="on-failure"
    fi ;;
  *) echo "Unexpected restart policy: $ORIGINAL_RESTART_POLICY" >&2; exit 1 ;;
esac
docker inspect "$CONFLICTING_CONTAINER" \
  --format 'name={{.Name}} image={{.Config.Image}} restart={{.HostConfig.RestartPolicy.Name}} ports={{json .HostConfig.PortBindings}}' \
  > "$B/conflicting-container-safe-summary.txt"
printf '%s\n%s\n' "$CONFLICTING_CONTAINER" "$ORIGINAL_RESTART_SPEC" > "$B/conflicting-container-rollback.txt"
```

Only after explicit user approval:

```bash
docker update --restart=no "$CONFLICTING_CONTAINER" && docker stop "$CONFLICTING_CONTAINER"
```

Rollback:

```bash
{
  IFS= read -r CONFLICTING_CONTAINER
  IFS= read -r ORIGINAL_RESTART_SPEC
} < "$B/conflicting-container-rollback.txt"
docker update --restart="$ORIGINAL_RESTART_SPEC" "$CONFLICTING_CONTAINER" && docker start "$CONFLICTING_CONTAINER"
```

## 5. Install and configure Caddy

```bash
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y caddy
sudo mkdir -p /etc/caddy/snippets /etc/caddy/sites-available /etc/caddy/sites-enabled
```

`/etc/caddy/Caddyfile`:

```caddyfile
{
	# Caddy is the only public HTTP(S) entrypoint on this VPS.
}

import /etc/caddy/snippets/*.caddy
import /etc/caddy/sites-enabled/*.caddy
```

`/etc/caddy/snippets/common.caddy`:

```caddyfile
(secure_headers) {
	header {
		-Server
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		X-Frame-Options "SAMEORIGIN"
	}
}

(common_proxy) {
	encode zstd gzip
	import secure_headers
}
```

`/etc/caddy/sites-available/app.example.com.caddy`:

```caddyfile
app.example.com {
	import common_proxy
	respond /caddy-healthz "ok\n" 200
	reverse_proxy 127.0.0.1:3000
}
```

Enable and reload:

```bash
sudo ln -sfn /etc/caddy/sites-available/app.example.com.caddy /etc/caddy/sites-enabled/app.example.com.caddy
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
systemctl is-active caddy
ss -tulpen | egrep ':(80|443)\b' || true
```

## 6. Docker Compose hardening patterns

Public app behind Caddy:

```yaml
ports:
  - "127.0.0.1:${APP_PORT:-3000}:3000"
```

Local-only dependencies:

```yaml
ports:
  - "127.0.0.1:${DB_PORT:-5432}:5432"
  - "127.0.0.1:${REDIS_PORT:-6379}:6379"
```

Better when Caddy runs in Docker on the same network: avoid host `ports:` for app services and proxy by service name.

## 7. Verification

Before DNS is correct:

```bash
curl -sS -i --max-time 5 -H 'Host: app.example.com' http://127.0.0.1/caddy-healthz | head -20
```

After DNS points to the VPS:

```bash
curl -I http://app.example.com
curl -Iv https://app.example.com
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates
sudo journalctl -u caddy -n 100 --no-pager
```

Expected:

- HTTP returns a redirect to HTTPS.
- HTTPS certificate is trusted and has the requested hostname.
- App responds through Caddy.
- Direct app/dependency ports are not public.

## 8. Rollback skeleton

```bash
set -Eeuo pipefail
sudo systemctl disable --now caddy
# restore configs from $B as needed
# restart prior service if it owned :443
ROLLBACK_METADATA="$B/conflicting-container-rollback.txt"
if [[ -f "$ROLLBACK_METADATA" ]]; then
  {
    IFS= read -r CONFLICTING_CONTAINER
    IFS= read -r ORIGINAL_RESTART_SPEC
  } < "$ROLLBACK_METADATA"
  [[ -n "$CONFLICTING_CONTAINER" && -n "$ORIGINAL_RESTART_SPEC" ]] || {
    echo "invalid conflicting-container rollback metadata" >&2
    exit 1
  }
  docker update --restart="$ORIGINAL_RESTART_SPEC" "$CONFLICTING_CONTAINER" &&
    docker start "$CONFLICTING_CONTAINER"
fi
```
