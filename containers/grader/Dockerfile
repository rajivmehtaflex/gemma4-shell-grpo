# Grading image for the restricted runner (Phase 1).
# Pinned base: debian:bookworm-slim (digest recorded in
# reports/phase1-grader.md after the first build on the Codespace).
# The candidate executes as an unprivileged numeric uid with LANG=C,
# LC_ALL=C, TZ=UTC and this exact toolset; no network, no extra packages.
FROM debian:bookworm-slim

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
