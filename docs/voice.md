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

可以在桌面快捷键设置中绑定 `doubao-voice toggle` 与 `doubao-voice cancel`。
`doubao-voice status` 查看状态。

## 右 Alt 快捷键

可选的 Fcitx 按键处理对应官方 Windows 客户端的两种默认绑定：

- 长按 **右 Alt** 开始说话，松开结束录音并提交；短按不启动。
- **右 Alt + 空格** 开始持续录音，再按一次结束；按住说话时按空格可转为持续录音。
- **Esc**、切换输入框或录音中打字会取消。密码框和存在未提交拼音时不启动按键听写。

先释放其他插件占用的右 Alt，然后在 Fcitx 配置工具的「豆包语音提交」附加组件中
启用右 Alt，或编辑 `~/.config/fcitx5/conf/doubaovoice.conf`：

```ini
EnableHotkeys=True
HoldThresholdMs=250
```

首次安装新模块后重启 Fcitx；之后修改这个配置可执行
`busctl --user call org.fcitx.Fcitx5 /controller org.fcitx.Fcitx.Controller1 ReloadAddonConfig s doubaovoice`。
快捷键默认关闭，安装脚本不自动修改其他插件。它在普通 Fcitx 输入框中生效，
可搭配豆包、英文键盘或其他输入法，不依赖桌面全局按键监听。

开始后先录音，在云端连接建立前只缓存在进程内存中，最多 20 秒；连接成功才发送。
连接期间松开右 Alt 会结束采集，并在连接就绪后发送已经采集的短句；取消则丢弃未发送的缓存。

## 范围

- 录音使用 `parec`；可通过服务环境 `DOUBAO_AUDIO_SOURCE` 指定麦克风。
- 最长录音 120 秒。密码/敏感输入框不发放提交许可；文字不会通过剪贴板粘贴。
- 仅接受匹配的分段最终结果和整句结束确认；取消、断线或旧会话不提交。
- Fcitx 的提交许可绑定调用进程和当前输入框，只能使用一次。
- 当前只接收单行文本；控制字符、多行文本会被拒绝。
- 官方设置里的 Windows 语音热键、麦克风和标点选项不控制这个 Linux 录音器；上述绑定由 Fcitx 配置管理。

默认遵守用户的代理配置。如果出现特定域名握手失败，可自行设置 `asr_no_proxy`，
例如 `log.snssdk.com,is.snssdk.com,frontier-audio-ime-ws.doubao.com`；此设置只影响适配器子进程。
不要把携带签名、设备 ID、令牌的日志直接提交到 issue。

`asr_ipv4_only` 默认是 `false`，省略时也不会限制地址族，沿用系统的 IPv4/IPv6 选择。
若本机到语音入口的 IPv6 不通、IPv4 正常，可在 `config.local.json` 设置
`"asr_ipv4_only": true`。这只让适配器子进程用 IPv4 连接豆包语音 WebSocket
域名，避免先等待 IPv6 超时；不会修改系统网络或固定服务器 IP。
改回 `false` 或删除该项即可恢复默认行为；配置在下一次听写启动适配器时生效。
松开右 Alt 后请等“已输入”提示再打字，识别完成前打字会取消本次提交。
