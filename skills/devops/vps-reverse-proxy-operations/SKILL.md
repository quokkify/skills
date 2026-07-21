---
name: vps-reverse-proxy-operations
description: "Configure, audit, and troubleshoot public HTTPS reverse proxies on a VPS, including DNS, ports, Docker exposure, backups, TLS, and service coexistence."
---

# VPS Reverse Proxy Operations

## When to use

Use this skill whenever a task involves publishing one or more services on a VPS through a public HTTP(S) entrypoint, especially with Caddy, Nginx, Docker Compose, automatic TLS, DNS records, or port/firewall hardening.

This includes:

- Configure Caddy/Nginx as the single public entrypoint for domains/subdomains.
- Replace temporary tunnels such as trycloudflare with normal VPS HTTPS.
- Audit which services listen publicly before opening HTTPS.
- Move app containers behind `localhost` or a Docker-internal network.
- Resolve conflicts where another approved service already owns `:443`.
- Produce verification and rollback commands after changing system services.

## Core workflow

1. **Read-only infrastructure audit first**
   - Capture host/date/IPs, public IPv4/IPv6, listening sockets, Docker containers, Docker networks, systemd web/proxy services, firewall state, and existing `/etc/caddy`, `/etc/nginx`, `/etc/apache2`, `/etc/letsencrypt`.
   - Inspect relevant Compose files for `ports:` mappings; flag `0.0.0.0` exposure of databases, Redis, app backends, admin APIs, and agent/gateway services.
   - Identify existing owners of `80/tcp`, `443/tcp`, and optionally `443/udp` before planning Caddy.
   - Resolve the intended domain/subdomains and verify DNS A/AAAA points to the VPS before expecting ACME success.

2. **Choose the simplest production-safe topology**
   - Public internet should reach only the reverse proxy on `80/tcp` and `443/tcp` (and optionally `443/udp` for HTTP/3 if acceptable).
   - Applications should listen only on `127.0.0.1:<port>` from the host perspective or solely on an internal Docker network.
   - Databases, Redis, queues, and internal APIs should not be published publicly; if host access is needed, bind to `127.0.0.1`.
   - Each future app should be addable with a separate site block/file for its subdomain, without changing the global architecture.

3. **Backup before writes**
   - Create a timestamped backup directory under the user's backup location.
   - Save an audit transcript plus existing web/proxy configs and relevant Compose files before editing.
   - For Docker services that must be stopped or moved, record `docker inspect` output and restart policy.

4. **Apply minimal changes**
   - Install the proxy package using the distro package manager unless the user needs a newer feature than the distro package provides.
   - For Caddy, prefer a small global `Caddyfile` that imports `snippets/*.caddy` and `sites-enabled/*.caddy`.
   - Put reusable headers/encoding in snippets; put each domain in its own `sites-available/<fqdn>.caddy` file and symlink into `sites-enabled`.
   - Let Caddy perform automatic HTTPS and HTTP→HTTPS redirects; avoid custom ACME or TLS tweaks unless required.
   - If another critical service owns `:443`, get explicit user direction before stopping/moving it. If approved, disable its restart policy before stopping so it does not race the proxy on reboot.

5. **Validate and reload safely**
   - Run config validation before reload (`caddy validate --config /etc/caddy/Caddyfile` or equivalent).
   - Reload rather than restart where supported.
   - Check listeners after reload and confirm only intended services are public.

6. **Verify end-to-end**
   - Treat source merge, CI success, release automation, deployment, and public runtime as separate gates. Before visual/runtime closeout, confirm that a deploy workflow or explicit rollout actually ran; inspect running container/image provenance and public behavior instead of assuming the current checkout SHA is deployed.
   - If the public app still shows the old behavior after merge, record deployment lag or missing deployment automation and leave runtime acceptance open. Do not rebuild/restart a live-data app merely to obtain screenshots until its backup gate and resource check pass.
   - Before DNS is correct, verify locally with Host headers and document that public ACME validation cannot complete yet.
   - After DNS points to the VPS, verify:
     - `http://domain` redirects to `https://domain`.
     - `https://domain` presents a trusted certificate for the right SAN.
     - The proxied application responds through the reverse proxy.
     - Direct app/database ports are not reachable from non-local interfaces.
   - Include exact verification and rollback commands in the final response.

## Caddy layout pattern

Use this layout for maintainability:

```text
/etc/caddy/Caddyfile
/etc/caddy/snippets/common.caddy
/etc/caddy/sites-available/<subdomain>.caddy
/etc/caddy/sites-enabled/<subdomain>.caddy -> ../sites-available/<subdomain>.caddy
```

Global `Caddyfile`:

```caddyfile
{
	# Caddy is the only public HTTP(S) entrypoint on this VPS.
}

import /etc/caddy/snippets/*.caddy
import /etc/caddy/sites-enabled/*.caddy
```

Site block:

```caddyfile
app.example.com {
	import common_proxy
	reverse_proxy 127.0.0.1:3000
}
```

## Docker Compose exposure rules

Prefer one of these:

```yaml
ports:
  - "127.0.0.1:${APP_PORT:-3000}:3000"
```

or no host port at all when Caddy is attached to the same Docker network and proxies to the container name.

For stateful dependencies, do not publish publicly:

```yaml
ports:
  - "127.0.0.1:${DB_PORT:-5432}:5432"
  - "127.0.0.1:${REDIS_PORT:-6379}:6379"
```

## Pitfalls

- **DNS mismatch blocks real HTTPS validation.** If A/AAAA records point elsewhere, Caddy config can validate and local Host-header checks can pass, but ACME and public HTTPS verification will not be valid for this VPS.
- **Resolver caches can hide an authoritative DNS change.** Compare `dig +trace <fqdn> A`, direct queries to authoritative nameservers, and multiple independent recursive resolvers. If authoritative DNS returns `<vps-ip>` while recursive resolvers return an old value, treat it as delegation propagation or caching. Use `curl --resolve <fqdn>:443:<vps-ip>` and `openssl s_client -connect <vps-ip>:443 -servername <fqdn>` for end-to-end verification against the intended VPS.
- **AAAA matters.** If IPv6 DNS points somewhere else, clients and ACME may hit the wrong host. Either point AAAA to the VPS IPv6 or remove it until configured.
- **Docker publishes through iptables.** A port may be public even if UFW is inactive or appears restrictive. Inspect `ss`, `docker ps`, and iptables/docker rules.
- **Another transport may own `443`.** Caddy cannot share the listener as a normal HTTP reverse proxy without an explicit multiplex/SNI architecture. Prefer freeing `443` for Caddy or using another VPS/IP unless the user explicitly chooses and validates multiplexing.
- **Caddy may bind UDP 443 for HTTP/3.** If the requirement is strictly only TCP 80/443, or another approved transport must avoid UDP/443 conflicts, explicitly disable HTTP/3 in the Caddy global options with `servers { protocols h1 h2 }` after validating the installed Caddy version supports it.
- **Do not silently edit app env/secrets.** Use an approved access-controlled backup process before changing public origins or callbacks. If approval for an env write times out or is denied, stop and report what remains rather than retrying via another path.
- **Agent/API sidecars may remain public.** Check every helper listener bound to `0.0.0.0:<port>`. Do not close it blindly because it may power gateway or application integrations; report it as a hardening finding and recommend restricting it to localhost, an intended container subnet, or trusted source addresses when public access is unnecessary. If containers still need `host.docker.internal:<port>`, prefer a narrow firewall rule over changing the bind address; see `references/restrict-sidecar-api-ports.md`.

## Verification checklist

- [ ] Backup path recorded.
- [ ] DNS A/AAAA checked against VPS IPs.
- [ ] `80/tcp` and `443/tcp` owned by reverse proxy.
- [ ] Existing services and containers not unintentionally restarted or exposed.
- [ ] App listens on localhost or internal Docker network, not public `0.0.0.0`.
- [ ] Databases/Redis/queues not publicly published.
- [ ] Proxy config validates and service reload succeeds.
- [ ] HTTP redirects to HTTPS.
- [ ] Certificate subject/SAN/issuer/dates verified.
- [ ] Reverse-proxied app endpoint responds.
- [ ] Running image/container provenance and public behavior confirm the intended revision is actually deployed.
- [ ] Rollback commands provided.

## References

- `references/caddy-vps-reverse-proxy-runbook.md` — concise command runbook for safe Caddy deployment on a VPS, including listener conflicts and DNS blockers.
- `references/restrict-sidecar-api-ports.md` — nftables + systemd pattern for restricting public helper/API ports while preserving localhost and Docker-container access.
