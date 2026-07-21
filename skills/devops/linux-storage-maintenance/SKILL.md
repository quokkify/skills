---
name: linux-storage-maintenance
description: "Use when diagnosing Linux disk pressure, reclaiming space safely, or building conservative recurring cleanup for Docker, logs, caches, and temporary files."
---

# Linux Storage Maintenance

## Overview

Diagnose disk pressure read-only first, classify cleanup candidates by risk, reclaim space in small verified stages, and automate only policies that are conservative and measurable. Prefer an incremental loop—observe, clean one class, verify, then expand—over a single broad prune command.

## When to Use

- A Linux host is low on disk space or unexpectedly full.
- The user asks what can be deleted safely.
- Docker/containerd, logs, caches, temporary directories, repositories, or application data are large.
- The user wants periodic cleanup without risking databases, uploads, backups, or active services.

## Portability and prerequisites

The bundled retention helper targets Bash 4+, GNU `flock`/coreutils, a rootful Docker CLI/daemon, and systemd. Adapt it for rootless Docker, Podman, Docker Desktop, non-systemd hosts, or distributions whose Docker unit has a different name. The service path, state path, owner/group, retention period, and timer schedule are templates—not universal defaults.

## Core Workflow

### 1. Establish the baseline

Start read-only. Capture:

- filesystem type, total/used/available space, and mount boundaries;
- inode usage separately from byte usage;
- top-level same-filesystem directory sizes;
- large files and deleted-but-open files;
- Docker image/container/volume/build-cache accounting when Docker is present;
- logs, package caches, user caches, temporary data, repositories, backups, and swap.

Use `du -x` so scans do not cross mounted filesystems. Distinguish allocated disk space from apparent file size when sparse files or container layers are involved. Treat swap files as operating-system capacity, not disposable cache.

### 2. Classify before deleting

Use three buckets:

1. **Low-risk/recreatable** — package caches, language package caches, stale browser binaries, bounded old journals, clearly stale temporary artifacts, unused container images.
2. **Conditional** — stopped containers, Docker volumes, old worktrees, large Git object stores, old state snapshots, old kernels, application logs with retention requirements.
3. **Protect by default** — active container layers, databases, uploads, bind mounts, backups, secrets, current state databases, swap, and anything whose owner or recovery path is unclear.

Never infer that a Docker volume is disposable merely because Docker reports it as unused. Map it to Compose projects, database names, mounts, and backup policy first.

### 3. Clean in stages

Apply one category at a time and re-check `df`, service health, and relevant application health after each stage. Avoid concurrent heavy deletes/prunes on small VPS hosts. Report actual before/after values rather than estimated savings.

A typical first pass may include:

- unused Docker images only, without volumes;
- package-manager caches;
- npm/npx or similar recreatable caches;
- stale temporary directories selected by path and age;
- journal retention by size or time.

Do not combine `docker system prune --volumes` with a general cleanup. Volume cleanup requires a separate evidence and approval gate.

### 4. Verify service health

After mutation, verify:

- filesystem free space and usage percentage;
- active containers and their health states;
- core services such as Docker/containerd/reverse proxy;
- application health endpoints where available;
- cleanup command exit status and logs.

A cleanup is not complete merely because the delete command returned output.

## Conservative Docker Image Retention

Docker's `image prune --filter until=168h` filters primarily by image creation time; it does **not** prove an image has been continuously unused for seven days. For a policy stated as “delete images unused for a week,” use stateful observation:

1. Enumerate all image IDs.
2. Enumerate image IDs referenced by **all containers**, including stopped containers.
3. Record the first time each unreferenced image is observed.
4. Remove its record whenever any container references it again.
5. Delete only after it remains unreferenced for the full retention period.
6. Avoid forced removal; if deletion fails, keep the record and retry later.
7. Use a lock and atomic state-file replacement so overlapping runs or interruption cannot corrupt retention state.

Run this daily with a seven-day retention window. A daily timer gives bounded detection delay without frequent churn. Log a compact summary: protected, newly unused, tracked, deleted, and failed counts.

Reusable files:

- `templates/docker-image-retention-cleanup.sh` — stateful Docker image retention script.
- `templates/docker-image-retention-cleanup.service` — hardened systemd oneshot service.
- `templates/docker-image-retention-cleanup.timer` — daily persistent timer.
- `references/staged-linux-disk-cleanup.md` — diagnostic and rollout checklist with pitfalls.

## Automation Rollout

Start with one narrow cleanup class. For the first iteration, Docker image retention is a good candidate because image data is recreatable and Docker itself prevents ordinary removal of images referenced by containers.

Before enabling a timer:

1. Run syntax/static validation.
2. Run `--dry-run` against the live Docker daemon.
3. Install the script and units with root ownership and explicit modes; create the state directory explicitly, for example `install -d -o root -g root -m 0750 /var/lib/docker-image-retention-cleanup`.
4. Validate units after the executable exists at its final path.
5. Enable the timer.
6. Run the service once manually to seed state.
7. Inspect service result, journal output, timer trigger, state-file ownership, disk usage, and container health.

Expand only after observing logs and real disk growth. Good second-stage candidates are bounded journal retention and age-scoped temporary files. Keep each cleanup category separately configurable and avoid silently broadening deletion scope.

## Common Pitfalls

- Treating image creation age as last-used age.
- Looking only at running containers and deleting images needed by stopped containers.
- Using `docker image rm -f` to overcome tagging conflicts without reassessing risk.
- Running a blanket Docker volume prune on a stateful VPS.
- Deleting a large state snapshot immediately after an update before recovery confidence exists.
- Removing swap because it appears as a large root-level file.
- Trusting `du` alone when deleted-but-open files retain disk blocks.
- Installing systemd units and validating them before the referenced executable exists, producing a misleading validation failure.
- Making a cleanup timer chatty; routine successful runs should stay in journald unless the user explicitly wants notifications.
- Assuming the bundled rootful-Docker service dependency, filesystem paths, or UTC schedule fit every host without adaptation.

## Verification Checklist

- [ ] Baseline `df` and inode usage captured.
- [ ] Same-filesystem size breakdown completed.
- [ ] Candidate data classified by recoverability and ownership.
- [ ] Databases, uploads, volumes, backups, swap, and current state are protected.
- [ ] Cleanup executed in small stages.
- [ ] Actual free-space gain measured.
- [ ] Containers and core services verified healthy.
- [ ] Automation has dry-run support, locking, atomic state, and compact logs.
- [ ] Timer is enabled, scheduled, and successfully exercised once.
- [ ] Next iteration is based on observed logs/usage rather than speculative broad pruning.
