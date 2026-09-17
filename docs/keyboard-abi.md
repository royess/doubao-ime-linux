# 本机确认的豆包 0.9.0.0 RPC 接口

这是从本地官方二进制调用点及实际输入测试得出的接口记录，不是公开稳定 API。

| 文件 | SHA-256 |
| --- | --- |
| `rpc.dll` | `a3ead1a55850257bac01a878c899f42291a1f41bd2b834e0caa5c5b66a674e02` |
| `tsf-oime-core.dll` | `77d58bfc5bbc9016ee58135967603fbab19a30e79a1c338bce6a2df62ce60a83` |

所有 `RpcPipe_*` 函数第一个参数是管道路径字符串 `\\.\pipe\ObricIme\oime-server`，不是 `CreateRpcClient()` 返回的 C++ 对象。

```c
void RpcPipe_EnsureServerRunning(void);
void RpcPipe_FocusIn(const char *endpoint, const char *host_application);
void RpcPipe_FocusOut(const char *endpoint);
int RpcPipe_KeyDown(const char *endpoint, unsigned packed_key,
                    uint64_t timestamp_us, const char *host_application);
int RpcPipe_KeyUp(const char *endpoint, unsigned packed_key);
int RpcPipe_GetCompTextUtf8(const char *endpoint, char *text, int capacity, int *cursor);
int RpcPipe_GetCommitTextUtf8(const char *endpoint, char *text, int capacity);
int RpcPipe_GetCandidateListUtf8(const char *endpoint, char *text, int capacity,
                                int *selected, int *has_previous, int *has_next);
void RpcPipe_SetUIElementShowState(const char *endpoint, int show);
```

`tsf-oime-core.dll` 的 RVA `0x7c10` 将 Windows VK 与状态位合并：Ctrl `0x0400`、Alt `0x0800`、Shift `0x1000`、CapsLock `0x2000`。左右修饰键先转换为各自的 VK（Shift 为 `0xa0/0xa1`）。CapsLock 按下时翻转 `0x2000`，使事件携带切换后的状态。

RVA `0xe8d3` 起用 `GetTickCount64() * 1000` 生成微秒时间；RVA `0xdaf0` 从当前模块路径取得宿主程序名，供后续按键调用使用。**第三个参数不是 Windows lParam，第四个参数不是输入字符。** 只传普通字母键码能输入拼音，但会丢失 Shift 大写及组合标点，因此初版冒烟测试不足以验证这些参数。

本桥接从 Fcitx `rawKey()` 取得布局转换后的键及状态，转换为上述编码；Ctrl/Alt/Super 应用快捷键由应用处理。RPC 宿主使用自己的单调时间，并以 `fcitx5-doubao.exe` 标识宿主。普通中文标点由官方引擎转换。

候选列表是换行分隔的 UTF-8 字符串，函数返回文本长度，不是候选数量。分段选词可能仅改变预编辑，如 `ni'hao` → `尼hao`；不能假定每次选词都会提交整句。当前宿主通过方向键移动官方选中项后按空格选择，保留引擎的分段行为。

观察到 KeyDown 返回 0 为未消费、1 为已处理、3 为发生提交；负值按错误处理。提交文本通过 `GetCommitTextUtf8()` 取出，随后应为空，避免重复提交。
