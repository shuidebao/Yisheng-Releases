from __future__ import annotations

import audioop
import io
import logging
import queue
import threading
import time
import wave
from dataclasses import asdict, dataclass


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


class SystemAudioManager:
    """Capture the Windows output mix through a WASAPI loopback device."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._chunks: queue.Queue[AudioChunk] = queue.Queue(maxsize=4)
        self._device: LoopbackDevice | None = None
        self._chunk_seconds = 3.6
        self._overlap_seconds = 0.75
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
        audio = pyaudio.PyAudio()
        try:
            default_index: int | None = None
            try:
                default_index = int(audio.get_default_wasapi_loopback()["index"])
            except (OSError, KeyError, TypeError):
                pass
            devices: list[LoopbackDevice] = []
            for item in audio.get_loopback_device_info_generator():
                channels = max(1, min(2, int(item.get("maxInputChannels", 2))))
                devices.append(
                    LoopbackDevice(
                        index=int(item["index"]),
                        name=str(item["name"]).replace(" [Loopback]", ""),
                        channels=channels,
                        sample_rate=int(float(item.get("defaultSampleRate", 48000))),
                        default=int(item["index"]) == default_index,
                    )
                )
            devices.sort(key=lambda item: (not item.default, item.name.casefold()))
            return devices
        except OSError as exc:
            raise SystemAudioError(f"无法读取 Windows 输出设备：{exc}") from exc
        finally:
            audio.terminate()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "device": self._device.to_dict() if self._device else None,
                "chunk_seconds": self._chunk_seconds,
                "overlap_seconds": self._overlap_seconds,
                "queued_chunks": self._chunks.qsize(),
                "level": round(self._level, 3),
                "error": self._error,
            }

    def start(self, device_index: int | None = None, chunk_seconds: float = 3.6) -> dict:
        with self._lock:
            if self.running:
                return self.status()
            devices = self.devices()
            if not devices:
                raise SystemAudioError("没有检测到可用的 Windows 电脑声音设备。")
            selected = next((item for item in devices if item.index == device_index), None)
            if selected is None:
                selected = next((item for item in devices if item.default), devices[0])

            self._drain_chunks()
            self._device = selected
            self._chunk_seconds = min(8.0, max(1.5, float(chunk_seconds)))
            self._level = 0.0
            self._error = None
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="yisheng-system-audio",
                daemon=True,
            )
            self._thread.start()

        # Surface device-open failures to the caller instead of waiting for a poll.
        time.sleep(0.12)
        if self._error:
            raise SystemAudioError(self._error)
        return self.status()

    def stop(self, timeout: float = 3.0) -> dict:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        with self._lock:
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

    def _capture_loop(self) -> None:
        pyaudio = self._pyaudio_module()
        device = self._device
        if device is None:
            self._error = "没有选中电脑声音设备。"
            return

        audio = pyaudio.PyAudio()
        stream = None
        frames_per_buffer = 1024
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=device.channels,
                rate=device.sample_rate,
                input=True,
                input_device_index=device.index,
                frames_per_buffer=frames_per_buffer,
            )
            target_frames = int(device.sample_rate * self._chunk_seconds)
            frames: list[bytes] = []
            frame_count = 0
            peak_rms = 0

            while not self._stop.is_set():
                data = stream.read(frames_per_buffer, exception_on_overflow=False)
                frames.append(data)
                current_frames = len(data) // (2 * device.channels)
                frame_count += current_frames
                rms = audioop.rms(data, 2)
                peak_rms = max(peak_rms, rms)
                self._level = min(1.0, rms / 6000.0)

                if frame_count >= target_frames:
                    raw_frames = b"".join(frames)
                    # Ignore digital silence and low-level loopback noise. Sending
                    # near-silence to Whisper is a major source of repeated-word
                    # hallucinations during pauses in podcasts and videos.
                    if peak_rms >= 48:
                        self._enqueue(
                            AudioChunk(
                                wav=self._encode_wav([raw_frames], device.channels, device.sample_rate),
                                duration=frame_count / device.sample_rate,
                                level=min(1.0, peak_rms / 6000.0),
                            )
                        )
                    # Retain a short tail so words crossing a fixed chunk
                    # boundary are present in the next recognition request.
                    overlap_frames = min(frame_count, int(device.sample_rate * self._overlap_seconds))
                    overlap_bytes = overlap_frames * 2 * device.channels
                    frames = [raw_frames[-overlap_bytes:]] if overlap_bytes else []
                    frame_count = overlap_frames
                    peak_rms = 0
        except Exception as exc:
            self._error = f"电脑声音捕获失败：{exc}"
            LOGGER.exception("WASAPI loopback capture failed")
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except OSError:
                    pass
            audio.terminate()
            self._stop.set()

    def _enqueue(self, chunk: AudioChunk) -> None:
        try:
            self._chunks.put_nowait(chunk)
        except queue.Full:
            try:
                self._chunks.get_nowait()
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
