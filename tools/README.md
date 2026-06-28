# 901 双向协议采集

必须把电脑接到交换机镜像口或真正的网络 TAP。普通旁路接入只看见广播和部分
下行流量时，不能据此推导接听、挂断、开门或麦克风上行报文。

1. 列出抓包接口：

   ```powershell
   python tools/capture_901.py --list
   ```

2. 启动采集（把 `4` 换成实际接口编号）：

   ```powershell
   python tools/capture_901.py --interface 4
   ```

3. 每次实际按键时，在采集窗口输入对应动作：`ring`、`answer`、`unlock`、
   `hangup`、`monitor_start`、`monitor_stop`、`tone_start`、`tone_stop`。

4. 下列实验各做三次，并分别保存抓包：

   - 呼叫901但不接听，等待超时。
   - 呼叫、接听、通话、挂断，不开门。
   - 呼叫、接听、开门、挂断。
   - 主动监视、停止监视。
   - 空闲状态直接开门。
   - 双向播放已知语音或 1 kHz 测试音。

5. 运行分析：

   ```powershell
   python tools/analyze_901.py captures/901_bidirectional_时间.pcapng
   ```

只有报告中 `bidirectional` 和 `usable_for_command_inference` 都为 `true`，才进入
字段比对。工具不会自动写入或启用开门命令。
