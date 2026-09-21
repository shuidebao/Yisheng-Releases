from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from app.inference_runtime import configure_inference_runtime


class InferenceRuntimeTests(unittest.TestCase):
    def test_windows_defaults_to_short_spin_without_changing_thread_budget(self):
        with mock.patch('app.inference_runtime.sys.platform', 'win32'), mock.patch.dict(
            os.environ, {'YISHENG_TEST_SENTINEL': 'keep'}, clear=True
        ):
            configure_inference_runtime()
            self.assertEqual(dict(os.environ), {'YISHENG_TEST_SENTINEL': 'keep', 'KMP_BLOCKTIME': '1'})
            configure_inference_runtime()
            self.assertEqual(os.environ['KMP_BLOCKTIME'], '1')

    def test_explicit_wait_settings_are_preserved(self):
        for settings in ({'KMP_BLOCKTIME': '0'}, {'KMP_BLOCKTIME': '200'},
                         {'KMP_BLOCKTIME': ''}, {'OMP_WAIT_POLICY': 'ACTIVE'},
                         {'OMP_WAIT_POLICY': 'PASSIVE'}, {'KMP_LIBRARY': 'throughput'},
                         {'KMP_BLOCKTIME': '5', 'OMP_WAIT_POLICY': 'ACTIVE'}):
            with self.subTest(settings=settings), mock.patch('app.inference_runtime.sys.platform', 'win32'), \
                    mock.patch.dict(os.environ, settings, clear=True):
                configure_inference_runtime()
                self.assertEqual(dict(os.environ), settings)

    def test_unmeasured_platforms_are_not_changed(self):
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform), mock.patch('app.inference_runtime.sys.platform', platform), \
                    mock.patch.dict(os.environ, {}, clear=True):
                configure_inference_runtime()
                self.assertEqual(dict(os.environ), {})

    def test_fresh_app_import_sets_policy_before_loading_any_inference_dependencies(self):
        app_root = Path(__file__).resolve().parents[1]
        child_env = os.environ.copy()
        for name in ('KMP_BLOCKTIME', 'OMP_WAIT_POLICY', 'KMP_LIBRARY'):
            child_env.pop(name, None)
        code = (
            "import os, sys; "
            f"sys.path.insert(0, {str(app_root)!r}); "
            "import app; "
            "assert os.environ.get('KMP_BLOCKTIME') == ('1' if sys.platform == 'win32' else None); "
            "assert not {'ctranslate2','faster_whisper','numpy','webview','onnxruntime'} & set(sys.modules)"
        )
        child = subprocess.run([sys.executable, '-S', '-c', code], env=child_env,
                               capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(child.returncode, 0, child.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
