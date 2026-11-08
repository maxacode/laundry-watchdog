# Laundry Watchdog

Raspberry Pi Pico W laundry monitor. Detects washer/dryer start and finish from GY-521 (MPU-6050) vibration, then POSTs JSON to your webhook. Includes a local config web UI.

## Wiring (GY-521 → Pico W)

| GY-521 | Pico W | Notes |
|--------|--------|--------|
| VCC | 3V3 | Use 3.3V only |
| GND | GND | |
| SDA | GP4 | `i2c_sda` in `config.json` |
| SCL | GP5 | `i2c_scl` in `config.json` |
| XDA / XCL / INT | leave unconnected | |
| AD0 | GND | I2C address `0x68` (`mpu_addr`: 104) |

Default pins are GP4/GP5. Change `i2c_sda` / `i2c_scl` in config if you rewire.

## Libraries to upload

No third-party MPU package is required. This repo includes:

| File | Role |
|------|------|
| `mpu6050.py` | MPU-6050 driver |
| `config_store.py` | Load/save `config.json` |
| `wifi_connect.py` | Wi-Fi connect |
| `webserver.py` | Local config HTTP UI |
| `notification.py` | Webhook JSON POST |
| `error_log.py` | Append timestamped errors to `error.log` |
| `main.py` | State machine + LED + orchestration |
| `config.example.json` | Template for local `config.json` |

Built-in MicroPython modules used: `machine`, `network`, `socket`, `ssl`/`ussl`, `json`, `time`, `struct`.

## 1. Flash MicroPython (once)

1. Hold **BOOTSEL**, plug USB, release → `RPI-RP2` drive.
2. Copy a Pico W MicroPython `.uf2` onto the drive (keep firmware locally; it is not in this repo).

## 2. Create `config.json`

Copy the example and fill in your secrets locally (never commit `config.json`):

```bash
cp config.example.json config.json
```

Set at least:

- `wifi_ssid` / `wifi_password`
- `webhook_url` — HTTPS or HTTP endpoint that accepts JSON POSTs
- `webhook_secret` — sent as `x-device-secret` header
- `device_id` (use `washer-01` for the registered washer)
- Tune `vibration_threshold`, `stillness_timeout_min` (default 10), and `start_timer_s` (default 60)

Webhook payload:

```json
{
  "device_id": "washer-01",
  "status": "COMPLETE",
  "message": "The washing machine cycle has finished",
  "timestamp": "uptime_ms:12345"
}
```

`status` is `STARTED` or `COMPLETE` (matching messages).

## 3. Deploy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./deploy.sh
```

Healthy board: onboard LED blinks every **2 seconds**.  
Wi-Fi / sensor / notify errors: **fast blink**.

## 4. Config web UI

After Wi-Fi connects, open `http://<pico-ip>/` on your LAN.  
View/edit settings and Save. Reboot after Wi-Fi or I2C pin changes.  
JSON: `http://<pico-ip>/api/config`  
Error log: `http://<pico-ip>/api/errors` (also on-device as `error.log`)

```bash
./fetch_error_log.sh   # pull into ./error.log and open in browser
mpremote connect auto cat :error.log
```

`./deploy.sh` fetches and opens the log automatically after reboot.

## 5. Test notifications alone

```bash
./test_notification.sh
```

Or:

```bash
mpremote connect auto run notification.py
```

## State machine

1. Vibration ≥ threshold → `STARTING` (must stay above threshold for `start_timer_s`, default 60s)
2. Steady long enough → `RUNNING` → webhook `STARTED` (drop during STARTING returns to `IDLE`)
3. Drops below threshold → `QUIET`, start stillness timer
4. Vibration returns before timeout → back to `RUNNING`, timer reset
5. Still for `stillness_timeout_min` → `COMPLETE` → webhook `COMPLETE`
6. After complete, another steady `start_timer_s` of vibration → `STARTED` again

## LED

| Pattern | Meaning |
|---------|---------|
| Toggle every 2s | Running normally |
| Fast blink (~150ms) | Wi-Fi, MPU, or notification error |
