from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path


TERMINAL = "172.30.2.55"
DOOR = "172.30.2.36"


def tshark_rows(tshark: str, capture: Path) -> list[dict[str, str]]:
    fields = [
        "frame.number",
        "frame.time_epoch",
        "ip.src",
        "ip.dst",
        "tcp.srcport",
        "tcp.dstport",
        "udp.srcport",
        "udp.dstport",
        "tcp.payload",
        "udp.payload",
        "frame.len",
    ]
    command = [tshark, "-r", str(capture), "-Y", "ip.addr==172.30.2.55 || ip.addr==172.30.2.36", "-T", "fields"]
    for field in fields:
        command.extend(["-e", field])
    command.extend(["-E", "header=y", "-E", "separator=\t", "-E", "quote=d"])
    result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return list(csv.DictReader(result.stdout.splitlines(), delimiter="\t", quotechar='"'))


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def clean_hex(value: str) -> str:
    return value.replace(":", "").replace(",", "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 HR-6107 901 双向抓包")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--markers", type=Path)
    parser.add_argument("--tshark", default=shutil.which("tshark") or "tshark")
    parser.add_argument("--window", type=float, default=2.0, help="动作前后分析窗口秒数")
    args = parser.parse_args()

    capture = args.capture.resolve()
    markers_path = args.markers or capture.with_suffix(".markers.json")
    rows = tshark_rows(args.tshark, capture)
    directions = Counter()
    port_stats = Counter()
    tcp_payloads = []
    media = Counter()

    for row in rows:
        src, dst = row.get("ip.src", ""), row.get("ip.dst", "")
        if src and dst:
            directions[f"{src}->{dst}"] += 1
        protocol_port = row.get("tcp.dstport") or row.get("udp.dstport") or "other"
        port_stats[protocol_port] += 1
        tcp_hex = clean_hex(row.get("tcp.payload", ""))
        if tcp_hex:
            tcp_payloads.append(
                {
                    "frame": int(row["frame.number"]),
                    "time": float(row["frame.time_epoch"]),
                    "src": src,
                    "dst": dst,
                    "src_port": row.get("tcp.srcport"),
                    "dst_port": row.get("tcp.dstport"),
                    "bytes": len(tcp_hex) // 2,
                    "hex": tcp_hex,
                }
            )
        udp_dst = row.get("udp.dstport")
        if udp_dst in {"46753", "46754"}:
            media[f"{src}->{dst}:{udp_dst}"] += 1

    seen_terminal_tx = directions[f"{TERMINAL}->{DOOR}"] > 0
    seen_door_tx = directions[f"{DOOR}->{TERMINAL}"] > 0
    markers = []
    if markers_path.exists():
        markers = json.loads(markers_path.read_text(encoding="utf-8")).get("markers", [])

    action_windows = []
    for marker in markers:
        center = epoch(marker["time"])
        candidates = [
            payload
            for payload in tcp_payloads
            if center - args.window <= payload["time"] <= center + args.window
        ]
        action_windows.append({**marker, "tcp_payloads": candidates})

    report = {
        "capture": str(capture),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "validation": {
            "terminal_to_door_seen": seen_terminal_tx,
            "door_to_terminal_seen": seen_door_tx,
            "bidirectional": seen_terminal_tx and seen_door_tx,
            "usable_for_command_inference": seen_terminal_tx and seen_door_tx and bool(markers),
        },
        "directions": dict(directions),
        "destination_ports": dict(port_stats),
        "media": dict(media),
        "tcp_payloads": tcp_payloads,
        "action_windows": action_windows,
        "warning": (
            None
            if seen_terminal_tx and seen_door_tx
            else "缺少至少一个方向；停止命令推导，改用交换机端口镜像或真正网络 TAP。"
        ),
    }
    output = capture.with_suffix(".analysis.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["validation"], ensure_ascii=False, indent=2))
    if report["warning"]:
        print("警告:", report["warning"])
    print("分析报告:", output)
    print("注意：分析器不会自动启用控制命令；需人工核对三次重复样本后再更新 protocol_profile.json。")
    return 0 if report["validation"]["usable_for_command_inference"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

