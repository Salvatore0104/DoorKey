/*
 * HR-6107 门禁协议实现
 * 控制帧格式: FF FF [长度2B] [载荷] [校验]
 */

#include "door_protocol.h"
#include <string.h>
#include <arpa/inet.h>

/* 已验证的控制命令 (来自 protocol_profile.json) */
/* call_ack: ffff001c000000000000000000000f0101...fe */
/* answer:   ffff001a0000000000000000000005fe (简化) */
/* hangup:   ffff001a0000000000000000000006fe */
/* unlock:   ffff001a00000000000000010300010001020501ac1e022f0003fe */

/* 命令尾部标识 */
#define CMD_TAIL_ANSWER   0x05
#define CMD_TAIL_HANGUP   0x06
#define CMD_TAIL_UNLOCK   0x03

/* 呼叫确认完整帧 (call_ack, 已从profile填充) */
static const uint8_t CMD_CALL_ACK[] = {
    0xff, 0xff, 0x00, 0x1c, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0f, 0x01,
    0x01, 0x00, 0x01, 0x00, 0x01, 0x02, 0x05, 0x01,
    0xac, 0x1e, 0x02, 0x2f, 0x00, 0x0f, 0x01, 0xfe
};

/* answer 命令帧 */
static const uint8_t CMD_ANSWER[] = {
    0xff, 0xff, 0x00, 0x1a, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x05, 0xfe
};

/* hangup 命令帧 */
static const uint8_t CMD_HANGUP[] = {
    0xff, 0xff, 0x00, 0x1a, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x06, 0xfe
};

/* unlock 命令帧 */
static const uint8_t CMD_UNLOCK[] = {
    0xff, 0xff, 0x00, 0x1a, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01,
    0x03, 0x00, 0x01, 0x00, 0x01, 0x02, 0x05, 0x01,
    0xac, 0x1e, 0x02, 0x2f, 0x00, 0x03, 0xfe
};

frame_kind_t door_parse_control_frame(const uint8_t *data, size_t len)
{
    if (len < 6 || data[0] != 0xFF || data[1] != 0xFF) {
        return FRAME_KIND_UNKNOWN;
    }
    /* 检查帧尾 0xFE */
    if (data[len - 1] != 0xFE) {
        return FRAME_KIND_UNKNOWN;
    }
    /* 根据倒数第二字节判断类型 */
    uint8_t cmd = data[len - 2];
    switch (cmd) {
        case 0x05: return FRAME_KIND_ANSWER;
        case 0x06: return FRAME_KIND_HANGUP;
        case 0x03: return FRAME_KIND_UNLOCK;
        default:
            /* call_start / call_end 需检查更长帧 */
            if (len >= 30 && cmd == 0x01 && data[len - 3] == 0x0f) {
                return FRAME_KIND_CALL_ACK;
            }
            /* call_start 特征: 包含 0x01 0x01 0x01...0x01 0xfe */
            if (len >= 30 && data[14] == 0x01 && data[15] == 0x01) {
                return FRAME_KIND_CALL_START;
            }
            if (len >= 24 && cmd == 0x06) {
                return FRAME_KIND_CALL_END;
            }
            return FRAME_KIND_UNKNOWN;
    }
}

size_t door_build_command(frame_kind_t kind, uint8_t *out, size_t out_size)
{
    const uint8_t *src = NULL;
    size_t src_len = 0;

    switch (kind) {
        case FRAME_KIND_CALL_ACK:
            src = CMD_CALL_ACK;
            src_len = sizeof(CMD_CALL_ACK);
            break;
        case FRAME_KIND_ANSWER:
            src = CMD_ANSWER;
            src_len = sizeof(CMD_ANSWER);
            break;
        case FRAME_KIND_HANGUP:
            src = CMD_HANGUP;
            src_len = sizeof(CMD_HANGUP);
            break;
        case FRAME_KIND_UNLOCK:
            src = CMD_UNLOCK;
            src_len = sizeof(CMD_UNLOCK);
            break;
        default:
            return 0;
    }

    if (out_size < src_len) {
        return 0;
    }
    memcpy(out, src, src_len);
    return src_len;
}

void door_build_audio_tx_packet(uint8_t *packet, const uint8_t *ulaw_data,
                                size_t ulaw_len, uint8_t sequence)
{
    /* 填充20字节头模板 */
    memcpy(packet, AUDIO_TX_HEADER_TEMPLATE, AUDIO_HEADER_LEN);
    /* 写入序号 (offset=3, 1字节, big-endian) */
    packet[AUDIO_TX_SEQ_OFFSET] = sequence;
    /* 填充μ-law音频数据 */
    if (ulaw_len > 0 && ulaw_data) {
        memcpy(packet + AUDIO_HEADER_LEN, ulaw_data, ulaw_len);
    }
}
