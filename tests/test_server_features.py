import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import quality
from instance import SingleInstance
from controller import Bridge
from lifecycle import Attempt, Cancelled


class QualityTests(unittest.TestCase):
    def test_stable_server_beats_fast_unreliable_server(self):
        stable={'successes':20,'failures':1,'sessions':10,'drops':0,'latency_ms':300,'checked_at':time.time()}
        fast={'successes':2,'failures':8,'sessions':5,'drops':4,'latency_ms':20,'checked_at':time.time()}
        self.assertGreater(quality.score(stable),quality.score(fast))

    def test_metadata_is_inferred_only_from_labels(self):
        self.assertEqual(quality.country('🇩🇪 Frankfurt'),'DE')
        self.assertEqual(quality.country('[NL] Amsterdam'),'NL')
        self.assertEqual(quality.country('server in Europe'),'')
        self.assertEqual(quality.country('My private server'),'')

    def test_result_persists_freshness_and_success_ratio(self):
        record=quality.result({},True,100)
        record=quality.result(record,False)
        self.assertEqual((record['successes'],record['failures'],record['status']),(1,1,'failed'))
        self.assertEqual(record['latency_ms'],100)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.bridge=Bridge(self.temp.name)
        self.bridge._nodes={str(i):{'protocol':'test','settings':{'id':i}} for i in range(6)}

    def tearDown(self):
        self.bridge._close_window()
        self.bridge._wake.set()
        self.bridge._monitor.join(timeout=2)
        self.bridge._store.db.close()
        self.temp.cleanup()

    def test_selection_respects_candidates_and_ignores_failed_probes(self):
        def probe(node,attempt):
            if node['settings']['id']==2: raise OSError('failed')
            return 120
        self.bridge._probe=Mock(side_effect=probe)
        result=self.bridge._choose_server(Attempt(),['2','3'])
        self.assertEqual(result,'3')
        self.assertEqual(self.bridge._probe.call_count,2)
        items={item['name']:item for item in self.bridge.servers()['items']}
        self.assertEqual(items['2']['status'],'failed')
        self.assertEqual(items['3']['status'],'passed')
        self.assertEqual(items['1']['status'],'untested')

    def test_four_probe_limit(self):
        self.bridge._probe=Mock(return_value=50)
        self.bridge._choose_server(Attempt(),list(self.bridge._nodes))
        self.assertEqual(self.bridge._probe.call_count,4)

    def test_cancel_does_not_count_as_server_failure(self):
        self.bridge._probe=Mock(side_effect=Cancelled())
        with self.assertRaises(Cancelled):
            self.bridge._choose_server(Attempt(),['1'])
        self.assertEqual(self.bridge.servers()['items'][1]['status'],'untested')


class InstanceTests(unittest.TestCase):
    def test_second_instance_activates_first_and_lock_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            first=SingleInstance(directory)
            self.assertTrue(first.acquire())
            event=threading.Event()
            first.set_callback(event.set)
            second=SingleInstance(directory)
            self.assertFalse(second.acquire())
            self.assertTrue(event.wait(2))
            first.close()
            third=SingleInstance(directory)
            self.assertTrue(third.acquire())
            third.close()



class PreflightTests(unittest.TestCase):
    def test_invalid_configuration_never_starts_runtime(self):
        import bridge
        with patch.object(bridge,'validate_config',side_effect=ValueError('invalid')), patch.object(bridge.subprocess,'Popen') as spawn:
            with self.assertRaises(ValueError):
                bridge.start({'protocol':'invalid'})
        spawn.assert_not_called()

    def test_conflict_detector_excludes_own_core(self):
        import os
        from desktop_integration import vpn_conflicts
        own=Mock(info={'name':'xray.exe','ppid':os.getpid()})
        other=Mock(info={'name':'wireguard.exe','ppid':123456789})
        with patch('desktop_integration.psutil.net_if_stats',return_value={}), patch('desktop_integration.psutil.process_iter',return_value=[own,other]):
            self.assertEqual(vpn_conflicts()['warnings'],['wireguard.exe'])

    def test_core_running_does_not_mean_connected(self):
        ready,finish=threading.Event(),threading.Event()
        connection=Mock(started=time.monotonic())
        connection.running.return_value=True
        connection.counters.return_value={'upload':0,'download':0}
        def factory(outbound,attempt):
            attempt.core_ready=True
            return connection
        with tempfile.TemporaryDirectory() as directory:
            api=Bridge(directory,connect=factory)
            api._nodes={'test':{'protocol':'test'}}
            api._check_access=lambda port,attempt:(ready.set(),finish.wait(3))
            try:
                api.connect('test')
                self.assertTrue(ready.wait(2))
                state=api.snapshot()
                self.assertTrue(state['core_running'])
                self.assertFalse(state['internet_verified'])
                self.assertFalse(state['active'])
                finish.set()
                for _ in range(100):
                    if api.snapshot()['active']:break
                    time.sleep(.01)
                self.assertTrue(api.snapshot()['internet_verified'])
            finally:
                finish.set()
                api._close_window()
                api._wake.set()
                api._monitor.join(timeout=2)
                api._store.db.close()

if __name__=='__main__': unittest.main()
