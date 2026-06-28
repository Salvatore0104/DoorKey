/*
 * G.711 μ-law 编解码
 * 查表法实现，约1KB ROM，适合ESP32
 * 参考: ITU-T G.711, ESP32-SIP-Voice项目
 */

#ifndef G711_ULAW_H
#define G711_ULAW_H

#include <stdint.h>
#include <stddef.h>

/* PCM s16le → G.711 μ-law (8kHz → 64kbps) */
uint8_t pcm16_to_ulaw(int16_t sample);

/* G.711 μ-law → PCM s16le */
int16_t ulaw_to_pcm16(uint8_t ulaw);

/* 批量编码: PCM s16le → μ-law */
void pcm16_to_ulaw_buf(const int16_t *pcm, uint8_t *ulaw, size_t samples);

/* 批量解码: μ-law → PCM s16le */
void ulaw_to_pcm16_buf(const uint8_t *ulaw, int16_t *pcm, size_t samples);

#endif /* G711_ULAW_H */
