# SPDX-License-Identifier: GPL-3.0-only
"""Persistence, terminal evidence, restart reconciliation and volume boundaries."""
from pathlib import Path
import json, os, sqlite3, tempfile, unittest
from unittest.mock import patch
from call_history import History
from alert_view import ring_volume,notification_counts,notification_line
import alert_audio as audio

class HistoryTests(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory()
        store=History(Path(temporary.name)/'calls.sqlite')
        self.addCleanup(temporary.cleanup);self.addCleanup(store.close)
        return store

    def call(self,uni='one',state='incoming',direction='incoming'):
        return {'uni':uni,'number':'+8613800000000','state':state,'direction':direction}

    def test_remote_cancel_is_missed_and_duplicate_events_do_not_duplicate(self):
        store=self.fixture()
        store.observe('a',self.call());store.observe('a',self.call())
        store.state('a','one','terminated','remote-hangup')
        store.disappeared('a','one')
        rows=store.listing(missed=True)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['result'],'missed')
        self.assertIsNone(rows[0]['answered'])

    def test_answer_signal_survives_a_snapshot_that_only_sees_end(self):
        store=self.fixture();store.observe('a',self.call())
        store.state('a','one','active');store.state('a','one','terminated','remote-hangup')
        self.assertEqual(store.listing()[0]['result'],'answered')
        self.assertEqual(store.listing(missed=True),[])

    def test_owner_loss_and_missing_terminal_evidence_are_unknown(self):
        store=self.fixture();store.observe('a',self.call());store.owner_left('a')
        store.observe('b',self.call());store.reconcile('b',[])
        self.assertEqual([r['result'] for r in store.listing()],['unknown','unknown'])
        self.assertEqual(store.listing(missed=True),[])

    def test_reject_is_not_missed_and_same_uni_in_new_owner_is_distinct(self):
        store=self.fixture();store.observe('a',self.call());store.state('a','one','terminated','local-hangup')
        store.observe('b',self.call());store.state('b','one','terminated','remote-hangup')
        self.assertEqual([r['result'] for r in store.listing()],['missed','rejected'])

    def test_restart_preserves_history_and_noop_snapshot_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'calls.sqlite';store=History(path);store.observe('a',self.call())
            before=store.db.total_changes
            store.observe('a',self.call());self.assertEqual(store.db.total_changes,before)
            store.close();store=History(path)
            store.state('a','one','terminated','remote-hangup');store.close()
            store=History(path)
            try:self.assertEqual(store.listing()[0]['result'],'missed')
            finally:store.close()
            self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_imported_verified_test_is_labelled_and_idempotent(self):
        store=self.fixture()
        for _ in range(2):store.import_missed_test('operator-test:fixture','+8613800000000',100,110)
        rows=store.listing()
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['evidence'],'test-report')
        with self.assertRaises(ValueError):store.import_missed_test('made-up','x',100,110)

    def test_volume_default_mute_invalid_and_persisted_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            config=Path(d)/'config'
            self.assertEqual(ring_volume(config),60)
            for value in [0,60,100]:
                config.write_text(json.dumps({'ring_volume':value}));self.assertEqual(ring_volume(config),value)
            for value in [-1,101,True,'80',None]:
                config.write_text(json.dumps({'ring_volume':value}));self.assertEqual(ring_volume(config),0)
            config.write_text('bad');self.assertEqual(ring_volume(config),0)
            for value in [-1,101,True]:
                with self.assertRaises(ValueError):audio.write_tone(Path(d)/'ring.wav',value)

    def test_notification_counts_persist_and_ack_only_selected_calls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=History(root/'calls.sqlite')
            try:
                for uni in ['one','two']:
                    store.observe('a',self.call(uni));store.state('a',uni,'terminated','remote-hangup')
                sms=root/'sms.sqlite';connection=sqlite3.connect(sms)
                connection.execute('CREATE TABLE messages(direction TEXT,unread INTEGER)')
                connection.executemany('INSERT INTO messages VALUES (?,?)',[('incoming',1),('incoming',0),('outgoing',1)])
                connection.commit()
                self.assertEqual(notification_counts(store.path,sms),{'missed':2,'sms':1})
                ids=[store.listing()[0]['id']];store.acknowledge(ids)
                store.observe('a',self.call('three'));store.state('a','three','terminated','remote-hangup')
                self.assertEqual(notification_counts(store.path,sms),{'missed':2,'sms':1})
                store.acknowledge([row['id'] for row in store.listing()])
                connection.execute("UPDATE messages SET unread=0 WHERE direction='incoming'");connection.commit();connection.close()
                self.assertEqual(notification_counts(store.path,sms),{'missed':0,'sms':0})
                self.assertEqual(len(store.listing()),3)
            finally:store.close()

    def test_missing_corrupt_archives_and_notification_text(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bad=root/'bad.sqlite';bad.write_bytes(b'not-a-database')
            self.assertEqual(notification_counts(root/'absent',root/'absent'),{'missed':0,'sms':0})
            self.assertEqual(notification_counts(bad,bad),{'missed':None,'sms':None})
            self.assertIsNone(notification_line({'missed':0,'sms':0},100))
            line=notification_line({'missed':1200,'sms':None},100)
            self.assertIn('MISSED 999+',line[0]);self.assertIn('SMS ?',line[0]);self.assertEqual(len(line[0]),100)

    def test_migration_preserves_old_history_and_marks_existing_missed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'calls.sqlite';store=History(path)
            store.observe('a',self.call());store.state('a','one','terminated','remote-hangup');store.close()
            connection=sqlite3.connect(path);connection.execute('ALTER TABLE calls DROP COLUMN unread');connection.close()
            store=History(path)
            try:self.assertEqual(store.listing()[0]['unread'],1)
            finally:store.close()
