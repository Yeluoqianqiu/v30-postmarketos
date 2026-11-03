# SPDX-License-Identifier: GPL-3.0-only
"""Private-use cells avoid ambiguous CJK widths in the Linux text console."""
SLOTS = {
    **{'battery'+str(n):(1+n,) for n in range(5)},
    **{'signal'+str(n):(6+n,) for n in range(5)},
    'unicom':(11,12,13,14), 'charge':(15,16,17,18), 'discharge':(19,20,15,16),
    'speaker':(21,22), 'ring':(23,24), 'missed':(19,20,25,26), 'sms':(27,28,29,30),
}


def icon(name):
    return ''.join(chr(0xe000+slot) for slot in SLOTS[name])
