"""Append-only cycle telemetry log on the Pico flash (cycle.log)."""

import os
import time

LOG_PATH = "cycle.log"
MAX_BYTES = 32768


def _timestamp():
    # Pico RTC often boots at 2021-01-01 until NTP — treat that as unset.
    try:
        t = time.localtime()
        if t[0] >= 2024:
            return "%04d-%02d-%02d %02d:%02d:%02d" % (
                t[0],
                t[1],
                t[2],
                t[3],
                t[4],
                t[5],
            )
    except (AttributeError, OSError, OverflowError):
        pass
    return "uptime_ms:%d" % time.ticks_ms()


def read_log():
    try:
        with open(LOG_PATH, "r") as f:
            return f.read()
    except OSError:
        return ""


def _rotate_if_needed():
    try:
        size = os.stat(LOG_PATH)[6]
    except OSError:
        return
    if size <= MAX_BYTES:
        return
    try:
        with open(LOG_PATH, "r") as f:
            data = f.read()
        # Keep the newest half (split on a newline when possible).
        keep = data[len(data) // 2 :]
        nl = keep.find("\n")
        if nl >= 0:
            keep = keep[nl + 1 :]
        with open(LOG_PATH, "w") as f:
            f.write("--- log rotated ---\n")
            f.write(keep)
    except OSError:
        pass


def log_cycle(message):
    """Write one cycle telemetry line: [timestamp] message."""
    line = "[%s] %s\n" % (_timestamp(), message)
    try:
        _rotate_if_needed()
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError as write_exc:
        print("cycle_log write failed:", write_exc)
    print(line, end="")
    return line
