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
| 单元测试 | 19 项通过：语音结果/取消、配置合并/冲突、服务归属、安装保护 |
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
GitHub Actions 已提供构建检查配置，但尚未在 GitHub 上执行。

## 复现命令

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/doctor.py
python3 scripts/headless.py --prefix keyboard -- python3 tests/integration_keyboard.py
python3 scripts/headless.py --prefix keyboard -- dbus-run-session -- python3 tests/integration_fcitx.py
python3 scripts/headless.py --prefix settings -- python3 tests/integration_settings_engine.py
python3 scripts/headless.py --prefix none -- python3 tests/integration_settings_ui.py
python3 tests/integration_install.py
python3 scripts/package.py --check
```

运行集成测试前停止**这个源码目录**的键盘服务、关闭设置窗口。测试有 prefix 排他锁，
不得通过删除锁文件绕过。原始日志和截图保存在 `work/`，不进入发布包。
通过其他机器或发行版验证后，请补充环境和对应结果，不要据此扩大本表的现有结论。
