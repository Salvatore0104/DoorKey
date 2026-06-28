# Haier HR-6107 Home Assistant 集成

将 `custom_components/haier_hr6107` 复制到 Home Assistant 配置目录的
`custom_components` 后重启，在“设备与服务”中添加 **Haier HR-6107**。

服务地址应填写运行软件终端的家庭网地址，例如 `http://192.168.1.20:8088`；
令牌取自软件终端目录中的 `.hr6107_api_token`。

集成提供：501 来电二元传感器、通话/服务状态传感器，以及经过认证并有
10 秒限频的固定门口机开门按钮。在协议配置尚未验证时，开门按钮会显示为
不可用。

完整视频与双向对讲使用后端网页。可在 Lovelace 添加网页卡片：

```yaml
type: iframe
url: http://192.168.1.20:8088/
aspect_ratio: 70%
```

后端不接受目标 IP、房号或原始十六进制报文参数。
