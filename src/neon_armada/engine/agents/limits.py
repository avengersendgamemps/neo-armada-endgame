"""Operating-system memory limits for agent processes.

Agents are trusted programs; the limit protects the engine from faulty
agents, it is not a sandbox (see ``contracts/agent-protocol.md`` §5).

* Windows: a Job Object with a per-process committed-memory limit. The agent
  is created suspended, placed in the job and only then resumed, so helper
  processes it spawns (for example the real interpreter behind a virtualenv
  ``python.exe`` launcher) inherit the limit. The job is also marked
  kill-on-close, so agent processes cannot outlive the engine. Agents started
  with the engine's own interpreter bypass the virtualenv launcher, see
  :func:`direct_interpreter`.
* Linux and other POSIX systems with a working ``RLIMIT_AS``: an address-space
  limit installed in the child before ``exec``.
* Elsewhere (notably macOS, where ``RLIMIT_AS`` is not enforced): no limit is
  applied and :func:`apply_after_start` reports ``False``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

_MEGABYTE = 1024 * 1024


def preexec_function(memory_limit_mb: int) -> Callable[[], None] | None:
    """Return a ``preexec_fn`` that limits the address space (POSIX only)."""
    if sys.platform == "win32" or sys.platform == "darwin":
        return None
    import resource

    limit = memory_limit_mb * _MEGABYTE

    def set_limit() -> None:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ValueError, OSError):
            pass  # best effort: the agent then runs without a memory limit

    return set_limit


def direct_interpreter(
    command: Sequence[str],
) -> tuple[list[str], dict[str, str] | None]:
    """Bypass the Windows virtualenv launcher for agents run by this Python.

    In a Windows virtual environment ``sys.executable`` is a small launcher
    that starts the real interpreter as a second process. With some Python
    distributions that second process does not inherit the job limits, and
    killing the launcher would leave it running. Starting the base interpreter
    with ``__PYVENV_LAUNCHER__`` set is exactly what the launcher itself does,
    so the agent still sees the virtual environment but is a single process.

    Returns the command to run and the environment (``None`` = inherit).
    """
    base = getattr(sys, "_base_executable", sys.executable)
    if (
        sys.platform != "win32"
        or not command
        or command[0] != sys.executable
        or not base
        or base == sys.executable
    ):
        return list(command), None
    environment = dict(os.environ, __PYVENV_LAUNCHER__=sys.executable)
    return [base, *command[1:]], environment


def creation_flags() -> int:
    """Return the ``creationflags`` for ``Popen``: suspended start on Windows."""
    return 0x00000004 if sys.platform == "win32" else 0  # CREATE_SUSPENDED


class JobHandle:
    """Owns the Windows Job Object of one agent (a no-op elsewhere)."""

    def __init__(self, handle: Any = None, applied: bool = False) -> None:
        self._handle = handle
        self.applied = applied

    def terminate(self) -> None:
        """Kill every process in the job (the agent and its children)."""
        if self._handle is not None:
            _kernel32().TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        if self._handle is not None:
            _kernel32().CloseHandle(self._handle)
            self._handle = None


def apply_after_start(process: subprocess.Popen, memory_limit_mb: int) -> JobHandle:
    """Apply the post-start part of the limit; return the owning handle.

    ``JobHandle.applied`` tells whether a memory limit is in force. On Windows
    the process was created suspended and is resumed here; ``OSError`` is
    raised only if it cannot be resumed.
    """
    if sys.platform != "win32":
        return JobHandle(applied=sys.platform != "darwin")
    try:
        job = _assign_job(process, memory_limit_mb)
    except OSError as error:
        logger.warning("could not apply the agent memory limit: %s", error)
        job = JobHandle()
    _resume(process)
    return job


def _resume(process: subprocess.Popen) -> None:
    import ctypes
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    status = ntdll.NtResumeProcess(int(process._handle))  # Popen's process handle
    if status != 0:
        raise OSError(f"could not resume the agent process (status {status:#x})")


def _kernel32() -> Any:
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


def _assign_job(process: subprocess.Popen, memory_limit_mb: int) -> JobHandle:
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in "abcdef"]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job_object_limit_process_memory = 0x00000100
    job_object_limit_kill_on_job_close = 0x00002000
    job_object_extended_limit_information = 9

    kernel32 = _kernel32()
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = (
        job_object_limit_process_memory | job_object_limit_kill_on_job_close
    )
    info.ProcessMemoryLimit = memory_limit_mb * _MEGABYTE
    configured = kernel32.SetInformationJobObject(
        handle,
        job_object_extended_limit_information,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    assigned = configured and kernel32.AssignProcessToJobObject(
        handle,
        int(process._handle),  # the Windows process handle held by Popen
    )
    if not assigned:
        error = ctypes.WinError(ctypes.get_last_error())
        kernel32.CloseHandle(handle)
        raise error
    return JobHandle(handle, applied=True)
