# Docker base images

## Where to look in the update

- The image's release notes, tag documentation, or image repository README: variant changes (distribution base, slim or minimal flavors), end-of-life notices, renamed or retired tags.
- The upstream `Dockerfile` diff between the two tags: changed default `USER`, `WORKDIR`, `ENV`, `ENTRYPOINT`, `HEALTHCHECK`, packages added to or removed from the base.

## Consumer files to grep

- `Dockerfile`, `*.Dockerfile`, `Dockerfile.*`, `Containerfile`, `docker-compose*.yml`, `compose*.yaml`, and image references in workflows or Helm/Kubernetes manifests.
- Search for the image name, then for instructions in the same stage that duplicate base behavior: `RUN apt-get install`, `apk add`, `RUN useradd`/`adduser`, `ENV`, `HEALTHCHECK`, `USER`.

## Local warning command

- `hadolint <Dockerfile>`.
- `docker build` output warnings (for example legacy `ENV key value` syntax or `FROM` casing notices from BuildKit), when a local build is part of the consumer's checks.

## Typical adoptable patterns

- A package the consumer installs that the new base now ships, when the image source states it: drop the install line.
- A non-root user created by hand when the new base documents a built-in user: switch to it.
- Environment variables duplicated from the new base defaults, when the source documents the default.
- A tag variant announced as end-of-life with a documented successor variant: move to it.
- Comments or docs naming the old image version.

## Typical false positives

- A digest-only update (`updateType` `digest`): nothing to adopt unless allowlisted and the notes say otherwise.
- A suffix change that the helper classifies `unknown`: review only through the explicit-PR override, and confirm the variant change is intended.
- Packages present in the new base by accident (transitive) rather than by documented contract.
- Changing the distribution family (for example a musl-based variant to a glibc-based one) is a design decision, not an adoption.
