# SPDX-License-Identifier: GPL-3.0-only
"""Private call history; terminal evidence distinguishes missed from unknown."""
from pathlib import Path
import os, sqlite3, stat, time
from alert_view import caller_label

DB = Path('/var/lib/v30-mobile/calls.sqlite')


class History:
    def __init__(self, path=DB):
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.path.parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Unsafe call-history directory')
        if self.path.exists() or self.path.is_symlink():
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise ValueError('Unsafe call-history database')
        old = os.umask(0o077)
        try:
            self.db = sqlite3.connect(self.path, timeout=.25)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('''CREATE TABLE IF NOT EXISTS calls (
              id INTEGER PRIMARY KEY, source TEXT NOT NULL, uni TEXT NOT NULL,
              number TEXT NOT NULL, direction TEXT NOT NULL, started REAL NOT NULL,
              answered REAL, ended REAL, result TEXT NOT NULL, last_state TEXT NOT NULL,
              evidence TEXT NOT NULL DEFAULT 'live', unread INTEGER NOT NULL DEFAULT 0, UNIQUE(source,uni))''')
            columns={row[1] for row in self.db.execute('PRAGMA table_info(calls)')}
            if 'unread' not in columns:
                self.db.execute('ALTER TABLE calls ADD COLUMN unread INTEGER NOT NULL DEFAULT 0')
                self.db.execute("UPDATE calls SET unread=1 WHERE result='missed'")
            self.db.commit()
        finally:
            os.umask(old)

    def close(self):
        self.db.close()

    def observe(self, source, info, now=None):
        now = time.time() if now is None else now
        uni = info.get('uni'); direction = info.get('direction')
        state = info.get('state')
        if not isinstance(uni, str) or not 0 < len(uni) <= 256 or direction not in ('incoming','outgoing'):
            return
        if state not in ('incoming','dialing','ringing','active','terminated'):
            return
        started = info.get('startedAt', now)
        if not isinstance(started, (int,float)) or not 1e9 < started <= now+300:
            started = now
        with self.db:
            self.db.execute('''INSERT OR IGNORE INTO calls
              (source,uni,number,direction,started,result,last_state) VALUES (?,?,?,?,?,?,?)''',
              (source,uni,caller_label(info.get('number')),direction,started,'pending',state))
        self.state(source, uni, state, info.get('reason',''), now)

    def state(self, source, uni, state, reason='', now=None):
        now = time.time() if now is None else now
        row = self.db.execute('SELECT * FROM calls WHERE source=? AND uni=?',(source,uni)).fetchone()
        if row is None or row['ended'] is not None:
            return
        if state == row['last_state'] and state != 'terminated' and (state != 'active' or row['answered'] is not None):
            return
        with self.db:
            if state == 'active':
                self.db.execute('UPDATE calls SET answered=COALESCE(answered,?),last_state=? WHERE id=?',
                                (now,state,row['id']))
            elif state == 'terminated':
                if row['answered'] is not None: result='answered'
                elif row['direction']=='incoming' and reason=='remote-hangup': result='missed'
                elif row['direction']=='incoming' and reason=='local-hangup': result='rejected'
                else: result='failed'
                self.db.execute('UPDATE calls SET ended=?,result=?,last_state=?,unread=? WHERE id=?',
                                (now,result,state,int(result=='missed'),row['id']))
            else:
                self.db.execute('UPDATE calls SET last_state=? WHERE id=?',(state,row['id']))

    def disappeared(self, source, uni, now=None):
        now = time.time() if now is None else now
        with self.db:
            self.db.execute('''UPDATE calls SET ended=?, result=CASE WHEN answered IS NOT NULL
              THEN 'answered' ELSE 'unknown' END,last_state='unknown'
              WHERE source=? AND uni=? AND ended IS NULL''',(now,source,uni))

    def reconcile(self, source, calls):
        live = {c.get('uni') for c in calls}
        for row in self.db.execute('SELECT uni FROM calls WHERE source=? AND ended IS NULL',(source,)).fetchall():
            if row['uni'] not in live:
                self.disappeared(source,row['uni'])

    def owner_left(self, source):
        for row in self.db.execute('SELECT uni FROM calls WHERE source=? AND ended IS NULL',(source,)).fetchall():
            self.disappeared(source,row['uni'])

    def listing(self, limit=20, missed=False):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('History limit must be 1..100')
        where = "WHERE result='missed'" if missed else ''
        return [dict(row) for row in self.db.execute(
            'SELECT * FROM calls '+where+' ORDER BY id DESC LIMIT ?', (limit,))]

    def acknowledge(self, ids):
        if len(ids)>100 or any(type(i) is not int or i<=0 for i in ids):
            raise ValueError('Invalid call-history selection')
        with self.db:
            for ident in ids:
                self.db.execute('UPDATE calls SET unread=0 WHERE id=?',(ident,))

    def import_missed_test(self, source, number, started, ended):
        """Only for a separately verified operator test; clearly label its origin."""
        if not source.startswith('operator-test:') or not 0 < started <= ended:
            raise ValueError('Invalid operator-test evidence')
        with self.db:
            self.db.execute('''INSERT OR IGNORE INTO calls
              (source,uni,number,direction,started,ended,result,last_state,evidence,unread)
              VALUES (?,'cancel',?,'incoming',?,?,'missed','terminated','test-report',1)''',
              (source,caller_label(number),started,ended))
