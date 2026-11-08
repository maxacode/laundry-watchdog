"""Washer/dryer completion monitor for Pico W + GY-521 (MPU-6050)."""

from machine import Pin
import time

from config_store import load_config
from mpu6050 import make_mpu
from wifi_connect import connect_wifi, wifi_ip
from webserver import ConfigServer
from notification import notify_cycle_complete, notify_cycle_started

# States
STATE_IDLE = "IDLE"
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


class LaundryMonitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = STATE_IDLE
        self.quiet_since = None
        self.last_vibration = 0.0
        self.notified = False
        self.threshold = float(cfg.get("vibration_threshold", 0.12))
        self.stillness_ms = int(cfg.get("stillness_timeout_ms", 600000))
        self.sample_ms = int(cfg.get("sample_interval_ms", 100))
        self._last_sample = time.ticks_ms()

    def status(self):
        quiet_ms = 0
        if self.quiet_since is not None:
            quiet_ms = time.ticks_diff(time.ticks_ms(), self.quiet_since)
        return {
            "state": self.state,
            "vibration": self.last_vibration,
            "threshold": self.threshold,
            "quiet_ms": quiet_ms,
            "stillness_timeout_ms": self.stillness_ms,
            "notified": self.notified,
        }

    def update(self, vibration):
        self.last_vibration = vibration
        now = time.ticks_ms()
        moving = vibration >= self.threshold
        event = None

        if self.state == STATE_IDLE:
            if moving:
                self.state = STATE_RUNNING
                self.notified = False
                self.quiet_since = None
                event = "STARTED"

        elif self.state == STATE_RUNNING:
            if not moving:
                self.state = STATE_QUIET
                self.quiet_since = now

        elif self.state == STATE_QUIET:
            if moving:
                self.state = STATE_RUNNING
                self.quiet_since = None
            elif time.ticks_diff(now, self.quiet_since) >= self.stillness_ms:
                self.state = STATE_COMPLETE
                event = "COMPLETE"

        elif self.state == STATE_COMPLETE:
            # Stay complete until a new vibration burst starts another cycle.
            if moving:
                self.state = STATE_RUNNING
                self.notified = False
                self.quiet_since = None
                event = "STARTED"

        return event

    def due_for_sample(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_sample) >= self.sample_ms:
            self._last_sample = now
            return True
        return False


def main():
    cfg = load_config()
    led = StatusLed(
        ok_period_ms=int(cfg.get("led_ok_period_ms", 2000)),
        error_period_ms=int(cfg.get("led_error_period_ms", 150)),
    )

    wlan = None
    server = None
    mpu = None
    fatal_error = None

    try:
        wlan = connect_wifi(cfg)
    except Exception as exc:
        fatal_error = "wifi: %s" % exc
        print("Wi-Fi error:", exc)
        led.set_error(True)

    try:
        mpu = make_mpu(cfg)
        print("MPU-6050 OK")
    except Exception as exc:
        fatal_error = "mpu: %s" % exc
        print("MPU-6050 error:", exc)
        led.set_error(True)

    monitor = LaundryMonitor(cfg)

    if wlan and wlan.isconnected():
        try:
            server = ConfigServer(port=80, get_status=monitor.status)
            server.set_ip(wifi_ip(wlan))
            print("Config UI: http://%s/" % wifi_ip(wlan))
        except Exception as exc:
            print("Web server error:", exc)
            led.set_error(True)

    if fatal_error:
        # Keep blinking fast forever if sensor/wifi failed hard.
        while True:
            led.update()
            if server:
                server.poll()
            time.sleep_ms(20)

    print(
        "Monitor ready. threshold=%.4f stillness_ms=%d"
        % (monitor.threshold, monitor.stillness_ms)
    )

    while True:
        led.update()
        if server:
            server.poll()

        if monitor.due_for_sample():
            try:
                vib = mpu.vibration_level()
                led.set_error(False)
            except Exception as exc:
                print("Read error:", exc)
                led.set_error(True)
                time.sleep_ms(50)
                continue

            event = monitor.update(vib)
            if event == "STARTED":
                print("STARTED — sending notification")
                try:
                    notify_cycle_started(load_config())
                    print("Notification sent")
                except Exception as exc:
                    print("Notification failed:", exc)
                    led.set_error(True)
            elif event == "COMPLETE" and not monitor.notified:
                print("COMPLETE — sending notification")
                try:
                    # Reload config so webhook edits from the web UI apply.
                    notify_cycle_complete(load_config())
                    monitor.notified = True
                    print("Notification sent")
                except Exception as exc:
                    print("Notification failed:", exc)
                    led.set_error(True)

        time.sleep_ms(10)


if __name__ == "__main__":
    main()
