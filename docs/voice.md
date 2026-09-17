# 可选豆包语音

本项目包含 Linux 录音协调器、结果校验和独立的 Fcitx 提交插件。
ASR 协议来自外部社区适配器；没有把它的代码或设备凭据放进发行包。

可以单独使用 [fcitx5-vinput](https://github.com/xifan2333/fcitx5-vinput) 管理语音，
同时使用本项目的豆包键盘。需要使用这里的语音协调器时，按下述步骤配置。

## 外部适配器

参考适配器是 [vinput-registry 的 doubaoime/streaming](https://github.com/xifan2333/vinput-registry/tree/38e203e328118e5575722d2d4dd74dd736b6c8d8/resources/providers/doubaoime/streaming)，
固定修订 `38e203e328118e5575722d2d4dd74dd736b6c8d8`。
按上游说明取得适配器并满足其依赖，将 `entry.py` 的绝对路径写入
`config.local.json` 的 `asr_entry`。本项目不自动拉取或重新分发该适配器。

适配器通过 stdin/stdout JSONL 传输 16 kHz 单声道 PCM、音频结束及识别结果。
`scripts/provider.py` 校验依赖的接口存在，将设备凭据保存在 `work/private/`，
并关闭失败后自动删除凭据、重复注册设备的行为。首次使用仍可能自动注册设备。
上游协议是非官方接口，服务端或适配器更新可能导致失效。

```sh
# 还未安装时追加 --voice；如已有安装，先按 README 停用服务并卸载入口。
python3 scripts/install.py install --voice --settings
systemctl --user daemon-reload
systemctl --user enable --now doubao-keyboard.service doubao-voice.service
```

在桌面快捷键设置中绑定 `doubao-voice toggle` 与 `doubao-voice cancel`。
快捷键需由用户选择。`doubao-voice status` 查看状态。
第一次触发连接完成后才开始录音，再次触发结束并提交；Esc、切换输入框或录音中打字会取消。

## 范围

- 录音使用 `parec`；可通过服务环境 `DOUBAO_AUDIO_SOURCE` 指定麦克风。
- 最长录音 120 秒。密码/敏感输入框不发放提交许可；文字不会通过剪贴板粘贴。
- 仅接受匹配的分段最终结果和整句结束确认；取消、断线或旧会话不提交。
- Fcitx 的提交许可绑定调用进程和当前输入框，只能使用一次。
- 当前只接收单行文本；控制字符、多行文本会被拒绝。
- 官方设置里的 Windows 语音热键、麦克风和标点选项不控制这个 Linux 录音器。

默认遵守用户的代理配置。如果出现特定域名握手失败，可自行设置 `asr_no_proxy`，
例如 `log.snssdk.com,is.snssdk.com,frontier-audio-ime-ws.doubao.com`；此设置只影响适配器子进程。
不要把携带签名、设备 ID、令牌的日志直接提交到 issue。
