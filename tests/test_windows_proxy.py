import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from windows_proxy import WindowsProxy


class ProxyLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.proxy = WindowsProxy.__new__(WindowsProxy)
        self.proxy.path = Path(self.directory.name) / 'proxy.json'
        self.proxy.mutex = 1
        self.previous = [5, 'previous.example:8080', '<local>', 'https://example.invalid/pac']
        self.current = self.previous[:]
        self.proxy.api = Mock()
        self.proxy.api.read.side_effect = lambda: self.current[:]
        self.proxy.api.write.side_effect = self.write
        for target, kwargs in [('windows_proxy.subprocess.Popen', {}),
                               ('windows_proxy.subprocess.CREATE_NO_WINDOW', {'new':0,'create':True})]:
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, values):
        self.current = values[:]

    def test_restore_original_including_pac(self):
        self.proxy.enable(12345)
        self.assertEqual(self.current[0], 3)
        self.assertIn('https=127.0.0.1:12345', self.current[1])
        self.proxy.close()
        self.assertEqual(self.current, self.previous)
        self.assertFalse(self.proxy.path.exists())

    def test_manual_changes_survive_disconnect(self):
        self.proxy.enable(12345)
        self.current = [1, '', '', '']
        self.proxy.close()
        self.assertEqual(self.current, [1, '', '', ''])

    def test_failed_application_rolls_back(self):
        def fail_once(values):
            self.write(values)
            if values != self.previous:
                raise OSError('notification failed')
        self.proxy.api.write.side_effect = fail_once
        with self.assertRaises(OSError):
            self.proxy.enable(12345)
        self.assertEqual(self.current, self.previous)
        self.assertFalse(self.proxy.path.exists())
        self.proxy.close()

    def test_failed_restore_keeps_recovery_record(self):
        self.proxy.enable(12345)
        self.proxy.api.write.side_effect = OSError('restore failed')
        with self.assertRaises(OSError):
            self.proxy.close()
        self.assertTrue(self.proxy.path.exists())
        self.proxy.api.kernel.CloseHandle.assert_called_once()

    def test_repeated_close_does_not_touch_another_session(self):
        self.proxy.enable(12345)
        self.proxy.close()
        self.proxy.api.read.reset_mock()
        self.proxy.close()
        self.proxy.api.read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
