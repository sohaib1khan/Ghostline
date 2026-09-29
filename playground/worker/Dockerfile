# Ephemeral learner workspace. No network. Read-only root + tmpfs /workspace.
FROM alpine:3.21.3

RUN apk add --no-cache \
      python3 \
      py3-pip \
      nodejs \
      npm \
      bash \
      coreutils \
      findutils \
    && adduser -D -u 1000 -h /home/learner learner

WORKDIR /workspace
USER learner

# Kept alive by the manager; file ops and runs use docker exec.
CMD ["sleep", "infinity"]
