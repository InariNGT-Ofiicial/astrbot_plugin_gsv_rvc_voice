"""AstrBot command adapter for the local GSV → RVC gateway."""
import asyncio
import io
import time
import uuid
import wave
from pathlib import Path

import aiohttp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path


def command_text(message: str) -> str:
    """Keep spaces in the utterance; the host handles the command prefix."""
    parts = message.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def validate_wav(data: bytes) -> None:
    if not 44 <= len(data) <= 20 * 1024 * 1024:
        raise ValueError("音频大小异常")
    with wave.open(io.BytesIO(data), "rb") as wav:
        if wav.getnframes() < 1 or wav.getframerate() < 8000:
            raise ValueError("网关没有返回有效 WAV")


@register("astrbot_plugin_gsv_rvc_voice", "InariNGT-Ofiicial",
          "通过 GSV + RVC 网关生成角色语音", "0.1.0")
class VoiceBridge(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = config
        self._busy = False

    def allowed(self, event: AstrMessageEvent) -> bool:
        allow = self.cfg.get("session_whitelist", [])
        return not allow or event.unified_msg_origin in allow

    async def synthesize(self, text: str) -> bytes:
        base = self.cfg.get("gateway_url", "http://127.0.0.1:8790").rstrip("/")
        timeout = aiohttp.ClientTimeout(total=int(self.cfg.get("timeout_sec", 120)))
        payload = {"input": text, "model": "gsv-rvc-voice", "voice": "default", "response_format": "wav"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(base + "/v1/audio/speech", json=payload) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"语音网关返回 HTTP {resp.status}")
                chunks, total = [], 0
                async for chunk in resp.content.iter_chunked(65536):
                    total += len(chunk)
                    if total > 20 * 1024 * 1024:
                        raise ValueError("音频超过 20 MiB")
                    chunks.append(chunk)
        data = b"".join(chunks)
        validate_wav(data)
        return data

    def save_audio(self, data: bytes) -> Path:
        folder = Path(get_astrbot_temp_path()) / "gsv_rvc_voice"
        folder.mkdir(parents=True, exist_ok=True)
        # Keep files long enough for platform upload; prune only our stale files.
        for old in folder.glob("voice_*.wav"):
            try:
                if time.time() - old.stat().st_mtime > 86400:
                    old.unlink()
            except OSError:
                pass
        path = folder / f"voice_{uuid.uuid4().hex}.wav"
        path.write_bytes(data)
        return path

    @filter.command("voice", alias={"语音"})
    async def voice(self, event: AstrMessageEvent):
        """/voice 要朗读的文本：生成并回复语音。"""
        if not self.allowed(event):
            yield event.plain_result("当前会话未启用语音。")
            return
        text = command_text(event.message_str)
        if not text:
            yield event.plain_result("用法：/voice 你好，很高兴见到你。")
            return
        if len(text) > int(self.cfg.get("max_chars", 80)):
            yield event.plain_result("文本超过长度限制，请分成短句。")
            return
        if self._busy:
            yield event.plain_result("正在生成上一条语音，请稍后再试。")
            return
        self._busy = True
        try:
            data = await self.synthesize(text)
            path = await asyncio.to_thread(self.save_audio, data)
            yield event.chain_result([Comp.Record(file=str(path), url=str(path))])
        except Exception as exc:
            logger.warning("[gsv-rvc-voice] synthesis failed: %s", type(exc).__name__)
            yield event.plain_result("语音生成失败，请检查本地网关和模型服务。")
        finally:
            self._busy = False

    @filter.command("voice_health")
    async def voice_health(self, event: AstrMessageEvent):
        """检查网关与上游服务，不展示服务器路径。"""
        if not self.allowed(event):
            yield event.plain_result("当前会话未启用语音。")
            return
        base = self.cfg.get("gateway_url", "http://127.0.0.1:8790").rstrip("/")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as session:
                async with session.get(base + "/health") as response:
                    data = await response.json()
                    ok = response.status == 200 and data.get("ok") is True
            yield event.plain_result("语音服务就绪。" if ok else "网关可达，但上游语音服务尚未就绪。")
        except Exception:
            yield event.plain_result("无法连接语音网关，请检查 gateway_url。")
