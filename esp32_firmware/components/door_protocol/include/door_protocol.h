/*
 * HR-6107 门禁协议定义
 * 基于抓包逆向: protocol_profile.json
 */

#ifndef DOOR_PROTOCOL_H
#define DOOR_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

/* 网络端口 */
#define DOOR_CONTROL_PORT   46752   /* TCP 控制 */
#define DOOR_AUDIO_PORT     46753   /* UDP 音频(双向) */
#define DOOR_VIDEO_PORT     46754   /* UDP 视频(下行) */

/* 私有头长度 */
#define AUDIO_HEADER_LEN    20      /* 音频包20字节私有头 */
#define VIDEO_HEADER_LEN    25      /* 视频包25字节私有头 */

/* 音频参数 */
#define AUDIO_SAMPLE_RATE   8000    /* 8kHz */
#define AUDIO_PACKET_SAMPLES 512   /* 每包512样本 = 512字节μ-law */

/* 上行音频头模板 (从抓包逆向: offset=3为1字节序号) */
/* 原始: 0000000000000400000000006a41aa0000000000 */
static const uint8_t AUDIO_TX_HEADER_TEMPLATE[AUDIO_HEADER_LEN] = {
    0x00, 0x00, 0x00, 0x00,   /* [0:3] 静态 + [3]序号(步长1, mod32) */
    0x00, 0x00, 0x04, 0x00,   /* [4:7] 静态 */
    0x00, 0x00, 0x00, 0x00,   /* [8:11] 静态 */
    0x6a, 0x41, 0xaa, 0x00,   /* [12:15] 会话标识(6a41 + aaxx) */
    0x00, 0x00, 0x00, 0x00    /* [16:19] 时间戳/校验(置0) */
};
#define AUDIO_TX_SEQ_OFFSET  3      /* 序号在头中的偏移 */
#define AUDIO_TX_SEQ_SIZE    1      /* 序号字段1字节 */

/* 控制帧前缀 */
static const uint8_t CONTROL_FRAME_PREFIX[2] = {0xFF, 0xFF};

/* 呼叫状态 */
typedef enum {
    CALL_STATE_IDLE = 0,
    CALL_STATE_RINGING,
    CALL_STATE_CONNECTING,
    CALL_STATE_ACTIVE,
    CALL_STATE_ENDING
} call_state_t;

/* 控制帧类型 */
typedef enum {
    FRAME_KIND_UNKNOWN = 0,
    FRAME_KIND_CALL_START,
    FRAME_KIND_CALL_END,
    FRAME_KIND_CALL_ACK,
    FRAME_KIND_ANSWER,
    FRAME_KIND_HANGUP,
    FRAME_KIND_UNLOCK
} frame_kind_t;

/* 解析控制帧 */
frame_kind_t door_parse_control_frame(const uint8_t *data, size_t len);

/* 构建控制命令 (返回帧总长度, 0=失败) */
size_t door_build_command(frame_kind_t kind, uint8_t *out, size_t out_size);

/* 构建上行音频包 (20字节头 + μ-law数据) */
void door_build_audio_tx_packet(uint8_t *packet, const uint8_t *ulaw_data,
                                size_t ulaw_len, uint8_t sequence);

#endif /* DOOR_PROTOCOL_H */
