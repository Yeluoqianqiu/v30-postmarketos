# SPDX-License-Identifier: GPL-3.0-only
"""Regression checks for call priority, private caller display and alert lifecycle."""
from pathlib import Path
from unittest.mock import patch
import fcntl, json, os, subprocess, sys, tempfile, unittest, wave
import alert_audio as audio
import incoming_alerts as incoming
from alert_view import caller_label, incoming_line


class Worker:
    def __init__(self, events):
        self.events = events; self.returncode = None
    def poll(self): return self.returncode
    def terminate(self): self.events.append('stop'); self.returncode = 0
    def wait(self, timeout=None): return self.returncode


class IncomingTests(unittest.TestCase):
    def test_labels_reject_terminal_tmux_bidi_and_private_identities(self):
        self.assertEqual(caller_label('+8613800000000'), '+8613800000000')
        for value in ['', None, 'anonymous', 'sip:private@example.test', '#(touch /tmp/bad)',
                      '123\x1b[2J', '123\u202e456', '1'*40, '\u4e00\u4e8c\u4e09']:
            self.assertEqual(caller_label(value), 'Unknown/withheld')

    def test_display_expires_on_time_boot_and_state_change(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'display.json'
            state = {'boot': 'a', 'updated': 10, 'state': 'incoming', 'number': '+8613800000000'}
            path.write_text(json.dumps(state))
            line = incoming_line(path, 'a', 12, 100)
            self.assertEqual(len(line[0]), 100)
            self.assertIn('INCOMING', line[0])
            for boot, now in [('b', 12), ('a', 17), ('a', 9)]:
                self.assertIsNone(incoming_line(path, boot, now, 100))
            state['state'] = 'idle'; path.write_text(json.dumps(state))
            self.assertIsNone(incoming_line(path, 'a', 12, 100))

    def lifecycle(self, exercise):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); boot = root/'boot'; boot.write_text('fixture-boot')
            events = []
            def command(args, **kw):
                events.append('wake' if args[-1] == 'on' else 'console')
                return subprocess.CompletedProcess(args, 0)
            def spawn(*args, **kw): events.append('ring'); return Worker(events)
            with patch.object(incoming, 'RUN', root), patch.object(audio, 'RUN', root), patch.object(incoming, 'BOOT', boot), \
                 patch.object(incoming, 'start_ticks', return_value='fixture-start'), \
                 patch.object(incoming.subprocess, 'run', side_effect=command), \
                 patch.object(incoming.subprocess, 'Popen', side_effect=spawn):
                from call_history import History
                app = incoming.Alerts(clock=lambda: 10, history=History(root/'history/calls.sqlite'))
                call = {'uni': 'call-a', 'state': 'incoming', 'direction': 'incoming', 'number': '+8613800000000'}
                exercise(app, call, events, root)
                app.history.close()

    def test_repeated_signals_wake_and_ring_once_then_cancel_clears(self):
        def run(app, call, events, root):
            app.update(':1.1', [call]); app.update(':1.1', [call])
            self.assertEqual(events.count('wake'), 1); self.assertEqual(events.count('ring'), 1)
            app.update(':1.1', [])
            self.assertEqual(events.count('stop'), 1)
            self.assertEqual(json.loads((root/'display.json').read_text())['number'], '')
        self.lifecycle(run)

    def test_answer_stops_ring_and_owner_loss_withdraws_display(self):
        def run(app, call, events, root):
            app.update(':1.1', [call]); call['state'] = 'active'; app.update(':1.1', [call])
            self.assertEqual(events.count('stop'), 1)
            self.assertEqual(json.loads((root/'display.json').read_text())['state'], 'idle')
            app.update('', [])
            self.assertFalse(json.loads((root/'status.json').read_text())['ready'])
        self.lifecycle(run)

    def test_new_owner_can_reuse_call_id_without_stale_state(self):
        def run(app, call, events, root):
            app.update(':1.1', [call]); app.update(':1.2', [call])
            self.assertEqual(events.count('stop'), 1); self.assertEqual(events.count('ring'), 2)
            app.update(':1.2', [])
        self.lifecycle(run)

    def test_failed_or_expired_worker_is_not_restarted_for_same_call(self):
        def run(app, call, events, root):
            app.update(':1.1', [call]); app.worker.returncode = 1
            app.update(':1.1', [call]); self.assertEqual(events.count('ring'), 1)
            app.update(':1.1', []); call['uni'] = 'call-b'; app.update(':1.1', [call])
            self.assertEqual(events.count('ring'), 2); app.update('', [])
        self.lifecycle(run)

    def test_call_waiting_does_not_compete_with_active_audio(self):
        def run(app, call, events, root):
            active = dict(call, uni='active', state='active')
            app.update(':1.1', [active, call])
            self.assertNotIn('ring', events); self.assertNotIn('wake', events)
        self.lifecycle(run)

    def test_muted_ringing_still_wakes_and_shows_caller(self):
        def run(app, call, events, root):
            with patch.object(incoming, 'ring_volume', return_value=0):
                app.update(':1.1', [call])
            self.assertIn('wake', events); self.assertNotIn('ring', events)
            self.assertEqual(json.loads((root/'display.json').read_text())['state'], 'incoming')
            app.update('', [])
        self.lifecycle(run)

    def test_history_storage_error_does_not_disable_incoming_alert(self):
        def run(app, call, events, root):
            import sqlite3
            with patch.object(app.history, 'observe', side_effect=sqlite3.OperationalError('fixture full')):
                app.update(':1.1', [call])
            self.assertIn('wake', events); self.assertIn('ring', events)
            self.assertFalse(json.loads((root/'status.json').read_text())['history_ready'])
            app.update('', [])
        self.lifecycle(run)

    def test_ring_journal_survives_partial_restore_and_is_retried(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); boot = root/'boot'; boot.write_text('fixture')
            before = {name: 'off' for name, _ in audio.PLAYBACK}
            audio.atomic_json(root/'mixer.json', {'boot': 'fixture', 'before': before})
            seen = []
            def restore(name, value):
                seen.append(name)
                if name == audio.PLAYBACK[1][0]: raise OSError('fixture')
            with patch.object(audio, 'RUN', root), patch.object(audio, 'BOOT', boot), \
                 patch.object(audio, 'get_control', return_value='off'), \
                 patch.object(audio, 'set_control', side_effect=restore):
                with self.assertRaises(RuntimeError): audio.recover_ring_mixer()
                self.assertEqual(set(seen), set(before)); self.assertTrue((root/'mixer.json').exists())
            with patch.object(audio, 'RUN', root), patch.object(audio, 'BOOT', boot), \
                 patch.object(audio, 'get_control', return_value='off'), patch.object(audio, 'set_control'):
                audio.recover_ring_mixer()
            self.assertFalse((root/'mixer.json').exists())

    def test_media_preempts_ring_and_reserves_audio_until_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); audio_lock = root/'audio.lock'; priority = root/'priority.lock'
            runner = """import sys,time,fcntl;from pathlib import Path
import alert_audio as a
a.PRIORITY_LOCK=Path(sys.argv[1]);lock=a.lock_file(Path(sys.argv[2]));fcntl.flock(lock,fcntl.LOCK_EX)
print('ring-ready',flush=True)
end=time.monotonic()+5
while time.monotonic()<end and not a.media_pending():time.sleep(.01)
print('ring-stopped',flush=True);lock.close()
"""
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).parent))
            child = subprocess.Popen([sys.executable, '-c', runner, str(priority), str(audio_lock)],
                                     env=env, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'ring-ready')
                with patch.object(audio, 'RUN', root), patch.object(audio, 'AUDIO_LOCK', audio_lock), \
                     patch.object(audio, 'PRIORITY_LOCK', priority):
                    with self.assertRaisesRegex(RuntimeError, 'cleanup fixture'):
                        with audio.media_audio_lock(timeout=2):
                            self.assertTrue(audio.media_pending())
                            self.assertEqual(child.stdout.readline().strip(), 'ring-stopped')
                            with audio.lock_file(audio_lock) as other:
                                with self.assertRaises(BlockingIOError):
                                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            raise RuntimeError('cleanup fixture')
                    self.assertFalse(audio.media_pending())
                    with audio.media_audio_lock(timeout=.1): pass
                self.assertEqual(child.wait(timeout=2), 0)
            finally:
                if child.poll() is None: child.kill(); child.wait(timeout=2)
                child.stdout.close()

    def test_generated_ringtone_is_bounded_stereo_and_contains_silence(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'ring.wav'; audio.write_tone(path, 60)
            import array
            with wave.open(str(path)) as stream:
                self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()), (2, 2, 48000, 96000))
                data = array.array('h', stream.readframes(96000))
                self.assertLessEqual(max(abs(v) for v in data), 4915)
                self.assertTrue(all(v == 0 for v in data[70000:]))

    def test_cleanup_failure_never_restores_again_without_audio_lock(self):
        with tempfile.TemporaryDirectory() as d:
            tone = audio.Ringtone(); tone.lock = audio.lock_file(Path(d)/'audio.lock')
            fcntl.flock(tone.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            tone.journaled = True
            with patch.object(audio, 'recover_ring_mixer', side_effect=OSError('fixture')) as recover:
                with self.assertRaises(OSError): tone.close()
                tone.close()
                self.assertEqual(recover.call_count, 1)
                self.assertIsNone(tone.lock)

    def test_codec_gain_is_restored_after_playback_route_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);boot=root/'boot';boot.write_text('fixture')
            before={name:'off' for name,_ in audio.PLAYBACK};before['ADC3 Volume']='7'
            audio.atomic_json(root/'mixer.json',{'boot':'fixture','before':before})
            values=dict(before);order=[]
            def change(name,value):
                order.append(name);values[name]=value
                if name=='Speaker Playback Volume':values['ADC3 Volume']='12'
            with patch.object(audio,'RUN',root),patch.object(audio,'BOOT',boot), \
                 patch.object(audio,'set_control',side_effect=change),patch.object(audio,'get_control',side_effect=lambda name:values[name]):
                audio.recover_ring_mixer()
            self.assertEqual(values['ADC3 Volume'],'7');self.assertEqual(order[-1],'ADC3 Volume')


if __name__ == '__main__': unittest.main()
