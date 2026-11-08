"""Connect the Pico W to Wi-Fi using values from config."""

import network
import time

from config_store import save_config


def connect_wifi(cfg, timeout_ms=20000):
    ssid = cfg.get("wifi_ssid") or ""
    password = cfg.get("wifi_password") or ""
    if not ssid:
        raise ValueError("wifi_ssid is empty in config.json")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("Wi-Fi connect timeout for SSID %r" % ssid)
            time.sleep_ms(200)

    ip = wifi_ip(wlan)
    print("Wi-Fi OK:", ip)
    if ip and cfg.get("wifi_ip") != ip:
        cfg["wifi_ip"] = ip
        save_config(cfg)
        print("Saved wifi_ip to config.json")
    return wlan


def wifi_ip(wlan):
    if not wlan or not wlan.isconnected():
        return None
    return wlan.ifconfig()[0]
