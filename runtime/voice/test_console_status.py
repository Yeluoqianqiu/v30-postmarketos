# SPDX-License-Identifier: GPL-3.0-only
import re
import unittest
from console_status import (MODEM, GPP, cellular_from_objects, operator_label,
                            technology, signal_label, speaker_from_text, format_rows, compact_rows)


class ConsoleStatusTests(unittest.TestCase):
    def objects(self, **changes):
        modem = {'State': 11, 'AccessTechnologies': 1 << 14, 'SignalQuality': (65, True)}
        modem.update(changes)
        return {'/modem/0': {MODEM: modem, GPP: {'RegistrationState': 1,
                                               'OperatorName': 'CHINA UNICOM'}}}

    def test_current_radio_not_supported_modes_or_offline_last_technology(self):
        value = cellular_from_objects(self.objects())
        self.assertEqual((value['operator'], value['network'], value['signal']),
                         ('UNICOM', '4G LTE', '|||. 65%'))
        self.assertEqual(cellular_from_objects(self.objects(State=3))['network'], 'NO SERVICE')
        self.assertEqual(technology(1 << 15), '5G NR')
        self.assertEqual(technology((1 << 15) | (1 << 14)), '5G NR/LTE')
        self.assertEqual(technology(1 << 5), '3G')
        self.assertEqual(technology(1 << 4), '2G')
        self.assertEqual(technology(0xffffffff), '--')

    def test_registration_unknown_and_multiple_modems(self):
        objects = self.objects()
        objects['/modem/0'][GPP]['RegistrationState'] = 2
        self.assertEqual(cellular_from_objects(objects)['network'], 'SEARCH')
        objects['/modem/0'][GPP]['RegistrationState'] = 5
        self.assertTrue(cellular_from_objects(objects)['roaming'])
        objects['/modem/1'] = objects['/modem/0']
        self.assertFalse(cellular_from_objects(objects)['registered'])
        self.assertEqual(cellular_from_objects({})['operator'], '--')

    def test_signal_zero_stale_and_invalid_are_distinct(self):
        self.assertEqual(signal_label((0, True)), '.... 0%')
        self.assertEqual(signal_label((100, True)), '|||| 100%')
        self.assertEqual(signal_label((90, False)), '|||| 90% STALE')
        for value in (None, (101, True), (-1, True), (True, True), (10, 1)):
            self.assertEqual(signal_label(value), '???? --')

    def test_network_names_cannot_inject_tmux_or_console_controls(self):
        self.assertEqual(operator_label('\u4e2d\u56fd\u8054\u901a'), 'UNICOM')
        self.assertEqual(operator_label(None), '--')
        self.assertEqual(operator_label('', '46001'), 'UNICOM')
        self.assertEqual(operator_label('', '99999'), '99999')
        self.assertEqual(operator_label('', '#(bad)'), '--')
        label = operator_label('#(touch /tmp/no)#[fg=red]\n\x1b[2J')
        self.assertNotRegex(label, r'[#\[\]\x00-\x1f]')
        self.assertLessEqual(len(label), 16)

    def test_speaker_fraction_and_multichannel_readback(self):
        text = "; type=INTEGER,access=rw---R--,values=1,min=0,max=15,step=0\n  : values=8\n"
        self.assertEqual(speaker_from_text(text), '53%')
        self.assertEqual(speaker_from_text(text.replace('values=8', 'values=0,15')), '0/100%')
        for invalid in ('', text.replace('values=8', 'values=16'), text.replace('max=15', 'max=0')):
            self.assertEqual(speaker_from_text(invalid), '--')

    def test_rows_never_wrap_even_at_small_widths(self):
        items = [('CELL', 'A'*16+' ROAM'), ('NET', 'NO SERVICE'), ('SIG', '???? 100% STALE')]
        for columns in (1, 10, 30, 60, 89, 90, 120):
            plain, styled = format_rows(columns, items)
            self.assertEqual(len(plain), columns)
            self.assertEqual(re.sub(r'#\[[^]]*\]', '', styled), plain)

    def test_compact_landscape_retains_metrics_and_notifications_in_two_rows(self):
        from console_icons import SLOTS, icon
        values={'capacity':'92','state':'DISCHG','battery_temp':'25.5\u2103','clock':'19:20',
                'cellular':{'network':'4G LTE','signal':'|||| 86% STALE'},'carrier':'UNICOM',
                'wifi':'UP','bluetooth':'OFF','speaker':'53%','ring':'100%',
                'notifications':{'missed':3,'sms':0},'cpu':'3%','cpu_temp':'32\u2103',
                'gpu':'SLEEP','gpu_temp':'29\u2103','ram':'0.7/3.5G','disk':'5.3/112G'}
        for icons in (False,True):
            rows=compact_rows(values,120,icons)
            self.assertEqual(len(rows),2)
            plain=' '.join(p for p,f in rows)
            for text in ['92','25.5\u2103','19:20','4G','86% STALE','53',
                         '100','3%','32\u2103','SLEEP','29\u2103','0.7/3.5G','5.3/112G']:
                self.assertIn(text,plain)
            if icons:
                self.assertIn(icon('missed')+'3',plain)
                self.assertIn(icon('sms')+'0',plain)
                self.assertIn(icon('unicom'),plain)
            self.assertIn('WiFi:ON BT:OFF',plain)
            self.assertNotIn('92%',plain)
            self.assertNotIn('53%',plain)
            self.assertNotIn('100%',plain)
            self.assertTrue(all(len(p)==120 for p,f in rows))
        self.assertEqual({slot for slots in SLOTS.values() for slot in slots},set(range(1,31)))


if __name__ == '__main__':
    unittest.main()
