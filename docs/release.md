# 发布说明草稿：0.1.0-rc.1

豆包 Windows 输入法 0.9.0.0 的官方键盘引擎现在可以通过本项目向 Fcitx 5
提供预编辑、候选词和中文提交。官方设置程序可以在独立 Wine Mono 环境运行，
关闭后将键盘选项合并到引擎配置。

这是供愿意自行构建和反馈的 Linux 用户试用的源码预发布版本。
可选语音组件包含录音协调和 Fcitx 提交保护，ASR 适配器由用户另外提供。

附件为 `doubao-ime-linux-0.1.0-rc.1.tar.gz` 和 `SHA256SUMS`。
压缩包仅包含明确列出的源码与文档，不包含官方组件、运行环境、词库、字体、
凭据、录音或开发机器日志。

使用前阅读 [README](../README.md)、[验证记录](validation.md) 和 [设置限制](settings.md)。
当前验证平台为 Arch x86_64 + Fcitx 5.1.22 + Wine 11.17；固定 RPC ABI 可能随官方升级失效。
完整 Windows 功能对等、其他发行版即装即用及长期云端 ASR 可用性不在本次承诺内。

## 本地维护者检查

```sh
python3 scripts/package.py --check
python3 scripts/package.py
cd dist
sha256sum -c SHA256SUMS
```

`RELEASE_FILES.txt` 是发布内容的唯一清单。打包器拒绝二进制、符号链接、
个人绝对路径和非项目内容；新源码必须先加入清单。压缩包使用固定元数据，
相同源码生成相同校验和。

创建 GitHub 仓库、推送和上传 Release 属于后续发布步骤，本地准备工具不自动执行。
