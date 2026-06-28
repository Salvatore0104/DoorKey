"""从抓包文件提取上行音频 UDP 46753 包，逆向还原 20 字节私有头模板和序号偏移。

用法：
    python tools/extract_audio_tx_header.py captures/901_upstream_direction_check.pcapng

依赖：scapy (pip install scapy)

输出：
    - 逐包 20 字节头的十六进制对照
    - 静态字段（所有包相同的字节）和动态字段（变化的字节）
    - 推测的序号字段偏移和字节序
    - 可直接写入 protocol_profile.json 的 header_template_hex 和 sequence_offset
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TERMINAL = "172.30.2.55"
DOOR = "172.30.2.36"
AUDIO_PORT = 46753
HEADER_LEN = 20


def scapy_audio_rows(capture: Path, terminal_ip: str, door_ip: str) -> list[dict]:
    """使用 scapy 提取上行 46753 音频包。"""
    try:
        from scapy.all import rdpcap, UDP, IP
    except ImportError:
        print("错误：需要 scapy 库。请运行: pip install scapy", file=sys.stderr)
        sys.exit(1)

    packets = rdpcap(str(capture))
    rows = []
    for i, pkt in enumerate(packets, 1):
        if IP not in pkt or UDP not in pkt:
            continue
        ip_layer = pkt[IP]
        udp_layer = pkt[UDP]
        if ip_layer.src != terminal_ip or ip_layer.dst != door_ip:
            continue
        if udp_layer.dport != AUDIO_PORT:
            continue
        payload = bytes(udp_layer.payload)
        if not payload:
            continue
        rows.append(
            {
                "frame.number": str(i),
                "frame.time_epoch": float(pkt.time),
                "ip.src": ip_layer.src,
                "ip.dst": ip_layer.dst,
                "udp.srcport": str(udp_layer.sport),
                "udp.dstport": str(udp_layer.dport),
                "udp.payload": payload.hex(),
                "frame.len": len(pkt),
            }
        )
    return rows


def analyze_headers(headers: list[bytes]) -> dict:
    """逐字节分析 20 字节头，区分静态字段和动态字段。"""
    if not headers:
        return {"error": "no headers"}

    length = len(headers[0])
    static_mask = [True] * length
    static_values = [headers[0][i] for i in range(length)]
    per_byte_values: list[set] = [set() for _ in range(length)]

    for header in headers:
        for i in range(min(length, len(header))):
            per_byte_values[i].add(header[i])
            if header[i] != static_values[i]:
                static_mask[i] = False

    # 找连续的动态字段作为序号候选
    dynamic_ranges = []
    i = 0
    while i < length:
        if not static_mask[i]:
            start = i
            while i < length and not static_mask[i]:
                i += 1
            dynamic_ranges.append((start, i))
        else:
            i += 1

    # 对每个动态字段范围，检查是否单调递增（序号特征）
    sequence_candidates = []
    for start, end in dynamic_ranges:
        size = end - start
        values = []
        for header in headers:
            chunk = header[start:end]
            big_val = int.from_bytes(chunk, "big")
            little_val = int.from_bytes(chunk, "little")
            values.append((big_val, little_val))

        big_diffs = [values[i + 1][0] - values[i][0] for i in range(len(values) - 1)]
        little_diffs = [values[i + 1][1] - values[i][1] for i in range(len(values) - 1)]

        big_increasing = all(d >= 0 and d < 100 for d in big_diffs) if big_diffs else False
        little_increasing = all(d >= 0 and d < 100 for d in little_diffs) if little_diffs else False
        big_constant_step = (
            len(set(big_diffs)) <= 2 if big_diffs else False
        )
        little_constant_step = (
            len(set(little_diffs)) <= 2 if little_diffs else False
        )

        candidate = {
            "offset": start,
            "size": size,
            "big_endian": {
                "values": [v[0] for v in values],
                "diffs": big_diffs,
                "monotonic_increasing": big_increasing,
                "constant_step": big_constant_step,
            },
            "little_endian": {
                "values": [v[1] for v in values],
                "diffs": little_diffs,
                "monotonic_increasing": little_increasing,
                "constant_step": little_constant_step,
            },
        }
        sequence_candidates.append(candidate)

    # 构建模板：静态字段填实际值，动态字段填 0x00 占位
    template = bytearray(length)
    for i in range(length):
        template[i] = static_values[i] if static_mask[i] else 0x00

    return {
        "header_length": length,
        "packet_count": len(headers),
        "static_mask": static_mask,
        "template_hex": template.hex(),
        "dynamic_ranges": dynamic_ranges,
        "per_byte_unique_counts": [len(s) for s in per_byte_values],
        "sequence_candidates": sequence_candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从抓包提取上行音频 UDP 46753 包的 20 字节私有头并逆向分析"
    )
    parser.add_argument("capture", type=Path, help="pcapng 抓包文件路径")
    parser.add_argument(
        "--terminal-ip",
        default=TERMINAL,
        help=f"终端 IP（默认 {TERMINAL}）",
    )
    parser.add_argument(
        "--door-ip",
        default=DOOR,
        help=f"门口机 IP（默认 {DOOR}）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出 JSON 报告路径（默认打印到 stdout）",
    )
    args = parser.parse_args()

    capture = args.capture.resolve()
    if not capture.exists():
        print(f"错误：抓包文件不存在: {capture}", file=sys.stderr)
        return 1

    print(f"正在提取 {args.terminal_ip} -> {args.door_ip}:{AUDIO_PORT} 的音频包...", file=sys.stderr)
    rows = scapy_audio_rows(capture, args.terminal_ip, args.door_ip)

    if not rows:
        print("警告：未找到上行音频包。请确认抓包包含终端→门口机的 UDP 46753 流量。", file=sys.stderr)
        return 2

    print(f"找到 {len(rows)} 个上行音频包", file=sys.stderr)

    headers: list[bytes] = []
    payloads: list[bytes] = []
    raw_packets: list[dict] = []

    for row in rows:
        hex_str = row.get("udp.payload", "")
        if not hex_str:
            continue
        payload = bytes.fromhex(hex_str)
        if len(payload) <= HEADER_LEN:
            print(
                f"  跳过 frame {row.get('frame.number', '?')}: 载荷仅 {len(payload)} 字节",
                file=sys.stderr,
            )
            continue
        header = payload[:HEADER_LEN]
        audio_data = payload[HEADER_LEN:]
        headers.append(header)
        payloads.append(audio_data)
        raw_packets.append(
            {
                "frame": int(row.get("frame.number", 0)),
                "time": float(row.get("frame.time_epoch", 0)),
                "src_port": row.get("udp.srcport", ""),
                "header_hex": header.hex(),
                "payload_len": len(audio_data),
                "payload_preview": audio_data[:16].hex(),
            }
        )

    if not headers:
        print("错误：没有有效的上行音频包（载荷均短于 20 字节头）。", file=sys.stderr)
        return 3

    analysis = analyze_headers(headers)

    report = {
        "capture": str(capture),
        "terminal_ip": args.terminal_ip,
        "door_ip": args.door_ip,
        "audio_port": AUDIO_PORT,
        "header_length": HEADER_LEN,
        "total_packets": len(rows),
        "valid_packets": len(headers),
        "raw_packets": raw_packets[:20],
        "analysis": analysis,
    }

    # 推荐配置
    best_seq = None
    best_score = -1
    for cand in analysis.get("sequence_candidates", []):
        score = 0
        if cand["big_endian"]["monotonic_increasing"]:
            score += 10
        if cand["big_endian"]["constant_step"]:
            score += 5
        if cand["little_endian"]["monotonic_increasing"]:
            score += 10
        if cand["little_endian"]["constant_step"]:
            score += 5
        if score > best_score:
            best_score = score
            best_seq = cand

    recommendation = {
        "header_template_hex": analysis.get("template_hex", ""),
        "sequence_offset": best_seq["offset"] if best_seq and best_score > 0 else None,
        "sequence_size": best_seq["size"] if best_seq and best_score > 0 else 2,
        "sequence_byteorder": (
            "big"
            if best_seq and best_score > 0 and best_seq["big_endian"]["monotonic_increasing"]
            else "little"
        ),
        "packet_samples": (
            len(payloads[0]) // 2 if payloads else 256
        ),  # PCM s16 样本数
        "confidence": "high" if best_score >= 15 else "medium" if best_score >= 10 else "low",
    }
    report["recommendation"] = recommendation

    output_json = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
        print(f"报告已写入: {args.output}", file=sys.stderr)
    else:
        print(output_json)

    print("\n" + "=" * 60, file=sys.stderr)
    print("推荐写入 protocol_profile.json 的 audio_tx 配置：", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(
        json.dumps(
            {
                "verified": recommendation["confidence"] in ("high", "medium"),
                "header_template_hex": recommendation["header_template_hex"],
                "sequence_offset": recommendation["sequence_offset"],
                "sequence_size": recommendation["sequence_size"],
                "sequence_byteorder": recommendation["sequence_byteorder"],
                "packet_samples": recommendation["packet_samples"],
                "sample_rate": 8000,
                "codec": "pcmu",
            },
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )
    print(f"\n置信度: {recommendation['confidence']}", file=sys.stderr)

    if recommendation["confidence"] == "low":
        print(
            "警告：序号字段识别置信度低，请人工检查 raw_packets 中的 header_hex 逐包对照。",
            file=sys.stderr,
        )
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
