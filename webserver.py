"""Tiny local HTTP config UI for the Pico W."""

import json
import socket
import time

from config_store import load_config, save_config

EDITABLE_KEYS = [
    "wifi_ssid",
    "wifi_password",
    "webhook_url",
    "device_id",
    "vibration_threshold",
    "stillness_timeout_ms",
    "sample_interval_ms",
    "i2c_sda",
    "i2c_scl",
    "i2c_freq",
    "mpu_addr",
    "led_ok_period_ms",
    "led_error_period_ms",
]


def _html_escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _page(cfg, status="", ip=""):
    rows = []
    for key in EDITABLE_KEYS:
        val = cfg.get(key, "")
        input_type = "password" if "password" in key else "text"
        rows.append(
            '<label>%s<br><input name="%s" type="%s" value="%s" '
            'style="width:100%%"></label><br><br>'
            % (key, key, input_type, _html_escape(val))
        )

    return (
        "<!DOCTYPE html><html><head><meta name='viewport' "
        "content='width=device-width,initial-scale=1'>"
        "<title>Laundry Monitor Config</title>"
        "<style>body{font-family:sans-serif;max-width:520px;margin:1.5rem auto;"
        "padding:0 1rem}input,textarea{font:inherit;padding:.4rem}"
        "button{padding:.6rem 1rem;font:inherit}.ok{color:green}.err{color:#b00}"
        "</style></head><body>"
        "<h1>Laundry Monitor</h1>"
        "<p>IP: %s</p>"
        "<p class='%s'>%s</p>"
        "<form method='POST' action='/save'>"
        "%s"
        "<button type='submit'>Save config</button>"
        "</form>"
        "<p><a href='/api/config'>Raw JSON</a></p>"
        "</body></html>"
    ) % (
        _html_escape(ip or "?"),
        "ok" if status.startswith("Saved") else ("err" if status else ""),
        _html_escape(status),
        "".join(rows),
    )


def _parse_form(body):
    result = {}
    for pair in body.split("&"):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k = _urldecode(k)
        v = _urldecode(v)
        result[k] = v
    return result


def _urldecode(text):
    text = text.replace("+", " ")
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "%" and i + 2 < len(text):
            try:
                out.append(chr(int(text[i + 1 : i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(ch)
        i += 1
    return "".join(out)


def _coerce(cfg, form):
    updated = dict(cfg)
    float_keys = {"vibration_threshold"}
    int_keys = {
        "stillness_timeout_ms",
        "sample_interval_ms",
        "i2c_sda",
        "i2c_scl",
        "i2c_freq",
        "mpu_addr",
        "led_ok_period_ms",
        "led_error_period_ms",
    }
    for key in EDITABLE_KEYS:
        if key not in form:
            continue
        raw = form[key]
        if key in float_keys:
            updated[key] = float(raw)
        elif key in int_keys:
            updated[key] = int(float(raw))
        else:
            updated[key] = raw
    return updated


def _http_response(status, body, content_type="text/html; charset=utf-8"):
    if isinstance(body, str):
        body = body.encode("utf-8")
    headers = (
        "HTTP/1.0 %s\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n"
    ) % (status, content_type, len(body))
    return headers.encode("utf-8") + body


class ConfigServer:
    def __init__(self, port=80, get_status=None):
        self.port = port
        self.get_status = get_status or (lambda: {})
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.listen(2)
        self.sock.setblocking(False)
        self.ip = ""

    def set_ip(self, ip):
        self.ip = ip or ""

    def poll(self):
        try:
            client, _addr = self.sock.accept()
        except OSError:
            return

        client.settimeout(2)
        try:
            req = b""
            while b"\r\n\r\n" not in req and len(req) < 4096:
                chunk = client.recv(512)
                if not chunk:
                    break
                req += chunk

            header, _, rest = req.partition(b"\r\n\r\n")
            lines = header.decode("utf-8", "ignore").split("\r\n")
            if not lines:
                return
            parts = lines[0].split()
            method = parts[0] if parts else "GET"
            path = parts[1] if len(parts) > 1 else "/"

            content_length = 0
            for line in lines[1:]:
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())

            body = rest
            while len(body) < content_length:
                body += client.recv(512)

            response = self._handle(method, path, body.decode("utf-8", "ignore"))
            client.sendall(response)
        except Exception as exc:
            try:
                err = _http_response("500 Internal Server Error", "Error: %s" % exc)
                client.sendall(err)
            except OSError:
                pass
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _handle(self, method, path, body):
        cfg = load_config()
        status_info = self.get_status()
        status_note = "state=%s vibration=%.4f" % (
            status_info.get("state", "?"),
            float(status_info.get("vibration", 0.0)),
        )

        if path.startswith("/api/config"):
            payload = dict(cfg)
            payload["_status"] = status_info
            return _http_response(
                "200 OK",
                json.dumps(payload),
                "application/json",
            )

        if method == "POST" and path.startswith("/save"):
            try:
                form = _parse_form(body)
                updated = _coerce(cfg, form)
                save_config(updated)
                cfg = load_config()
                note = "Saved. Reboot Pico to apply Wi-Fi/I2C pin changes. %s" % status_note
            except Exception as exc:
                note = "Save failed: %s" % exc
            return _http_response("200 OK", _page(cfg, note, self.ip))

        return _http_response("200 OK", _page(cfg, status_note, self.ip))
