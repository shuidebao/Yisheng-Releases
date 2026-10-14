from __future__ import annotations

import audioop
import io
import logging
import queue
import threading
import wave
from dataclasses import asdict, dataclass

from .speech_chunker import SAMPLE_RATE, SpeechChunker


LOGGER = logging.getLogger(__name__)


class SystemAudioError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoopbackDevice:
    index: int
    name: str
    channels: int
    sample_rate: int
    default: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AudioChunk:
    wav: bytes
    duration: float
    level: float
    sequence: int = 0
    continuation: bool = False
    started_at: float = 0.0
    ended_at: float = 0.0


class SystemAudioManager:
    """Capture the Windows output mix through a WASAPI loopback device."""

    START_TIMEOUT = 10.0

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._listed_devices: list[LoopbackDevice] = []
        self._thread: threading.Thread | None = None
        self._chunks: queue.Queue[AudioChunk] = queue.Queue(maxsize=2)
        self._device: LoopbackDevice | None = None
        self._chunk_seconds = 8.0
        self._overlap_seconds = 0.6
        self._sequence = 0
        self._dropped_chunks = 0
        self._level = 0.0
        self._error: str | None = None

    @staticmethod
    def _pyaudio_module():
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise SystemAudioError("电脑声音组件尚未安装，请重新运行 setup.cmd。") from exc
        return pyaudio

    def devices(self) -> list[LoopbackDevice]:
        pyaudio = self._pyaudio_module()
        audio = None
        try:
            audio = pyaudio.PyAudio()
            devices = self._enumerate_devices(audio)
            with self._lock:
                self._listed_devices = devices
            return devices
        except (OSError, LookupError, TypeError, ValueError) as exc:
            raise SystemAudioError(f"无法读取 Windows 输出设备：{exc}") from exc
        finally:
            if audio is not None:
                audio.terminate()

    @staticmethod
    def _enumerate_devices(audio) -> list[LoopbackDevice]:
        default_index = None
        try:
            default_index = int(audio.get_default_wasapi_loopback()["index"])
        except (OSError, LookupError, TypeError, ValueError):
            pass
        devices = []
        for item in audio.get_loopback_device_info_generator():
            channels = int(item.get("maxInputChannels", 0))
            sample_rate = int(float(item.get("defaultSampleRate", 0)))
            if channels <= 0 or sample_rate <= 0:
                continue
            devices.append(LoopbackDevice(
                index=int(item["index"]),
                name=str(item["name"]).removesuffix(" [Loopback]"),
                channels=min(2, channels), sample_rate=sample_rate,
                default=int(item["index"]) == default_index,
            ))
        return sorted(devices, key=lambda item: (not item.default, item.name.casefold()))

    @staticmethod
    def _select_device(devices: list[LoopbackDevice], name: str | None) -> LoopbackDevice:
        if name is not None:
            matches = [item for item in devices if item.name == name]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise SystemAudioError("有多个同名电脑声音设备，请将所需设备设为 Windows 默认输出，并在译声选择自动跟随默认设备。")
            raise SystemAudioError("所选电脑声音设备已断开或名称已变化，请连接设备后在设置中重新选择。")
        selected = next((item for item in devices if item.default), None)
        if selected is not None:
            return selected
        raise SystemAudioError("没有可用的 Windows 默认声音输出，请连接耳机或扬声器，或在设置中明确选择电脑声音设备。")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._ready.is_set()
                    and not self._stop.is_set() and not self._error)

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "device": self._device.to_dict() if self._device else None,
                "chunk_seconds": self._chunk_seconds,
                "overlap_seconds": self._overlap_seconds,
                "queued_chunks": self._chunks.qsize(),
                "dropped_chunks": self._dropped_chunks,
                "level": round(self._level, 3),
                "error": self._error,
            }

    def start(self, device_index: int | None = None, chunk_seconds: float = 8.0,
              device_name: str | None = None) -> dict:
        with self._lock:
            if self.running:
                return self.status()
            if self._thread and self._thread.is_alive():
                raise SystemAudioError("电脑声音仍在启动或停止，请稍后重试。")
            # A PortAudio index belongs to an enumeration, not to a physical
            # device. Legacy callers may refer only to our last listed snapshot.
            if device_name is None and device_index is not None:
                listed = next((item for item in self._listed_devices if item.index == device_index), None)
                if listed is None:
                    raise SystemAudioError("电脑声音设备列表已变化，请在设置中重新选择设备。")
                device_name = listed.name

            self._drain_chunks()
            self._device = None
            self._chunk_seconds = min(8.0, max(3.0, float(chunk_seconds)))
            self._sequence = 0
            self._dropped_chunks = 0
            self._level = 0.0
            self._error = None
            self._stop.clear()
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._capture_loop,
                args=(device_name,),
                name="yisheng-system-audio",
                daemon=True,
            )
            self._thread.start()

        # Do not report success until the worker actually opens its stream.
        if not self._ready.wait(self.START_TIMEOUT):
            self._stop.set()
            raise SystemAudioError("电脑声音设备启动超时，请确认耳机或扬声器可用后重试；无需重新安装翻译模型。")
        with self._lock:
            if self._error:
                raise SystemAudioError(self._error)
            if not self.running:
                raise SystemAudioError("电脑声音启动已取消或设备已断开，请重新开始同传。")
            return self.status()

    def stop(self, timeout: float = 3.0) -> dict:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        with self._lock:
            if not thread or not thread.is_alive():
                self._thread = None
            self._level = 0.0
        return self.status()

    def get_chunk(self, timeout: float = 5.0) -> AudioChunk | None:
        try:
            return self._chunks.get(timeout=max(0.05, min(10.0, timeout)))
        except queue.Empty:
            if self._error:
                raise SystemAudioError(self._error)
            return None

    def _capture_loop(self, device_name: str | None = None) -> None:
        audio = None
        stream = None
        frames_per_buffer = 1024
        resample_state = None

        def emit(chunks):
            for chunk in chunks:
                self._sequence += 1
                self._enqueue(AudioChunk(
                    wav=self._encode_wav([chunk.pcm], 1, SAMPLE_RATE),
                    duration=len(chunk.pcm) / (2 * SAMPLE_RATE),
                    level=min(1.0, audioop.rms(chunk.pcm, 2) / 6000.0),
                    sequence=self._sequence,
                    continuation=chunk.continuation,
                    started_at=chunk.started_at,
                    ended_at=chunk.ended_at,
                ))

        try:
            pyaudio = self._pyaudio_module()
            chunker = SpeechChunker(self._chunk_seconds, self._overlap_seconds)
            for attempt in range(2):
                if self._stop.is_set():
                    return
                audio = pyaudio.PyAudio()
                # Enumerate and open in the SAME PortAudio lifetime/thread.
                device = self._select_device(self._enumerate_devices(audio), device_name)
                self._device = device
                try:
                    stream = audio.open(
                        format=pyaudio.paInt16, channels=device.channels,
                        rate=device.sample_rate, input=True,
                        input_device_index=device.index, frames_per_buffer=frames_per_buffer,
                    )
                    break
                except OSError as exc:
                    if attempt or exc.errno not in (-9996, -9985):
                        raise
                    LOGGER.warning("WASAPI device changed while opening; re-enumerating once: %s", exc)
                    audio.terminate()
                    audio = None
                    if self._stop.wait(.1):
                        return
            if self._stop.is_set():
                return
            LOGGER.info("WASAPI capture ready: index=%s name=%r channels=%s rate=%s",
                        device.index, device.name, device.channels, device.sample_rate)
            self._ready.set()
            while not self._stop.is_set():
                data = stream.read(frames_per_buffer, exception_on_overflow=False)
                rms = audioop.rms(data, 2)
                self._level = min(1.0, rms / 6000.0)
                if device.channels == 2:
                    data = audioop.tomono(data, 2, .5, .5)
                data, resample_state = audioop.ratecv(
                    data, 2, 1, device.sample_rate, SAMPLE_RATE, resample_state,
                )
                emit(chunker.feed(data))
            # Flush the last spoken words before the frontend drains the queue.
            emit(chunker.finish())
        except Exception as exc:
            if isinstance(exc, SystemAudioError):
                self._error = str(exc)
            elif isinstance(exc, OSError) and exc.errno in (-9996, -9985):
                self._error = "电脑声音设备无效或已断开，请连接耳机或扬声器，在设置中重新选择电脑声音设备后重试（错误 %s）；无需重新安装翻译模型。" % exc.errno
            else:
                self._error = f"电脑声音捕获失败：{exc}"
            LOGGER.exception("WASAPI loopback capture failed")
        finally:
            if stream is not None:
                for close in (stream.stop_stream, stream.close):
                    try:
                        close()
                    except Exception:
                        LOGGER.exception("WASAPI stream cleanup failed")
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    LOGGER.exception("WASAPI termination failed")
            self._stop.set()
            self._ready.set()

    def _enqueue(self, chunk: AudioChunk) -> None:
        try:
            self._chunks.put_nowait(chunk)
        except queue.Full:
            try:
                self._chunks.get_nowait()
                self._dropped_chunks += 1
            except queue.Empty:
                pass
            self._chunks.put_nowait(chunk)

    def _drain_chunks(self) -> None:
        while True:
            try:
                self._chunks.get_nowait()
            except queue.Empty:
                return

    @staticmethod
    def _encode_wav(frames: list[bytes], channels: int, sample_rate: int) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"".join(frames))
        return output.getvalue()
