from __future__ import annotations

import io
import types
import threading
import time
import unittest
import wave
from unittest.mock import patch

from app.speech_chunker import SpeechChunk
from app.system_audio import AudioChunk, LoopbackDevice, SystemAudioManager, SystemAudioError


def device(index=1, name="Test output", channels=2, rate=48000):
    return dict(index=index, name=name + " [Loopback]", maxInputChannels=channels, defaultSampleRate=rate)


class FakeAudio:
    """Device indices change between lifetimes, as they can after hotplug."""
    def __init__(self, manager, snapshots, errors=(), delay=0, gate=None):
        self.instances = []
        self.opens = []
        self.reads = 0
        self.closes = 0
        outer = self
        class Audio:
            def __init__(self):
                self.number = len(outer.instances)
                self.items = snapshots[min(self.number, len(snapshots) - 1)]
                self.terminated = False
                outer.instances.append(self)
            def get_default_wasapi_loopback(self):
                if not self.items:
                    raise OSError(-9996, "Invalid device")
                return self.items[0]
            def get_loopback_device_info_generator(self):
                return iter(self.items)
            def open(self, **kwargs):
                assert not self.terminated
                outer.opens.append(kwargs)
                assert kwargs['input_device_index'] in [item['index'] for item in self.items]
                if gate is not None:
                    gate.wait(1)
                if delay:
                    time.sleep(delay)
                if self.number < len(errors) and errors[self.number]:
                    raise errors[self.number]
                return Stream()
            def terminate(self):
                self.terminated = True
        class Stream:
            def read(self, *_args, **_kwargs):
                outer.reads += 1
                manager._stop.wait(.01)
                return b'\0' * 4096
            def stop_stream(self):
                pass
            def close(self):
                outer.closes += 1
        self.module = types.SimpleNamespace(PyAudio=Audio, paInt16=16)


class SilentChunker:
    def __init__(self, *_args):
        pass
    def feed(self, _data):
        return []
    def finish(self):
        return []


class SystemAudioTests(unittest.TestCase):
    def test_bounded_queue_reports_loss_and_keeps_sequence_gaps(self):
        manager = SystemAudioManager()
        for sequence in (1, 2, 3):
            manager._enqueue(AudioChunk(b"pcm", 1, .2, sequence=sequence))
        self.assertEqual(manager.status()["dropped_chunks"], 1)
        self.assertEqual(manager.get_chunk(.05).sequence, 2)
        self.assertEqual(manager.get_chunk(.05).sequence, 3)
        self.assertIsNone(manager.get_chunk(.05))

    def test_capture_flushes_tail_as_mono_16khz_with_source_metadata(self):
        manager = SystemAudioManager()
        manager._device = LoopbackDevice(1, "Test output", 2, 48000, True)
        submitted = []
        tail = b"\x00\x04" * 4800
        class Chunker:
            def __init__(self, *args):
                pass
            def feed(self, data):
                submitted.append(data)
                return []
            def finish(self):
                return [SpeechChunk(tail, 2.0, 2.3, False)]
        class Stream:
            def read(self, *_args, **_kwargs):
                manager._stop.set()
                return b"\x00\x04\x00\x04" * 1024
            def stop_stream(self):
                pass
            def close(self):
                pass
        class Audio:
            def get_default_wasapi_loopback(self):
                return device()
            def get_loopback_device_info_generator(self):
                return iter([device()])
            def open(self, **_kwargs):
                return Stream()
            def terminate(self):
                pass
        module = types.SimpleNamespace(PyAudio=Audio, paInt16=16)
        with patch.object(manager, "_pyaudio_module", return_value=module), patch("app.system_audio.SpeechChunker", Chunker):
            manager._capture_loop()
        self.assertTrue(submitted)
        self.assertLess(len(submitted[0]), 1024 * 2)
        chunk = manager.get_chunk(.05)
        self.assertEqual((chunk.sequence, chunk.started_at, chunk.ended_at, chunk.continuation), (1, 2.0, 2.3, False))
        with wave.open(io.BytesIO(chunk.wav), "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getnframes()), (1, 16000, 4800))
        self.assertAlmostEqual(chunk.duration, .3)

    def run_fake(self, manager, fake, action):
        with patch.object(manager, '_pyaudio_module', return_value=fake.module), patch('app.system_audio.SpeechChunker', SilentChunker):
            try:
                return action()
            finally:
                manager.stop()

    def test_manual_device_rematches_name_after_index_reuse(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device(8, 'Headphones')], [device(8, 'Other'), device(19, 'Headphones')]])
        def action():
            manager.devices()
            result = manager.start(8)
            self.assertTrue(result['running'])
            self.assertEqual(result['device']['index'], 19)
            self.assertEqual(fake.opens[0]['input_device_index'], 19)
        self.run_fake(manager, fake, action)
        self.assertTrue(all(item.terminated for item in fake.instances))

    def test_auto_enumerates_once_in_capture_lifetime(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device(41)]])
        result = self.run_fake(manager, fake, manager.start)
        self.assertTrue(result['running'])
        self.assertEqual(len(fake.instances), 1)
        self.assertEqual(fake.opens[0]['input_device_index'], 41)
        self.assertEqual(fake.closes, 1)

    def test_missing_manual_device_never_falls_back_to_default(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device(1, 'Other')]])
        def action():
            with self.assertRaisesRegex(SystemAudioError, '已断开'):
                manager.start(device_name='Headphones')
        self.run_fake(manager, fake, action)
        self.assertFalse(fake.opens)

    def test_ambiguous_name_is_not_guessed(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device(1), device(2)]])
        def action():
            with self.assertRaisesRegex(SystemAudioError, '同名'):
                manager.start(device_name='Test output')
        self.run_fake(manager, fake, action)
        self.assertFalse(fake.opens)

    def test_open_invalid_device_refreshes_once_and_rematches_name(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device(3)], [device(24)]], errors=[OSError(-9996, 'Invalid device')])
        result = self.run_fake(manager, fake, lambda: manager.start(device_name='Test output'))
        self.assertTrue(result['running'])
        self.assertEqual([call['input_device_index'] for call in fake.opens], [3, 24])
        self.assertTrue(all(item.terminated for item in fake.instances))

    def test_repeated_invalid_device_is_bounded_and_actionable(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device()]], errors=[OSError(-9996, 'Invalid device')] * 2)
        def action():
            with self.assertRaisesRegex(SystemAudioError, '重新选择.*-9996'):
                manager.start()
        self.run_fake(manager, fake, action)
        self.assertEqual(len(fake.opens), 2)
        self.assertFalse(manager.running)

    def test_unrelated_open_failure_does_not_retry(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device()]], errors=[OSError(-9997, 'Invalid sample rate')])
        def action():
            with self.assertRaisesRegex(SystemAudioError, 'sample rate'):
                manager.start()
        self.run_fake(manager, fake, action)
        self.assertEqual(len(fake.opens), 1)

    def test_start_waits_for_slow_open_failure_instead_of_reporting_success(self):
        manager = SystemAudioManager()
        fake = FakeAudio(manager, [[device()]], errors=[OSError(-9997, 'late failure')], delay=.2)
        def action():
            started = time.monotonic()
            with self.assertRaisesRegex(SystemAudioError, 'late failure'):
                manager.start()
            self.assertGreaterEqual(time.monotonic() - started, .18)
        self.run_fake(manager, fake, action)

    def test_start_timeout_cancels_late_open_and_keeps_worker_until_exit(self):
        manager = SystemAudioManager()
        manager.START_TIMEOUT = .02
        gate = threading.Event()
        fake = FakeAudio(manager, [[device()]], gate=gate)
        def action():
            try:
                with self.assertRaisesRegex(SystemAudioError, '启动超时'):
                    manager.start()
                with self.assertRaisesRegex(SystemAudioError, '仍在启动或停止'):
                    manager.start()
                self.assertFalse(manager.running)
            finally:
                gate.set()
        self.run_fake(manager, fake, action)
        self.assertEqual(fake.reads, 0)
        self.assertEqual(fake.closes, 1)

    def test_initialization_failure_is_reported_and_signals_ready(self):
        manager = SystemAudioManager()
        module = types.SimpleNamespace(PyAudio=lambda: (_ for _ in ()).throw(OSError('init failed')))
        with patch.object(manager, '_pyaudio_module', return_value=module):
            with self.assertRaisesRegex(SystemAudioError, 'init failed'):
                manager.start()
        manager.stop()
        self.assertTrue(manager._ready.is_set())

    def test_unknown_legacy_index_requires_refresh(self):
        with self.assertRaisesRegex(SystemAudioError, '列表已变化'):
            SystemAudioManager().start(500)

    def test_no_default_and_invalid_candidates_are_not_guessed(self):
        audio = types.SimpleNamespace(
            get_default_wasapi_loopback=lambda: (_ for _ in ()).throw(LookupError('no analogue')),
            get_loopback_device_info_generator=lambda: iter([device(1, channels=0), device(2, rate=0), device(3)]))
        devices = SystemAudioManager._enumerate_devices(audio)
        self.assertEqual([item.index for item in devices], [3])
        with self.assertRaisesRegex(SystemAudioError, '默认声音输出'):
            SystemAudioManager._select_device(devices, None)


if __name__ == "__main__":
    unittest.main()
