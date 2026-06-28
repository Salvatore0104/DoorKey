import json
import socket
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DEVICE_IP = "172.30.2.47"
CONTROL_PORT = 46752
DOOR_IP = "172.30.2.36"
WEB_HOST = "127.0.0.1"
WEB_PORT = 8088
BASE = Path(__file__).resolve().parent
HTML_FILE = BASE / "haier_dashboard.html"
LOG_FILE = BASE / "haier_dashboard.log"

lock = threading.Lock()
events = deque(maxlen=1000)
next_event_id = 1
state = {
    "listener": "starting",
    "last_call": None,
    "last_call_epoch": 0.0,
    "call_count": 0,
    "rx_bytes": 0,
    "tx_bytes": 0,
    "door_ip": DOOR_IP,
    "device_ip": DEVICE_IP,
    "control_port": CONTROL_PORT,
    "unlock_available": False,
}


def add_event(direction: str, level: str, message: str, hex_data: str = "") -> None:
    global next_event_id
    now = datetime.now()
    event = {
        "id": next_event_id,
        "time": now.strftime("%H:%M:%S.%f")[:-3],
        "direction": direction,
        "level": level,
        "message": message,
        "hex": hex_data,
    }
    with lock:
        next_event_id += 1
        events.append(event)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def tcp_listener() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((DEVICE_IP, CONTROL_PORT))
    server.listen(8)
    with lock:
        state["listener"] = "online"
    add_event("SYS", "ok", f"监听 {DEVICE_IP}:{CONTROL_PORT}")

    while True:
        client, address = server.accept()
        client.settimeout(5)
        add_event("RX", "info", f"TCP连接 {address[0]}:{address[1]}")
        received = bytearray()
        try:
            while True:
                block = client.recv(4096)
                if not block:
                    break
                received.extend(block)
        except socket.timeout:
            add_event("SYS", "warn", "连接读取超时")
        finally:
            client.close()

        payload = bytes(received)
        with lock:
            state["rx_bytes"] += len(payload)
            if address[0] == DOOR_IP and len(payload) == 34:
                state["last_call_epoch"] = time.time()
                state["last_call"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state["call_count"] += 1
        if payload:
            add_event("RX", "call" if len(payload) == 34 else "info", f"收到 {len(payload)} 字节来电控制报文", payload.hex())
        else:
            add_event("RX", "warn", "连接关闭，未收到数据")
        add_event("SYS", "info", "连接已关闭；未发送应用层响应")


class Handler(BaseHTTPRequestHandler):
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/state":
            with lock:
                snapshot = dict(state)
            snapshot["call_active"] = time.time() - snapshot["last_call_epoch"] < 15
            self.send_json(snapshot)
            return
        if parsed.path == "/api/logs":
            query = parse_qs(parsed.query)
            after = int(query.get("after", ["0"])[0])
            with lock:
                result = [event for event in events if event["id"] > after]
            self.send_json({"events": result})
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/api/unlock":
            add_event("TX", "blocked", "开门请求被阻止：协议尚未确认，未发送任何数据")
            self.send_json({"ok": False, "error": "开门协议尚未确认，功能已安全禁用"}, 409)
            return
        self.send_json({"error": "not found"}, 404)

    def log_message(self, format, *args):
        return


def main() -> None:
    add_event("SYS", "info", "501本地门禁仪表盘启动")
    threading.Thread(target=tcp_listener, daemon=True).start()
    web = ThreadingHTTPServer((WEB_HOST, WEB_PORT), Handler)
    add_event("SYS", "ok", f"网页 http://{WEB_HOST}:{WEB_PORT}")
    web.serve_forever()


if __name__ == "__main__":
    main()
