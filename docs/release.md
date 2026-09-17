# GitHub Release 发布流程

仓库通过版本标签发布源码包。`main` 推送、Pull Request 和手动 CI 运行只执行测试，
不会创建 Release。推送 `v*` 标签时，`.github/workflows/release.yml` 先调用完整 CI，
只有 GCC 与 Clang 两组检查全部通过，才会进入发布步骤。

## 发布内容与检查

发布步骤下载**同一次运行、同一个提交**生成的源码 artifact，重新核对文件内容、
发布清单与 SHA-256，再创建包含两个附件的草稿，上传成功后公开发布：

- `doubao-ime-linux-<版本>.tar.gz`
- `SHA256SUMS`

`-rc` 版本标记为预发布，不作为最新稳定版。`VERSION` 必须与去掉 `v` 的标签完全一致，
且必须存在 `docs/releases/<版本>.md`。流程不会覆盖已经存在的 Release。
版本说明使用完整 GitHub 链接，便于在 Release 页面直接访问对应版本文档。

仅发布桥接源码、文档和测试。官方 EXE/DLL、Wine、字体、词库、凭据及录音不进入 artifact。
普通 CI 和 Release 检查都不依赖官方安装包或云端账号。

## 准备并发布一个版本

1. 更新 `VERSION`、中英文 README、`CHANGELOG.md`、验证记录与对应版本说明。
2. 把新增源码和文档加入 `RELEASE_FILES.txt`，运行本地检查。
3. 提交并推送 `main`，确认 CI 通过。
4. 在该提交创建与 `VERSION` 一致的标签并推送。不要重新指向已发布标签。

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/package.py --check
python3 scripts/package.py
python3 scripts/check_package.py --rebuild

git tag -a v0.1.0-rc.1 -m 'Source preview v0.1.0-rc.1'
git push origin v0.1.0-rc.1
```

随后在 [Release workflow](https://github.com/royess/doubao-ime-linux/actions/workflows/release.yml)
查看测试和发布结果，在 [Releases](https://github.com/royess/doubao-ime-linux/releases) 下载附件。
`docs/releases/0.1.0-rc.1.md` 是首个版本的中英文发布说明。

工作流使用 GitHub 提供的临时 `GITHUB_TOKEN`；只有发布 job 有 `contents: write` 权限，
无需配置个人访问令牌。仓库需要允许 Actions 运行及该 job 申请的内容写入权限。

## 失败处理

CI 失败时不创建 Release。修复源码后发布新的版本标签，不移动已有发布标签。
如果上传中断留下草稿，先检查草稿及附件；修复或移除不完整草稿后才能重试。
已公开的版本不会被流程自动覆盖。

详细机制可参考 [GitHub 可复用工作流](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
与 [GitHub CLI Release 命令](https://cli.github.com/manual/gh_release_create)。
