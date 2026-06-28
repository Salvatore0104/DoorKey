from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path


ACTIONS = {
    "ring": "呼叫但不接听/呼叫开始",
    "answer": "按下接听",
    "unlock": "按下开门",
    "hangup": "按下挂断",
    "monitor_start": "主动监视开始",
    "monitor_stop": "主动监视停止",
    "tone_start": "已知测试音开始",
    "tone_stop": "已知测试音停止",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def list_interfaces(tshark: str) -> None:
    subprocess.run([tshark, "-D"], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="HR-6107 901 双向抓包与动作标记")
    parser.add_argument("--interface", "-i", help="tshark 接口编号或名称")
    parser.add_argument("--output", "-o", type=Path, help="输出 pcapng")
    parser.add_argument("--list", action="store_true", help="列出抓包接口")
    parser.add_argument("--tshark", default=shutil.which("tshark") or "tshark")
    args = parser.parse_args()

    if args.list:
        list_interfaces(args.tshark)
        return 0
    if not args.interface:
        parser.error("需要 --interface；先用 --list 查看编号")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = (args.output or Path(f"captures/901_bidirectional_{stamp}.pcapng")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    marker_path = output.with_suffix(".markers.json")
    markers: list[dict] = []

    command = [
        args.tshark,
        "-i",
        str(args.interface),
        "-f",
        "host 172.30.2.55 or host 172.30.2.36",
        "-w",
        str(output),
    ]
    print(f"开始抓包: {output}")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL)

    def save() -> None:
        marker_path.write_text(
            json.dumps(
                {
                    "capture": str(output),
                    "terminal_ip": "172.30.2.55",
                    "door_ip": "172.30.2.36",
                    "markers": markers,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print("输入动作名称后回车即可打点；note 自定义说明；quit 完成。")
    print("可用动作:", ", ".join(ACTIONS))
    try:
        while process.poll() is None:
            value = input("901> ").strip()
            if value == "quit":
                break
            if value == "note":
                label = input("说明> ").strip()
                action = "note"
            elif value in ACTIONS:
                action, label = value, ACTIONS[value]
            else:
                print("未知动作；可用:", ", ".join([*ACTIONS, "note", "quit"]))
                continue
            marker = {"index": len(markers) + 1, "time": now_iso(), "action": action, "label": label}
            markers.append(marker)
            save()
            print(f"已标记 #{marker['index']} {marker['time']} {label}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        save()

    print(f"抓包完成: {output}")
    print(f"动作标记: {marker_path}")
    print(f"下一步: python tools/analyze_901.py \"{output}\"")
    return process.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())

