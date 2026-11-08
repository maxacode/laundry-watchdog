"""Load and save device configuration from config.json on the Pico."""

import json
import os

CONFIG_PATH = "config.json"

DEFAULTS = {
    "wifi_ssid": "",
    "wifi_password": "",
    "wifi_ip": "",
    "webhook_url": "",
    "webhook_secret": "",
    "device_id": "washer-01",
    "vibration_threshold": 0.12,
    "stillness_timeout_min": 10,
    "start_timer_s": 60,
    "cycle_log_interval_s": 30,
    "sample_interval_ms": 100,
    "i2c_sda": 4,
    "i2c_scl": 5,
    "i2c_freq": 400000,
    "mpu_addr": 104,
    "led_ok_period_ms": 2000,
    "led_error_period_ms": 150,
}


def load_config(path=CONFIG_PATH):
    cfg = dict(DEFAULTS)
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except OSError:
        pass
    except ValueError:
        pass
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    merged = dict(DEFAULTS)
    merged.update(cfg)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(merged, f)
    try:
        os.remove(path)
    except OSError:
        pass
    os.rename(tmp, path)
    return merged
