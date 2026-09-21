from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import Any


def prepare_audio_input(media: Path | bytes) -> Any:
    """Keep uploaded audio in memory; fast-path only our exact PCM WAV format.

    The app's two capture sources already produce mono, 16 kHz signed 16-bit
    samples. Reading these directly avoids redundant PyAV decoding/resampling
    and its full garbage collection, with the same float32 normalization.
    Noncanonical WAV/WebM inputs still use Whisper's normal decoder.
    """
    if not isinstance(media, bytes):
        return str(media)
    if (
        len(media) > 44
        and media[:4] == b"RIFF"
        and media[8:16] == b"WAVEfmt "
        and media[36:40] == b"data"
        and struct.unpack_from("<I", media, 4)[0] == len(media) - 8
        and struct.unpack_from("<IHHIIHH", media, 16)
        == (16, 1, 1, 16000, 32000, 2, 16)
        and struct.unpack_from("<I", media, 40)[0] == len(media) - 44
        and (len(media) - 44) % 2 == 0
    ):
        # Import lazily so desktop startup and dependency-free tests stay light.
        import numpy as np

        return np.frombuffer(media, dtype="<i2", offset=44).astype(np.float32) / 32768.0
    return io.BytesIO(media)
