"""Webhook push notifications for laundry state changes.

Posts JSON to config.webhook_url:
  {"device_id", "status", "message", "timestamp"}

Test alone (with config.json filled in):
  ./test_notification.sh
  # or: mpremote connect auto run notification.py
"""

import json
import time

try:
    import usocket as socket
except ImportError:
    import socket

try:
    import ussl as ssl
except ImportError:
    import ssl

try:
    from config_store import load_config
except ImportError:
    load_config = None

STATUS_MESSAGES = {
    "COMPLETE": "The washing machine cycle has finished",
    "STARTED": "The washing machine cycle has Started",
}


def _timestamp():
    """Wall clock seconds if RTC/NTP set, else uptime seconds."""
    try:
        now = time.time()
        if now > 1_000_000_000:
            return str(int(now))
    except (AttributeError, OSError):
        pass
    return "uptime_ms:%d" % time.ticks_ms()


def build_payload(cfg, status):
    status = str(status).upper()
    if status not in STATUS_MESSAGES:
        raise ValueError("status must be COMPLETE or STARTED, got %r" % status)
    return {
        "device_id": cfg.get("device_id") or "washer-01",
        "status": status,
        "message": STATUS_MESSAGES[status],
        "timestamp": _timestamp(),
    }


def _parse_url(url):
    url = (url or "").strip()
    if not url:
        raise ValueError("webhook_url missing in config")

    if url.startswith("https://"):
        scheme = "https"
        rest = url[8:]
        default_port = 443
    elif url.startswith("http://"):
        scheme = "http"
        rest = url[7:]
        default_port = 80
    else:
        raise ValueError("webhook_url must start with http:// or https://")

    path = "/"
    if "/" in rest:
        hostport, path = rest.split("/", 1)
        path = "/" + path
    else:
        hostport = rest

    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        port = int(port_s)
    else:
        host = hostport
        port = default_port

    if not host:
        raise ValueError("webhook_url has empty host")
    return scheme, host, port, path


def post_json(url, payload, timeout_s=20, secret=None):
    """HTTP(S) POST JSON body. Returns status code int."""
    scheme, host, port, path = _parse_url(url)
    body = json.dumps(payload)
    if isinstance(body, str):
        body = body.encode("utf-8")

    headers = [
        "POST %s HTTP/1.1" % path,
        "Host: %s" % host,
        "User-Agent: pico-w-laundry/1.0",
        "Content-Type: application/json",
        "Content-Length: %d" % len(body),
        "Connection: close",
    ]
    if secret:
        headers.append("x-device-secret: %s" % secret)
    req = "\r\n".join(headers) + "\r\n\r\n"

    addr = socket.getaddrinfo(host, port)[0][-1]
    raw = socket.socket()
    raw.settimeout(timeout_s)
    raw.connect(addr)
    if scheme == "https":
        # Cloudflare and most CDNs require SNI (server_hostname).
        # Pico CA store is limited; skip verify so handshake can complete.
        try:
            sock = ssl.wrap_socket(
                raw,
                server_hostname=host,
                cert_reqs=ssl.CERT_NONE,
            )
        except TypeError:
            # Older MicroPython builds may not accept those kwargs.
            sock = ssl.wrap_socket(raw, server_hostname=host)
    else:
        sock = raw
    try:
        sock.write(req.encode("utf-8") if isinstance(req, str) else req)
        sock.write(body)
        # Read status line only; ignore the rest.
        data = b""
        while b"\r\n" not in data and len(data) < 512:
            chunk = sock.read(64) if hasattr(sock, "read") else sock.recv(64)
            if not chunk:
                break
            data += chunk
        line = data.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
        parts = line.split()
        if len(parts) < 2:
            raise OSError("Bad HTTP response: %r" % line)
        return int(parts[1])
    finally:
        try:
            sock.close()
        except OSError:
            pass


def notify_status(cfg, status):
    """POST laundry status to webhook_url. Returns HTTP status code."""
    url = (cfg.get("webhook_url") or "").strip()
    if not url:
        raise ValueError("webhook_url missing in config")
    secret = (cfg.get("webhook_secret") or "").strip()
    if not secret:
        raise ValueError("webhook_secret missing in config")
    payload = build_payload(cfg, status)
    code = post_json(url, payload, secret=secret)
    print("Webhook %s -> HTTP %s" % (status, code))
    if code < 200 or code >= 300:
        raise OSError("Webhook HTTP %s for %s" % (code, status))
    return code


def notify_cycle_complete(cfg):
    return notify_status(cfg, "COMPLETE")


def notify_cycle_started(cfg):
    return notify_status(cfg, "STARTED")


def notify_test(cfg=None):
    if cfg is None:
        if load_config is None:
            raise RuntimeError("config_store not available")
        cfg = load_config()
    notify_status(cfg, "COMPLETE")
    print("Test notification sent.")
    return True


if __name__ == "__main__":
    from error_log import log_error
    from wifi_connect import connect_wifi

    cfg = load_config()
    try:
        connect_wifi(cfg)
        notify_test(cfg)
    except Exception as exc:
        log_error("notify_test", "failed", exc)
        raise
