import socket
import time
from datetime import datetime
from pathlib import Path


HOST = "172.30.2.47"
PORT = 46752
RUN_SECONDS = 300
IDLE_SECONDS = 20
BASE = Path(__file__).resolve().parent
LOG = BASE / "haier_46752_listener.log"


def log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='milliseconds')} {message}"
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def main() -> None:
    deadline = time.monotonic() + RUN_SECONDS
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(8)
    server.settimeout(1)
    log(f"LISTEN {HOST}:{PORT}")

    connection_number = 0
    while time.monotonic() < deadline:
        try:
            client, address = server.accept()
        except socket.timeout:
            continue

        connection_number += 1
        client.settimeout(IDLE_SECONDS)
        log(f"ACCEPT #{connection_number} {address[0]}:{address[1]}")
        received = bytearray()
        try:
            while time.monotonic() < deadline:
                try:
                    block = client.recv(65535)
                except socket.timeout:
                    log(f"TIMEOUT #{connection_number}")
                    break
                if not block:
                    log(f"CLOSE #{connection_number}")
                    break
                received.extend(block)
                log(f"RECV #{connection_number} bytes={len(block)} hex={block.hex()}")
        finally:
            client.close()
            binary_path = BASE / f"haier_46752_connection_{connection_number}.bin"
            binary_path.write_bytes(received)
            log(f"SAVED #{connection_number} total={len(received)} file={binary_path.name}")

    server.close()
    log("STOP")


if __name__ == "__main__":
    main()
