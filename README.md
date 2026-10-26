# AstrBot GSV–RVC Voice

让小肥鱼把文字念出来：调用本地 **GPT-SoVITS → RVC** 网关，生成角色音色 WAV，再由 AstrBot 的消息平台适配器发送语音。

## 安装

在 AstrBot 插件管理中使用仓库地址安装：

https://github.com/InariNGT-Ofiicial/astrbot_plugin_gsv_rvc_voice

**先部署网关和模型服务**：[gsv-rvc-voice-bridge](https://github.com/InariNGT-Ofiicial/gsv-rvc-voice-bridge)。仅安装本插件不会下载模型或自动建立推理环境。

## 使用

- `/voice 你好，很高兴见到你。`：朗读指定文本，保留文本中的空格。
- `/语音 今天也辛苦啦。`：同一指令的别名。
- `/voice_health`：检查网关及上游服务。

指令前缀随 AstrBot 配置变化。语音生成失败时回复错误提示；正在生成时提示稍后重试，不堆积并行任务。

| 配置 | 默认 | 含义 |
|---|---|---|
| `gateway_url` | `http://127.0.0.1:8790` | 网关根地址，不加 `/v1` |
| `max_chars` | 80 | 单条字数上限，不应超过网关限制 |
| `timeout_sec` | 120 | HTTP 合成超时 |
| `session_whitelist` | `[]` | 会话 UMO 白名单；空允许所有会话，用 `/sid` 查询 |

音色由网关连接的 RVC 模型决定；不通过聊天指令任意加载模型。收到的 WAV 保存在 AstrBot 临时目录的 `gsv_rvc_voice` 子目录中，下一次生成时清理本插件超过 24 小时的旧文件。

## 部署边界

插件只提供按指令合成，不自动替换 LLM 回复，不包含语音识别、实时通话或翻唱。需要自动 TTS 时可直接使用 AstrBot 内置 OpenAI TTS provider，API Base 指向网关 `/v1`，见主仓说明。

插件通过 HTTP 下载音频字节，不要求与网关共享音频目录。Docker 中 `127.0.0.1` 指容器自己，应填写容器可达的受保护网关地址。网关本身没有认证，不直接暴露公网。

Record 消息最终能否发送及呈现为语音条，取决于平台适配器。已做模拟事件与真实本地 HTTP 测试，**尚未完成真实 AstrBot / QQ 收发验收**。公开 RVC 模型质量可能不佳，仅作演示。

## 开发与许可

源代码维护于主仓 `packages/astrbot_plugin_gsv_rvc_voice`，本仓为可安装同步副本。依据 [AstrBot 插件文档](https://docs.astrbot.app/dev/star/plugin-new.html) 和 [Record 接口](https://docs.astrbot.app/dev/star/guides/send-message.html) 实现。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s test
```

MIT。模型权重和参考音频不随仓库分发。
