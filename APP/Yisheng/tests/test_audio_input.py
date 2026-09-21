from __future__ import annotations

import io
import struct
import sys
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

from app.audio_input import prepare_audio_input


def pcm_wav(samples=(-32768, -1, 0, 1, 32767)):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return stream.getvalue()


def replace_field(media, offset, format_string, value):
    changed = bytearray(media)
    struct.pack_into(format_string, changed, offset, value)
    return bytes(changed)


class AudioInputTests(unittest.TestCase):
    def assert_decoder_fallback(self, media):
        # Unsupported formats must not need NumPy or alter/consume the upload.
        with patch.dict(sys.modules, {"numpy": None}):
            prepared = prepare_audio_input(media)
        self.assertIsInstance(prepared, io.BytesIO)
        self.assertEqual(prepared.tell(), 0)
        self.assertEqual(prepared.read(), media)

    def test_existing_path_interface_is_preserved_without_opening_file(self):
        path = Path("not-created") / "audio sample.wav"
        with patch.dict(sys.modules, {"numpy": None}):
            self.assertEqual(prepare_audio_input(path), str(path))

    def test_capture_wav_dispatches_to_little_endian_float32_normalization(self):
        media = pcm_wav()
        normalized = object()
        float_samples = Mock()
        float_samples.__truediv__ = Mock(return_value=normalized)
        integer_samples = Mock()
        integer_samples.astype.return_value = float_samples
        numpy_stub = types.SimpleNamespace(
            float32=object(), frombuffer=Mock(return_value=integer_samples)
        )
        with patch.dict(sys.modules, {"numpy": numpy_stub}):
            self.assertIs(prepare_audio_input(media), normalized)
        numpy_stub.frombuffer.assert_called_once_with(media, dtype="<i2", offset=44)
        integer_samples.astype.assert_called_once_with(numpy_stub.float32)
        float_samples.__truediv__.assert_called_once_with(32768.0)

    def test_all_pcm16_values_are_preserved_in_float32_without_clipping(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy is not installed in the source-only test environment")
        samples = tuple(range(-32768, 32768))
        media = pcm_wav(samples)
        prepared = prepare_audio_input(media)
        self.assertIsInstance(prepared, np.ndarray)
        self.assertEqual(prepared.dtype, np.dtype("float32"))
        self.assertEqual(prepared.shape, (65536,))
        # Each PCM16 value divided by 2**15 is exactly representable in float32.
        self.assertEqual(prepared.tolist(), [sample / 32768.0 for sample in samples])
        self.assertEqual(float(prepared.min()), -1.0)
        self.assertEqual(float(prepared.max()), 32767 / 32768.0)
        self.assertEqual(media, pcm_wav(samples))

    def test_empty_and_every_short_header_fall_back_without_unpack_errors(self):
        media = pcm_wav()
        for length in range(45):
            with self.subTest(length=length):
                self.assert_decoder_fallback(media[:length])
        self.assert_decoder_fallback(pcm_wav(()))

    def test_non_wav_and_invalid_chunk_markers_fall_back(self):
        self.assert_decoder_fallback(b"\x1aE\xdf\xa3" + b"WebM upload" * 5)
        media = pcm_wav()
        for offset, replacement in ((0, b"RIFX"), (8, b"AVI "), (12, b"JUNK"), (36, b"JUNK")):
            with self.subTest(offset=offset):
                self.assert_decoder_fallback(media[:offset] + replacement + media[offset + 4:])

    def test_other_wave_formats_use_normal_decoder(self):
        media = pcm_wav()
        variants = (
            ("extended fmt size", 16, "<I", 18),
            ("non-PCM codec", 20, "<H", 3),
            ("extensible codec", 20, "<H", 65534),
            ("stereo", 22, "<H", 2),
            ("48 kHz", 24, "<I", 48000),
            ("wrong byte rate", 28, "<I", 64000),
            ("wrong block alignment", 32, "<H", 4),
            ("8-bit samples", 34, "<H", 8),
            ("24-bit samples", 34, "<H", 24),
            ("32-bit samples", 34, "<H", 32),
        )
        for name, offset, format_string, value in variants:
            with self.subTest(format=name):
                self.assert_decoder_fallback(replace_field(media, offset, format_string, value))

    def test_riff_and_data_lengths_must_both_match_complete_upload(self):
        media = pcm_wav()
        for offset, size in ((4, len(media) - 8), (40, len(media) - 44)):
            for changed_size in (0, size - 2, size + 2, 0xFFFFFFFF):
                with self.subTest(offset=offset, size=changed_size):
                    self.assert_decoder_fallback(replace_field(media, offset, "<I", changed_size))

    def test_odd_truncated_and_trailing_samples_are_not_fast_pathed(self):
        media = pcm_wav()
        for upload in (media[:-1], media[:-2], media + b"x", media + b"xy"):
            with self.subTest(length=len(upload)):
                self.assert_decoder_fallback(upload)
        # Even with self-consistent lengths, PCM16 cannot contain a half-sample.
        odd = replace_field(media[:-1], 4, "<I", len(media) - 9)
        odd = replace_field(odd, 40, "<I", len(odd) - 44)
        self.assert_decoder_fallback(odd)

    def test_metadata_and_extended_fmt_chunks_keep_complete_bytes(self):
        media = pcm_wav()
        junk = b"JUNK" + struct.pack("<I", 4) + b"meta"
        before_data = media[:36] + junk + media[36:]
        before_data = replace_field(before_data, 4, "<I", len(before_data) - 8)
        self.assert_decoder_fallback(before_data)

        after_data = media + junk
        after_data = replace_field(after_data, 4, "<I", len(after_data) - 8)
        self.assert_decoder_fallback(after_data)

        extended_fmt = media[:36] + b"\0\0" + media[36:]
        extended_fmt = replace_field(extended_fmt, 16, "<I", 18)
        extended_fmt = replace_field(extended_fmt, 4, "<I", len(extended_fmt) - 8)
        self.assert_decoder_fallback(extended_fmt)


if __name__ == "__main__":
    unittest.main()
