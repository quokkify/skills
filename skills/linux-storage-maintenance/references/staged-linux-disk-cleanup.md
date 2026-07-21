# Staged Linux Disk Cleanup

## Read-only inventory

Capture these before deletion:

```bash
df -hT -x tmpfs -x devtmpfs -x squashfs
df -ih -x tmpfs -x devtmpfs -x squashfs
sudo du -x -h --max-depth=1 / | sort -h
du -x -h --max-depth=1 "$HOME" | sort -h
sudo du -x -h --max-depth=2 /var/lib | sort -h
sudo journalctl --disk-usage
docker system df
sudo lsof +L1
```

For large-file searches, remain on one filesystem (`-xdev`). Reduce output to the largest candidates and do not expose secret-bearing config files.

## Candidate interpretation

- Docker **images** are usually recreatable, but preserve images referenced by running or stopped containers.
- Docker **volumes** may contain databases, uploads, caches, or abandoned test data. “Unused” is not equivalent to “safe to delete.”
- `/tmp` needs path/age/owner inspection. Delete explicit stale candidates instead of an indiscriminate wildcard when active tests or browsers may use it.
- Package, npm, npx, Playwright, uv, and similar caches are usually recreatable; note that later commands may need network access and time to restore them.
- Journald can be bounded with `journalctl --vacuum-size=...` or `--vacuum-time=...`; preserve enough history for incident diagnosis.
- Large `.git` directories may be legitimate history, stale worktrees, or inefficient packs. Inspect repository/worktree state before garbage collection or deletion.
- State snapshots are recovery assets. Keep recent pre-update snapshots until the updated service is proven stable.
- Swap files are not cleanup targets unless the host's memory design is deliberately being changed.

## Conservative first pass

Prefer separate, observable operations:

1. prune unused Docker images without volumes;
2. clear recreatable package/language/browser caches;
3. remove specifically identified stale temporary directories;
4. vacuum journals to a bounded size;
5. re-measure disk space;
6. verify containers, services, and health endpoints.

Do not report a theoretical sum as reclaimed space. Compare real before/after filesystem values.

## Stateful Docker retention rationale

`docker image prune -a --filter until=168h` is based on image timestamps, not a durable last-use history. A continuously-unused policy needs a small state database:

- image ID → first observed unused timestamp;
- reset by omission when any container references the image;
- deletion only after the threshold;
- failed deletion retained for retry;
- atomic state replacement and `flock` around each run.

Include stopped containers in the protected set via `docker ps -aq` plus `docker inspect --format '{{.Image}}'`. Do not use force merely to handle an image with multiple tags; log and revisit the policy.

## Installation and verification

Install the executable before running `systemd-analyze verify`, because unit validation checks that `ExecStart` exists and is executable.

```bash
sudo install -o root -g root -m 0755 docker-image-retention-cleanup.sh \
  /usr/local/sbin/docker-image-retention-cleanup
sudo install -o root -g root -m 0644 docker-image-retention-cleanup.service \
  /etc/systemd/system/docker-image-retention-cleanup.service
sudo install -o root -g root -m 0644 docker-image-retention-cleanup.timer \
  /etc/systemd/system/docker-image-retention-cleanup.timer
sudo install -d -o root -g root -m 0750 \
  /var/lib/docker-image-retention-cleanup
sudo systemd-analyze verify \
  /etc/systemd/system/docker-image-retention-cleanup.service \
  /etc/systemd/system/docker-image-retention-cleanup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now docker-image-retention-cleanup.timer
sudo systemctl start docker-image-retention-cleanup.service
```

Verify:

```bash
systemctl status docker-image-retention-cleanup.timer --no-pager
sudo systemctl show docker-image-retention-cleanup.service \
  -p Result -p ExecMainStatus -p ActiveState -p SubState
sudo journalctl -u docker-image-retention-cleanup.service -n 30 --no-pager
df -h /
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

A first non-dry-run execution normally seeds state and deletes nothing. That is expected and proves the retention window begins from observed evidence rather than guessed historical use.

## Iteration policy

Review logs and disk growth before adding another cleanup class. Add one separately configurable category at a time. Good next candidates are bounded journals and explicit age-scoped temporary roots. Keep volumes, databases, uploads, backups, and application state behind separate discovery and approval gates.
