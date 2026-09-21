from pathlib import Path
import unittest


class InstallerPayloadTests(unittest.TestCase):
    def test_development_and_user_state_are_excluded(self):
        repository = Path(__file__).resolve().parents[3]
        build = (repository / 'build_offline_installer.ps1').read_text(encoding='utf-8')
        for directory in ('.build', 'tests', 'logs', '__pycache__', 'model-sources',
                          '.models/webview-profile', '.models/webview-test-profile',
                          '.models/clear-webview-cache'):
            with self.subTest(directory=directory):
                self.assertIn(f'"--exclude={directory}"', build)


if __name__ == '__main__':
    unittest.main()
