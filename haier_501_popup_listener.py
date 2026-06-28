import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path


HOST = "172.30.2.47"
PORT = 46752
DOOR_IP = "172.30.2.36"
BASE = Path(__file__).resolve().parent
LOG = BASE / "haier_501_popup_listener.log"
PID_FILE = BASE / "haier_501_popup_listener.pid"
POPUP_COOLDOWN_SECONDS = 5


def log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='milliseconds')} {message}"
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def show_popup(remote_ip: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"501 门禁来电\n门口机：{remote_ip}\n时间：{timestamp}"
    command = (
        "Add-Type -AssemblyName PresentationFramework; "
        "[System.Media.SystemSounds]::Exclamation.Play(); "
        f"[void][System.Windows.MessageBox]::Show('{message}', '海尔门禁提醒')"
    )
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", command],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def main() -> None:
    PID_FILE.write_text(str(__import__("os").getpid()), encoding="ascii")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(8)
    log(f"LISTEN {HOST}:{PORT}")
    last_popup = 0.0

    try:
        while True:
            client, address = server.accept()
            client.settimeout(5)
            received = bytearray()
            try:
                while True:
                    block = client.recv(4096)
                    if not block:
                        break
                    received.extend(block)
            except socket.timeout:
                pass
            finally:
                client.close()

            log(f"CALL from={address[0]}:{address[1]} bytes={len(received)} hex={received.hex()}")
            now = time.monotonic()
            if address[0] == DOOR_IP and len(received) == 34 and now - last_popup >= POPUP_COOLDOWN_SECONDS:
                show_popup(address[0])
                last_popup = now
                log("POPUP shown")
    finally:
        server.close()
        PID_FILE.unlink(missing_ok=True)
        log("STOP")


if __name__ == "__main__":
    main()
