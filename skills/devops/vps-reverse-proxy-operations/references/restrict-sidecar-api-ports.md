# Restrict sidecar/API ports on a VPS without breaking Docker apps

Use when an application or reverse-proxy audit finds a helper API process listening on `0.0.0.0:<port>` but local containers still need to reach it through `host.docker.internal`.

## Pattern

Prefer a dedicated nftables table plus a small systemd oneshot service instead of editing Docker-managed `ip`/`ip6` nft tables. Docker labels many tables as managed by `iptables-nft`; do not modify those directly.

Example: restrict a helper API on `<port>/tcp` so only localhost and one intended application Docker network can reach it.

```bash
# Backup first
umask 077
TS=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="${BACKUP_ROOT:?set BACKUP_ROOT to a private backup directory}/sidecar-firewall-$TS"
install -d -m 0700 "$BACKUP_DIR"
sudo nft list ruleset > "$BACKUP_DIR/nft-ruleset.before.nft"
[ -f /etc/nftables.conf ] && sudo cat /etc/nftables.conf > "$BACKUP_DIR/nftables.conf.before"

# Discover the app Docker subnet
# Select the host-approved form: DOCKER=(docker) or DOCKER=(sudo -n docker).
DOCKER=(docker)
"${DOCKER[@]}" network inspect <compose_network> --format '{{range .IPAM.Config}}{{.Subnet}} {{.Gateway}}{{end}}'
```

Create `/usr/local/sbin/restrict-<service>-api.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
TABLE="${TABLE_NAME:?set TABLE_NAME to a unique table owned by this service}"
SUBNET="${SUBNET:?set SUBNET to the discovered application Docker subnet}"
PORT="${PORT:?set PORT to the helper API port}"
[[ "$TABLE" =~ ^[A-Za-z_][A-Za-z0-9_]{0,31}$ ]] || { echo "invalid TABLE_NAME" >&2; exit 2; }
[[ "$SUBNET" =~ ^[0-9.]+/[0-9]{1,2}$ ]] || { echo "SUBNET must be an IPv4 CIDR" >&2; exit 2; }
[[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT >= 1 && PORT <= 65535)) || { echo "invalid PORT" >&2; exit 2; }

if nft list table inet "$TABLE" >/dev/null 2>&1; then
  table_reset="delete table inet $TABLE"
else
  table_reset=""
fi

umask 077
rules_file=$(mktemp)
trap 'rm -f "$rules_file"' EXIT
cat > "$rules_file" <<EOF
$table_reset
add table inet $TABLE
add chain inet $TABLE input { type filter hook input priority -100; policy accept; }
add rule inet $TABLE input tcp dport $PORT iifname "lo" accept
add rule inet $TABLE input tcp dport $PORT ip saddr $SUBNET accept
add rule inet $TABLE input tcp dport $PORT drop
EOF
nft -f "$rules_file"
```

Choose a table name unique to this service and verify it is unused before the first run. On later runs, the atomic ruleset transaction deletes and recreates only that explicitly dedicated table so changed inputs are applied idempotently. Never reuse a shared or distribution-managed table name.

Create `/etc/default/restrict-<service>-api` with mode `0600`:

```bash
TABLE_NAME=<unique_nft_table_name>
SUBNET=<discovered_docker_subnet>
PORT=<helper_api_port>
```

Make it persistent with a oneshot service:

```ini
[Unit]
Description=Restrict public access to sidecar API port
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/default/restrict-<service>-api
ExecStart=/usr/local/sbin/restrict-<service>-api.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable/apply:

```bash
sudo chmod 0755 /usr/local/sbin/restrict-<service>-api.sh
sudo chmod 0600 /etc/default/restrict-<service>-api
sudo systemctl daemon-reload
sudo systemctl enable --now restrict-<service>-api.service
sudo nft list table inet <unique_nft_table_name>
```

## Verification

- Localhost still reaches the API: `curl -i http://127.0.0.1:<port>/...` (401/403 can be OK; it proves network reachability and auth is active).
- The intended app container reaches the API: `docker exec <app> <container-http-probe-command> http://host.docker.internal:<port>/...`.
- An unrelated Docker network is blocked: `docker run --rm --add-host=host.docker.internal:host-gateway alpine sh -c 'wget -T 3 -qO- http://host.docker.internal:<port>/... || echo blocked_or_failed'`.
- Primary public HTTPS app still works through Caddy.

## Pitfalls

- If the app container uses `host.docker.internal`, binding the API to `127.0.0.1` on the host may break it. Firewall restriction is often safer than changing the bind address.
- Quote nft comments carefully or omit them; unquoted multi-word comments can make a oneshot service fail.
- A host-local curl to the public IP may still succeed because it is locally routed; use Docker negative tests or an external probe to prove public blocking.
- Do not enable a global `/etc/nftables.conf` with `flush ruleset` casually on Docker hosts; it can wipe Docker’s runtime tables. A dedicated systemd-applied table is lower risk.
