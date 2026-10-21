# Grading image for the restricted runner (Phase 1).
# Base pinned by digest (amd64), recorded from the first Codespace build
# 2026-10-21 and verified in reports/phase1-grader.md.
# The candidate executes as an unprivileged numeric uid with LANG=C,
# LC_ALL=C, TZ=UTC and this exact toolset; no network, no extra packages.
FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash \
      coreutils \
      findutils \
      grep \
      sed \
      gawk \
      diffutils \
      python3 \
 && rm -rf /var/lib/apt/lists/*

ENV LANG=C LC_ALL=C TZ=UTC

# Freeze the tool identity inside the image so every GradeResult can be
# traced to the utilities that actually produced it.
RUN mkdir -p /usr/share/shell-grpo \
 && dpkg-query -W -f='${Package}\t${Version}\n' \
      > /usr/share/shell-grpo/tool-manifest.txt \
 && { bash --version | head -1; \
      env LC_ALL=C sort --version | head -1; \
      env LC_ALL=C find --version | head -1; \
      python3 --version; } \
      > /usr/share/shell-grpo/versions.txt
