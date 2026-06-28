# ESP32-S3 HR-6107 门禁终端固件

ESP32-S3 + W5500以太网 + 2.4寸LCD 的嵌入式门禁终端方案。

## 硬件

| 部件 | 型号 |
|------|------|
| MCU | ESP32-S3-WROOM-1-N16R8 (16MB Flash, 8MB Octal PSRAM) |
| 以太网 | W5500 SPI模块 (门禁网 172.30.2.0/24) |
| WiFi | 板载 (家庭HA网) |
| LCD | 2.4寸 SPI TFT ST7789 320x240 |
| 音频功放 | MAX98357A I2S |
| 麦克风 | INMP441 I2S MEMS |
| 继电器 | 3.3V光耦隔离继电器 |

## 开发环境

```bash
# ESP-IDF v5.2+
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3
. ./export.sh

# 编译
cd esp32_firmware/
idf.py set-target esp32s3
idf.py menuconfig    # 确认 PSRAM=on, CPU=240MHz
idf.py build
idf.py -p COM3 flash monitor
```

## 功能实现状态

- [x] TCP 46752 控制协议（来电监听、answer/hangup/unlock）
- [x] G.711 μ-law 编解码
- [x] 上行音频 20 字节头（offset=3, 1字节序号）
- [ ] UDP 46753 音频 I2S 双工
- [ ] UDP 46754 视频 esp_h264 解码
- [ ] LCD SPI 显示
- [ ] W5500 + WiFi 双网卡
- [ ] ESPHome/HA 集成

## 协议参考

详见上级目录的 `protocol_profile.json` 和 `HR-6107_抓包分析与HA接入记录.md`。
