"""Namespace executor: the restricted engine for hosts without Docker.

Re-proved on the Colab L4 host 2026-10-22 (see reports/runtime-capabilities.md):
unprivileged user namespaces work but the kernel forbids fork inside a
non-init PID namespace, and util-linux's --map-users drops the caller from
its own map. This helper therefore creates user+net namespaces directly and
writes the uid/gid maps from the privileged parent:

    inner 0   -> outer 0        (namespace root, used only for the drop)
    inner N   -> outer 100000+N-1 for N in 1..65535

then the child setuid/setgids to inner 65534 (outer 165533, zero
capabilities after the uid change) and execs the candidate. The parent
reaps via the status word. Timeouts and process-group kills are the
runner's responsibility.
"""

from __future__ import annotations

import os
import signal

NS_USER = 0x10000000
NS_NET = 0x40000000

INNER_UNPRIVILEGED = 65534  # outer 165533 under the 100000 subuid allocation
SUBUID_BASE = 100000

_READY = b"ready"


def _write_map(pid: int, name: str, content: str) -> None:
    with open(f"/proc/{pid}/{name}", "w") as fh:
        fh.write(content)


def ns_exec(argv: list[str], env: dict[str, str], cwd: str) -> int:
    """Run argv in a fresh user+net namespace as an unprivileged uid.

    Returns the child's exit status (negative signal on kill). Must be
    invoked as root on a host that allows unprivileged user namespaces.
    """
    r1, w1 = os.pipe()  # child -> parent: namespace created
    r2, w2 = os.pipe()  # parent -> child: maps written, proceed

    pid = os.fork()
    if pid == 0:
        os.close(r1)
        os.close(w2)
        import ctypes

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        if libc.unshare(NS_USER | NS_NET) != 0:
            os._exit(3)
        os.write(w1, _READY)
        os.close(w1)
        os.read(r2, 1)  # EOF once the parent has written the maps
        os.setgroups([])
        os.setgid(INNER_UNPRIVILEGED)
        os.setuid(INNER_UNPRIVILEGED)
        os.chdir(cwd)
        os.execve(argv[0], argv, env)
        os._exit(127)

    os.close(w1)
    os.close(r2)
    try:
        if os.read(r1, len(_READY)) != _READY:
            os.kill(pid, signal.SIGKILL)
            raise RuntimeError("child failed to create namespaces (userns disabled?)")
        # Parent is real root (CAP_SETGID over the child's namespace), so the
        # gid_map needs no setgroups=deny — and the child must keep the right
        # to clear its inherited supplementary groups.
        _write_map(pid, "gid_map", f"0 0 1\n1 {SUBUID_BASE} 65535\n")
        _write_map(pid, "uid_map", f"0 0 1\n1 {SUBUID_BASE} 65535\n")
    finally:
        os.close(w2)
        os.close(r1)

    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)
