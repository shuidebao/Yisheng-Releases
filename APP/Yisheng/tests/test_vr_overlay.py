from __future__ import annotations

import ctypes
import math
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch

from app.vr_overlay import DEFAULTS, EMPTY, SteamVRDisplay, VROverlay, settings


class VRSettingsTests(unittest.TestCase):
    def test_invalid_geometry_and_boolean_values_are_rejected(self):
        for value in (math.nan, math.inf, -1, 9, True, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings({"size": value})
        with self.assertRaises(ValueError):
            settings({"original": "false"})
        with self.assertRaises(ValueError):
            settings(None)

    def test_default_is_off_and_updates_do_not_start_native_code(self):
        controller = VROverlay()
        with patch('app.vr_overlay.subprocess.Popen') as popen:
            for index in range(500):
                controller.update({"original": str(index), "translation": "字幕"})
            self.assertEqual(controller._subtitle["original"], "499")
            self.assertEqual(controller.snapshot()["state"], "off")
            popen.assert_not_called()
        controller.update(EMPTY)
        self.assertEqual(controller._subtitle, EMPTY)

    def test_config_snapshot_is_independent(self):
        controller = VROverlay()
        result = controller.configure({"original": False})
        result["settings"]["size"] = 10
        self.assertEqual(controller.snapshot()["settings"]["size"], 1)
        self.assertFalse(controller.snapshot()["settings"]["original"])


class VRProcessTests(unittest.TestCase):
    @staticmethod
    def wait_display(controller, expected, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = controller.snapshot()
            if result['state'] == 'ready' and result['display'] == expected:
                return result
            time.sleep(.02)
        raise AssertionError(controller.snapshot())

    @staticmethod
    def wait_state(controller, expected, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = controller.snapshot()
            if result["state"] == expected:
                return result
            time.sleep(.02)
        raise AssertionError(controller.snapshot())

    def make(self, script):
        controller = VROverlay([sys.executable, "-u", "-c", script])
        self.addCleanup(controller.stop)
        return controller

    def test_repeat_start_does_not_spawn_duplicate_and_restart_works(self):
        controller = self.make("import sys;\nfor line in sys.stdin: print('{\"ok\":true}', flush=True)")
        for _ in range(2):
            controller.start(DEFAULTS)
            self.wait_state(controller, "ready")
            child = controller._process
            controller.start(DEFAULTS)
            self.assertIs(controller._process, child)
            self.assertEqual(controller.stop()["state"], "off")
            self.assertIsNotNone(child.poll())

    def test_hung_child_can_be_stopped_without_late_activation(self):
        controller = self.make("import sys,time; sys.stdin.readline(); print('{\"ok\":true}',flush=True); sys.stdin.readline(); time.sleep(30)")
        controller.start(DEFAULTS)
        self.wait_state(controller, "ready")
        time.sleep(.2)
        started = time.monotonic()
        result = controller.stop()
        self.assertLess(time.monotonic() - started, 4.5)
        self.assertEqual(result["state"], "off")
        self.assertFalse(controller._thread.is_alive())

    def test_startup_timeout_cleans_child_and_immediate_stop_can_restart(self):
        controller = self.make("import sys,time; sys.stdin.readline(); time.sleep(30)")
        with patch('app.vr_overlay.START_TIMEOUT_SECONDS', .15):
            controller.start(DEFAULTS)
            self.assertEqual(self.wait_state(controller, "error")["error"], "timeout")
        controller.start(DEFAULTS)
        self.assertEqual(controller.stop()["state"], "off")
        self.assertFalse(controller._thread.is_alive())

    def test_native_errors_reach_ui_and_child_is_cleaned(self):
        controller = self.make("import sys; sys.stdin.readline(); print('{\"error\":\"no_headset\"}',flush=True)")
        controller.start(DEFAULTS)
        result = self.wait_state(controller, "error")
        self.assertEqual(result["error"], "no_headset")
        self.assertIsNone(controller._process)

    def test_process_exit_does_not_report_ready(self):
        controller = self.make("raise SystemExit(0)")
        controller.start(DEFAULTS)
        result = self.wait_state(controller, "error")
        self.assertIn(result["error"], ("worker_exit", "runtime_error"))

    def test_blocked_pipe_write_does_not_prevent_stop(self):
        controller = self.make("import sys,time; sys.stdin.readline(); print('{\"ok\":true}',flush=True); time.sleep(30)")
        controller.update({"original": "字" * 4000, "translation": "幕" * 4000})
        controller.start(DEFAULTS)
        self.wait_state(controller, 'ready')
        child = controller._process
        time.sleep(.3)  # The second request exceeds the pipe's buffer.
        started = time.monotonic()
        self.assertEqual(controller.stop()['state'], 'off')
        self.assertLess(time.monotonic() - started, 4.5)
        self.assertIsNotNone(child.poll())
        self.assertFalse(controller._thread.is_alive())

    def test_response_deadline_includes_blocked_pipe_write(self):
        controller = self.make("import sys,time; sys.stdin.readline(); print('{\"ok\":true}',flush=True); time.sleep(30)")
        controller.update({"original": "字" * 4000, "translation": "幕" * 4000})
        with patch('app.vr_overlay.RESPONSE_TIMEOUT_SECONDS', .2):
            controller.start(DEFAULTS)
            result = self.wait_state(controller, 'error')
        self.assertEqual(result['error'], 'timeout')
        self.assertIsNone(controller._process)

    def test_test_subtitle_requires_ready_and_restores_current_without_history(self):
        controller = self.make("import sys;\nfor line in sys.stdin: print('{\"ok\":true}', flush=True)")
        self.assertEqual(controller.preview()['error'], 'not_ready')
        self.assertIsNone(controller._thread)
        current = {**EMPTY, 'translation': 'actual subtitle'}
        controller.update(current)
        controller.start(DEFAULTS)
        self.wait_display(controller, 'subtitle')
        controller.preview('en')
        self.wait_display(controller, 'preview')
        self.assertEqual(controller._subtitle, current)
        self.assertGreater(controller._preview_until - time.monotonic(), 4)
        with controller._lock:
            controller._preview_until = time.monotonic() - 1
        self.wait_display(controller, 'subtitle')
        controller.preview()
        self.wait_display(controller, 'preview')
        controller.update({**EMPTY, 'translation': 'new subtitle'})
        self.wait_display(controller, 'subtitle')
        controller.preview()
        self.wait_display(controller, 'preview')
        controller.update(EMPTY)
        self.wait_display(controller, 'empty')

    def test_malformed_success_reply_is_not_reported_as_connected(self):
        controller = self.make("import sys; sys.stdin.readline(); print('{}',flush=True)")
        controller.start(DEFAULTS)
        self.assertEqual(self.wait_state(controller, 'error')['error'], 'runtime_error')

    def test_cleanup_failure_keeps_owned_process_blocks_start_and_can_retry(self):
        for failure in ('kill', 'wait'):
            with self.subTest(failure=failure):
                controller = VROverlay()
                process = Mock()
                process.poll.return_value = None
                process.wait.side_effect = subprocess.TimeoutExpired('owned-vr-worker', 1.5)
                process.kill.side_effect = OSError('temporarily unavailable') if failure == 'kill' else None
                controller._publish_exit(process, (), 'runtime_error')
                self.assertIs(controller._process, process)
                self.assertEqual(controller.snapshot()['error'], 'cleanup_failed')
                with patch('app.vr_overlay.subprocess.Popen') as popen:
                    controller.start(DEFAULTS)
                    popen.assert_not_called()
                self.assertEqual(controller.snapshot()['error'], 'cleanup_failed')
                process.poll.return_value = 0
                self.assertEqual(controller.stop()['state'], 'off')
                self.assertIsNone(controller._process)


class VRDisplayTests(unittest.TestCase):
    def setUp(self):
        class Matrix(ctypes.Structure):
            _fields_ = [("m", (ctypes.c_float * 4) * 3)]
        self.vr = types.SimpleNamespace(
            HmdMatrix34_t=Matrix, VREvent_t=lambda: types.SimpleNamespace(eventType=0),
            VREvent_Quit=700, VREvent_ImageFailed=517, k_unTrackedDeviceIndex_Hmd=0)
        self.display = SteamVRDisplay()
        self.display.vr = self.vr
        self.display.system = Mock()
        self.display.system.isTrackedDeviceConnected.return_value = True
        self.display.system.pollNextEvent.return_value = False
        self.display.overlay = Mock()
        self.display.overlay.pollNextOverlayEvent.return_value = (False, None)
        self.display.handle = 99
        self.render = patch('app.vr_overlay.render_text', return_value=(b'\xff\x00\x00\xff', 1, 1)).start()
        self.addCleanup(patch.stopall)

    def test_latest_text_is_rendered_once_and_clear_hides_overlay(self):
        value = {**EMPTY, "translation": "当前一句"}
        self.display.tick(value, DEFAULTS)
        self.display.tick(dict(value), dict(DEFAULTS))
        self.render.assert_called_once()
        self.display.overlay.showOverlay.assert_called_once_with(99)
        self.display.tick(EMPTY, DEFAULTS)
        self.display.overlay.hideOverlay.assert_called_once_with(99)
        self.display.tick({**EMPTY, "translation": "下一句"}, DEFAULTS)
        self.assertEqual(self.render.call_count, 2)

    def test_head_relative_geometry_and_rgba_buffer(self):
        self.display.tick({**EMPTY, "translation": "字"}, DEFAULTS)
        handle, device, matrix = self.display.overlay.setOverlayTransformTrackedDeviceRelative.call_args.args
        self.assertEqual((handle, device), (99, 0))
        self.assertAlmostEqual(matrix.m[2][3], -1.5)
        self.assertAlmostEqual(matrix.m[1][3], -.525)
        self.assertEqual(matrix.m[0][0], 1)
        self.assertAlmostEqual(self.display.overlay.setOverlayWidthInMeters.call_args.args[1], 1.05)
        self.assertEqual(bytes(self.display._pixels)[:4], b'\xff\x00\x00\xff')

    def test_no_original_or_translation_hides_even_with_meta(self):
        self.display.tick({**EMPTY, "original": "hidden", "meta": "status"}, {**DEFAULTS, "original": False})
        self.render.assert_not_called()
        self.display.overlay.hideOverlay.assert_called_once()

    def test_disconnection_and_runtime_quit_are_explicit(self):
        self.display.system.isTrackedDeviceConnected.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'no_headset'):
            self.display.tick(EMPTY, DEFAULTS)
        self.display.overlay.pollNextOverlayEvent.return_value = (True, types.SimpleNamespace(eventType=700))
        with self.assertRaisesRegex(RuntimeError, 'runtime_quit'):
            self.display.tick(EMPTY, DEFAULTS)
        self.display.system.acknowledgeQuit_Exiting.assert_called_once()

    def test_failed_overlay_destruction_still_shuts_down_runtime(self):
        self.display._initialized = True
        self.vr.shutdown = Mock()
        self.display.overlay.destroyOverlay.side_effect = RuntimeError('gone')
        with self.assertRaises(RuntimeError):
            self.display.close()
        self.vr.shutdown.assert_called_once()

    def test_async_image_failure_is_not_hidden_by_cached_subtitle(self):
        text = {**EMPTY, 'translation': 'current'}
        self.display.tick(text, DEFAULTS)
        self.display.overlay.pollNextOverlayEvent.return_value = (True, types.SimpleNamespace(eventType=517))
        with self.assertRaisesRegex(RuntimeError, 'runtime_error'):
            self.display.tick(text, DEFAULTS)


if __name__ == '__main__':
    unittest.main()
