
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(r"E:\Apps\Strata-main\Strata-main")
HERE = ROOT / "model-controller"
TOKEN_FILE = HERE / "controller-token.txt"
KEY_FILE = HERE / "strata-key.txt"

HOST = "192.168.1.4"
PORT = 8090
STRATA_URL = "http://127.0.0.1:8080"


def read_secret(path):
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"Empty secret file: {path.name}")
    return value


def strata_health():
    req = Request(f"{STRATA_URL}/api/health")
    with urlopen(req, timeout=3) as response:
        return json.loads(response.read())


def strata_status():
    key = read_secret(KEY_FILE)
    req = Request(
        f"{STRATA_URL}/v1/status",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urlopen(req, timeout=3) as response:
        return json.loads(response.read())


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not secrets.compare_digest(
            self.headers.get("Authorization", ""),
            "Bearer " + read_secret(TOKEN_FILE),
        ):
            self.reply(401, {"error": "unauthorized"})
            return

        if self.path != "/status":
            self.reply(404, {"error": "unknown endpoint"})
            return

        try:
            health = strata_health()
            status = strata_status()
            self.reply(200, {
                "controller": "ok",
                "strata": {
                    "model": health.get("model"),
                    "loaded": health.get("loaded"),
                    "service": health.get("service"),
                    "busy": status.get("busy"),
                    "queued": status.get("queued"),
                },
            })
        except Exception as exc:
            self.reply(503, {
                "controller": "ok",
                "strata_error": str(exc),
            })

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    for path in (TOKEN_FILE, KEY_FILE):
        if not path.is_file():
            raise SystemExit(f"Missing required file: {path}")

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Read-only controller listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping controller.")
    finally:
        server.server_close()
