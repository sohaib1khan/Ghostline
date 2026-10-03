# Ephemeral learner workspace. No network. Read-only root + tmpfs /workspace.
# DECISION: Debian/glibc base so manager-side `pip download` wheels install cleanly
# (Alpine/musl rejected manylinux wheels like markupsafe).
FROM python:3.12.14-slim-bookworm

# JDK + Mono for one-shot Java / C# compiles inside the offline worker.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         nodejs \
         npm \
         bash \
         ca-certificates \
         default-jdk-headless \
         mono-mcs \
         mono-runtime \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /bin/bash learner

WORKDIR /workspace
USER learner

# Kept alive by the manager; file ops and runs use docker exec.
CMD ["sleep", "infinity"]
