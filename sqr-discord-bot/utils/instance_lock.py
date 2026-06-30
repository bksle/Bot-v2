"""Ensure only one bot.py process runs at a time."""

from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

_LOCK_PATH = Path(__file__).resolve().parent.parent / "data" / "bot.instance.lock"
_MUTEX_NAME = r"Local\SQRDiscordBotSingleInstance"
_lock_fd: int | None = None
_mutex_handle: int | None = None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def _read_lock_pid() -> int | None:
    try:
        raw = _LOCK_PATH.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (OSError, ValueError):
        return None


def _write_lock_pid() -> None:
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LOCK_PATH.write_text(str(os.getpid()), encoding="ascii")


def release_bot_instance_lock() -> None:
    global _lock_fd, _mutex_handle

    if sys.platform == "win32" and _mutex_handle:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.ReleaseMutex(_mutex_handle)
        kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None

    fd = _lock_fd
    _lock_fd = None
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass

    try:
        if _LOCK_PATH.exists():
            _LOCK_PATH.unlink()
    except OSError:
        pass


def _acquire_windows_mutex() -> None:
    global _mutex_handle

    import ctypes

    kernel32 = ctypes.windll.kernel32
    ERROR_ALREADY_EXISTS = 183
    handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if not handle:
        raise SystemExit("تعذّر بدء البوت — فشل قفل النسخة الواحدة.")

    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        raise SystemExit(
            "البوت شغّال مسبقاً — أغلق كل نوافذ python bot.py أو start_bot.bat "
            "ثم شغّل نسخة واحدة فقط."
        )

    _mutex_handle = handle
    _write_lock_pid()
    atexit.register(release_bot_instance_lock)


def _acquire_posix_lock() -> None:
    global _lock_fd

    import fcntl

    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _LOCK_PATH.exists():
        existing_pid = _read_lock_pid()
        if existing_pid is not None and _pid_alive(existing_pid):
            raise SystemExit(
                "البوت شغّال مسبقاً — أغلق النسخ الإضافية ثم حاول مرة أخرى."
            )
        try:
            _LOCK_PATH.unlink()
        except OSError:
            raise SystemExit(
                "تعذّر بدء البوت — ملف القفل مستخدم. أغلق أي نسخة أخرى ثم حاول."
            ) from None

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(_LOCK_PATH), flags)
    except FileExistsError:
        raise SystemExit(
            "البوت شغّال مسبقاً — أغلق النسخ الإضافية ثم حاول مرة أخرى."
        ) from None

    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
    except OSError:
        os.close(fd)
        try:
            _LOCK_PATH.unlink()
        except OSError:
            pass
        raise

    _lock_fd = fd
    atexit.register(release_bot_instance_lock)


def acquire_bot_instance_lock() -> None:
    if sys.platform == "win32":
        _acquire_windows_mutex()
        return
    _acquire_posix_lock()
