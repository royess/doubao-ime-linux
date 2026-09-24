# 0.1.0-rc.1 验证记录

日期：2026-09-17。以下是本次独立源码预发布目录的实际验证结果。

环境为 Arch Linux x86_64、Fcitx 5 **5.1.22**、发行版原始 Wine **11.17**、
Wine Mono **11.3.0**、豆包 Windows 输入法 **0.9.0.0**。
Windows 宿主使用 Clang **22.1.8**、LLD 和标准 MinGW-w64 **14.0.0** 头文件及库编译。
所有 Wine prefix 都由源码中的准备工具重新初始化，没有复制既有用户配置。
设置字体仅为 Noto Sans CJK SC。

| 检查 | 结果 |
|---|---|
| 原生 Fcitx 键盘与独立语音提交模块 | 编译通过 |
| Windows RPC 宿主与设置检查工具 | 标准 MinGW 接口编译通过 |
| 单元测试 | 21 项通过：语音结果/取消、配置合并/冲突、服务归属、安装保护及源码包校验 |
| 官方键盘 RPC | 11 项通过：预编辑、候选词、首选/非首选、分段选词、退格、清空、焦点重置及异常客户端 |
| 私有 GTK/Fcitx 输入 | 15 项通过：真实键盘输入及语音提交端点的焦点、调用方、敏感框、控制字符和一次性校验 |
| 官方引擎键盘选项 | 全拼、繁简、小鹤、自然码、86 五笔共 5 项通过 |
| 官方设置窗口 | 干净环境中显示可读中文；正常关闭，活动键盘配置保持不变 |
| 暂存安装/卸载 | 12 个入口及插件文件；带空格路径、systemd 单元语法、完整移除和无关文件保留均通过 |

表情开关仍有已知问题：关闭后「你好」候选仍可能包含表情，未计为通过。

本次没有进行真人录音或连接外部 ASR 服务的完整听写回归；语音集成检查验证的是
真实 Fcitx 提交端点和协调逻辑，不代表外部云端接口当前可用。
Windows 设置中的每一个选项、账号同步、长时稳定性及其他发行版尚未全部验证。
GTK 集成测试使用私有 X11 显示；本预发布版本未替换当前桌面插件做新的 Wayland 回归。
首轮 GitHub Actions 构建与单元检查[已通过](https://github.com/royess/doubao-ime-linux/actions/runs/35185628495)。
现有 CI 扩展了 GCC/Clang、仅键盘构建、模拟引擎下的真实 Fcitx/GTK 测试、暂存安装与可重复打包；
最新状态见 [GitHub Actions](https://github.com/royess/doubao-ime-linux/actions/workflows/ci.yml)。
模拟引擎只提供固定候选词，不能替代上表中的官方引擎实测。

## 后续右 Alt 与图标验证（2026-09-17）

- 29 项单元测试通过，包括连接建立前的音频缓存、提前松键、取消清空、容量上限及子进程回收。
- 模拟键盘和录音会话的真实 Fcitx/GTK 集成共 37 项通过，包括右 Alt 长按/短按、松开提交、
  右 Alt + 空格持续录音、Esc/焦点取消、密码框/拼音预编辑保护及运行中停用热键。
- 带独立图标的暂存安装/卸载覆盖 13 个文件。
- 上述新增测试全部纳入 GitHub Actions 的 GCC/Clang 矩阵：单元测试使用 `test_*.py`
  自动发现，快捷键测试位于现有 `integration_fcitx.py --mock-engine` 入口。

此处模拟录音会话和 ASR 协议边界，没有使用真实麦克风或云端识别服务。
官方引擎、官方设置窗口的手动验证仍需要另行准备 Wine 和官方组件；它们不是托管 CI 中的在线测试。

## 实时预览验证（2026-09-24）

- 40 项单元测试通过，包括流式中间结果、修订去重、取消后的旧事件、识别错误后的清理，
  以及仅有 partial 时禁止提交的规则。
- 私有 Xvfb / D-Bus 的真实 Fcitx / GTK 集成通过：预览不写入正文、修订替换、
  等待最终结果时保留预览、一次性提交、焦点/按键/服务断开清理，及两种右 Alt 操作。
- 本机安装更新后的语音模块，在 niri Wayland 的 GTK 输入框和 Alacritty 中验证
  预览修订、最终落字和取消。Alacritty 的 Wayland 协议收到预编辑更新，终端 PTY
  只收到一次最终文字；临时预览没有作为键盘输入写入终端。
- 真人麦克风与云端识别的 Alacritty 测试由用户确认：说话时显示文字，最终文字正常。
- 按正常速度发送固定中文音频时，服务端 partial 更新间隔中位数约 0.64 秒，
  表现为文字分批出现。独立测试将 `cell_compress_rate` 从 8 改为 4 后间隔无明显变化，
  未将此实验参数作为配置或默认值发布。

Wayland 与真人验证是本机实测，不属于托管 CI；服务端更新频率和识别质量仍受外部服务影响。

## 复现命令

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/doctor.py
python3 scripts/headless.py --prefix keyboard -- python3 tests/integration_keyboard.py
python3 scripts/headless.py --prefix keyboard -- dbus-run-session -- python3 tests/integration_fcitx.py
python3 scripts/headless.py --prefix settings -- python3 tests/integration_settings_engine.py
python3 scripts/headless.py --prefix none -- python3 tests/integration_settings_ui.py
python3 tests/integration_install.py
python3 scripts/headless.py --prefix none -- dbus-run-session -- python3 tests/integration_fcitx.py --mock-engine
python3 scripts/package.py --check
python3 scripts/package.py
python3 scripts/check_package.py --rebuild
```

运行集成测试前停止**这个源码目录**的键盘服务、关闭设置窗口。测试有 prefix 排他锁，
不得通过删除锁文件绕过。原始日志和截图保存在 `work/`，不进入发布包。
通过其他机器或发行版验证后，请补充环境和对应结果，不要据此扩大本表的现有结论。
