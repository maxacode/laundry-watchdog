"""Washer/dryer completion monitor for Pico W + GY-521 (MPU-6050)."""

from machine import Pin
import time

from config_store import load_config
from cycle_log import log_cycle
from error_log import log_error
from mpu6050 import make_mpu
from wifi_connect import connect_wifi, wifi_ip
from webserver import ConfigServer
from notification import notify_cycle_complete, notify_cycle_started

# States
STATE_IDLE = "IDLE"
STATE_STARTING = "STARTING"
STATE_RUNNING = "RUNNING"
STATE_QUIET = "QUIET"
STATE_COMPLETE = "COMPLETE"


class StatusLed:
    def __init__(self, ok_period_ms=2000, error_period_ms=150):
        self.led = Pin("LED", Pin.OUT)
        self.ok_period_ms = ok_period_ms
        self.error_period_ms = error_period_ms
        self.error = False
        self._last = time.ticks_ms()
        self.led.value(0)

    def set_error(self, is_error):
        self.error = bool(is_error)

    def update(self):
        period = self.error_period_ms if self.error else self.ok_period_ms
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last) >= period:
            self._last = now
            self.led.toggle()


def _stillness_minutes(cfg):
    """Prefer stillness_timeout_min; migrate legacy stillness_timeout_ms."""
    if "stillness_timeout_min" in cfg and cfg.get("stillness_timeout_min") not in (
        None,
        "",
    ):
        return float(cfg.get("stillness_timeout_min"))
    legacy_ms = cfg.get("stillness_timeout_ms")
    if legacy_ms not in (None, ""):
        return float(legacy_ms) / 60000.0
    return 10.0


class LaundryMonitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = STATE_IDLE
        self.quiet_since = None
        self.starting_since = None
        self.last_vibration = 0.0
        self.notified = False
        self.threshold = float(cfg.get("vibration_threshold", 0.12))
        self.stillness_min = _stillness_minutes(cfg)
        self.stillness_ms = int(self.stillness_min * 60000)
        self.start_timer_ms = int(float(cfg.get("start_timer_s", 60)) * 1000)
        self.sample_ms = int(cfg.get("sample_interval_ms", 100))
        self.log_interval_ms = int(float(cfg.get("cycle_log_interval_s", 30)) * 1000)
        self._last_sample = time.ticks_ms()
        self._last_heartbeat = time.ticks_ms()

    def status(self):
        quiet_ms = 0
        starting_ms = 0
        now = time.ticks_ms()
        if self.quiet_since is not None:
            quiet_ms = time.ticks_diff(now, self.quiet_since)
        if self.starting_since is not None:
            starting_ms = time.ticks_diff(now, self.starting_since)
        return {
            "state": self.state,
            "vibration": self.last_vibration,
            "threshold": self.threshold,
            "quiet_ms": quiet_ms,
            "starting_ms": starting_ms,
            "stillness_timeout_min": self.stillness_min,
            "start_timer_s": self.start_timer_ms // 1000,
            "cycle_log_interval_s": self.log_interval_ms // 1000,
            "notified": self.notified,
            "mpu_ok": getattr(self, "mpu_ok", False),
            "last_error": getattr(self, "last_error", ""),
        }

    def _begin_starting(self, now):
        self.state = STATE_STARTING
        self.starting_since = now
        self.quiet_since = None
        self.notified = False

    def _confirm_started(self):
        self.state = STATE_RUNNING
        self.starting_since = None
        self.quiet_since = None
        return "STARTED"

    def _quiet_duration_s(self, now):
        if self.quiet_since is None:
            return 0
        return max(0, time.ticks_diff(now, self.quiet_since) // 1000)

    def update(self, vibration):
        self.last_vibration = vibration
        now = time.ticks_ms()
        moving = vibration >= self.threshold
        event = None
        prev = self.state

        if self.state == STATE_IDLE:
            if moving:
                self._begin_starting(now)

        elif self.state == STATE_STARTING:
            if not moving:
                # Bump/noise — require a fresh steady run.
                self.state = STATE_IDLE
                self.starting_since = None
            elif time.ticks_diff(now, self.starting_since) >= self.start_timer_ms:
                event = self._confirm_started()

        elif self.state == STATE_RUNNING:
            if not moving:
                self.state = STATE_QUIET
                self.quiet_since = now

        elif self.state == STATE_QUIET:
            if moving:
                duration_s = self._quiet_duration_s(now)
                self.state = STATE_RUNNING
                self.quiet_since = None
                log_cycle(
                    "quiet_ended duration_s=%d next=%s vib=%.4f"
                    % (duration_s, self.state, vibration)
                )
            elif time.ticks_diff(now, self.quiet_since) >= self.stillness_ms:
                duration_s = self._quiet_duration_s(now)
                self.state = STATE_COMPLETE
                self.quiet_since = None
                event = "COMPLETE"
                log_cycle(
                    "quiet_ended duration_s=%d next=%s vib=%.4f"
                    % (duration_s, self.state, vibration)
                )

        elif self.state == STATE_COMPLETE:
            # New cycle also needs steady vibration before STARTED.
            if moving:
                self._begin_starting(now)

        if self.state != prev:
            log_cycle("%s->%s vib=%.4f" % (prev, self.state, vibration))

        return event

    def maybe_heartbeat(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_heartbeat) < self.log_interval_ms:
            return
        self._last_heartbeat = now
        quiet_s = self._quiet_duration_s(now)
        starting_s = 0
        if self.starting_since is not None:
            starting_s = max(0, time.ticks_diff(now, self.starting_since) // 1000)
        log_cycle(
            "hb state=%s vib=%.4f quiet_s=%d starting_s=%d notified=%s"
            % (
                self.state,
                self.last_vibration,
                quiet_s,
                starting_s,
                self.notified,
            )
        )

    def due_for_sample(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_sample) >= self.sample_ms:
            self._last_sample = now
            return True
        return False


def _ensure_wifi(cfg, wlan, led):
    """Connect or reconnect Wi-Fi. Returns wlan or None."""
    try:
        if wlan and wlan.isconnected():
            return wlan
        return connect_wifi(cfg)
    except Exception as exc:
        log_error("wifi", "connect failed", exc)
        led.set_error(True)
        return None


def _ensure_server(wlan, server, monitor, led):
    """Start config UI whenever Wi-Fi is up. Returns server or None."""
    if server:
        return server
    if not (wlan and wlan.isconnected()):
        return None
    try:
        server = ConfigServer(port=80, get_status=monitor.status)
        ip = wifi_ip(wlan)
        server.set_ip(ip)
        print("Config UI: http://%s/  errors: http://%s/api/errors" % (ip, ip))
        return server
    except Exception as exc:
        log_error("webserver", "start failed", exc)
        led.set_error(True)
        return None


def main():
    cfg = load_config()
    led = StatusLed(
        ok_period_ms=int(cfg.get("led_ok_period_ms", 2000)),
        error_period_ms=int(cfg.get("led_error_period_ms", 150)),
    )

    wlan = None
    server = None
    mpu = None
    monitor = LaundryMonitor(cfg)
    monitor.mpu_ok = False
    monitor.last_error = ""
    last_wifi_try = 0
    last_mpu_try = 0

    # Bring up network + web UI first so logs stay reachable even if MPU fails.
    wlan = _ensure_wifi(cfg, wlan, led)
    server = _ensure_server(wlan, server, monitor, led)

    try:
        mpu = make_mpu(cfg)
        monitor.mpu_ok = True
        print("MPU-6050 OK")
    except Exception as exc:
        monitor.last_error = "mpu: %s" % exc
        log_error("mpu", "init failed", exc)
        led.set_error(True)

    print(
        "Running (degraded OK). threshold=%.4f stillness_min=%.1f "
        "start_timer_s=%d mpu_ok=%s"
        % (
            monitor.threshold,
            monitor.stillness_min,
            monitor.start_timer_ms // 1000,
            monitor.mpu_ok,
        )
    )

    while True:
        led.update()
        if server:
            server.poll()

        now = time.ticks_ms()

        # Keep trying Wi-Fi / webserver so error logs stay queryable.
        if not (wlan and wlan.isconnected()):
            if time.ticks_diff(now, last_wifi_try) >= 10000:
                last_wifi_try = now
                cfg = load_config()
                wlan = _ensure_wifi(cfg, wlan, led)
                server = _ensure_server(wlan, server, monitor, led)
        elif server is None:
            server = _ensure_server(wlan, server, monitor, led)

        # Retry MPU periodically without taking down the web UI.
        if mpu is None and time.ticks_diff(now, last_mpu_try) >= 15000:
            last_mpu_try = now
            try:
                mpu = make_mpu(load_config())
                monitor.mpu_ok = True
                monitor.last_error = ""
                led.set_error(False)
                print("MPU-6050 OK (retry)")
            except Exception as exc:
                monitor.mpu_ok = False
                msg = "mpu: %s" % exc
                if msg != monitor.last_error:
                    log_error("mpu", "init retry failed", exc)
                monitor.last_error = msg
                led.set_error(True)

        if mpu is None:
            time.sleep_ms(20)
            continue

        if monitor.due_for_sample():
            try:
                vib = mpu.vibration_level()
                monitor.mpu_ok = True
                led.set_error(False)
            except Exception as exc:
                monitor.mpu_ok = False
                monitor.last_error = "mpu read: %s" % exc
                log_error("mpu", "read failed", exc)
                led.set_error(True)
                mpu = None
                time.sleep_ms(50)
                continue

            event = monitor.update(vib)
            monitor.maybe_heartbeat()
            if event == "STARTED":
                print("STARTED — sending notification")
                try:
                    notify_cycle_started(load_config())
                    log_cycle("event=STARTED notify=ok")
                    print("Notification sent")
                except Exception as exc:
                    monitor.last_error = "notify STARTED: %s" % exc
                    log_cycle("event=STARTED notify=fail err=%s" % exc)
                    log_error("notify", "STARTED webhook failed", exc)
                    led.set_error(True)
            elif event == "COMPLETE" and not monitor.notified:
                print("COMPLETE — sending notification")
                try:
                    # Reload config so webhook edits from the web UI apply.
                    notify_cycle_complete(load_config())
                    monitor.notified = True
                    log_cycle("event=COMPLETE notify=ok")
                    print("Notification sent")
                except Exception as exc:
                    monitor.last_error = "notify COMPLETE: %s" % exc
                    log_cycle("event=COMPLETE notify=fail err=%s" % exc)
                    log_error("notify", "COMPLETE webhook failed", exc)
                    led.set_error(True)

        time.sleep_ms(10)


if __name__ == "__main__":
    main()
