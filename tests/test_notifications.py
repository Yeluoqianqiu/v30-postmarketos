# SPDX-License-Identifier: GPL-3.0-only
"""Read the actual SMS archive without marking read; clear only through its API."""
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/voice'));sys.path.insert(0,str(ROOT/'runtime/sms'))
from alert_view import notification_counts
from sms_core import Store

class NotificationTests(unittest.TestCase):
    def test_real_sms_store_unread_lasts_until_explicit_read(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=Store(root/'sms/messages.sqlite')
            try:
                ident=store.ingest({'Number':'+8613800000000','Text':'synthetic notification',
                    'Data':[],'Timestamp':'2026-10-31T10:00:00Z','PduType':1,'State':3,'MessageReference':1},'fixture/one')
                for _ in range(3):self.assertEqual(notification_counts(root/'absent',store.path)['sms'],1)
                store.get(ident,mark_read=True)
                self.assertEqual(notification_counts(root/'absent',store.path)['sms'],0)
                self.assertEqual(store.counts()['total'],1)
            finally:store.close()
