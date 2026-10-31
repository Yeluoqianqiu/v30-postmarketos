#!/usr/bin/python3
"""Linux 运行时的充电保护：80% 停充，75% 恢复；保留硬件保护。"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import time

CHARGER = Path('/sys/class/power_supply/pmi8998-charger')
BATTERY = Path('/sys/class/power_supply/qcom-battery')
STATE = Path('/var/lib/v30-charge-limit/state.json')


def decide(capacity, temp, health, previous, thermal_hold):
    """温度单位为 0.1°C；读数异常时停充，不绕过硬件保护。"""
    if not 0 <= capacity <= 100 or not -400 <= temp <= 1000:
        return 'inhibit-charge', True, 'invalid-sensor'
    if health != 'Good':
        return 'inhibit-charge', thermal_hold, 'charger-health'
    thermal_hold = (temp >= 400 or temp <= 50 or
                    (thermal_hold and not 70 <= temp <= 370))
    if thermal_hold:
        return 'inhibit-charge', True, 'temperature'
    if capacity >= 80:
        return 'inhibit-charge', False, 'upper-threshold'
    if capacity <= 75:
        return 'auto', False, 'lower-threshold'
    return (previous if previous in ('auto', 'inhibit-charge') else 'inhibit-charge'), False, 'hysteresis'


def read_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def active_mode():
    words = (CHARGER / 'charge_behaviour').read_text().split()
    selected = [word[1:-1] for word in words if word.startswith('[') and word.endswith(']')]
    if len(selected) != 1:
        raise ValueError('Unrecognised charge_behaviour response')
    return selected[0]


def step():
    prior = read_state()
    try:
        capacity = int((BATTERY / 'capacity').read_text())
        temp = int((BATTERY / 'temp').read_text())
        health = (CHARGER / 'health').read_text().strip()
        desired, thermal, reason = decide(capacity, temp, health, prior.get('desired'), prior.get('thermal_hold', False))
    except (OSError, ValueError):
        desired, thermal, reason = 'inhibit-charge', True, 'sensor-read-error'
    actual = active_mode()
    if actual != desired:
        (CHARGER / 'charge_behaviour').write_text(desired + '\n')
        if active_mode() != desired:
            raise RuntimeError('Charge control readback mismatch')
    state = {'desired': desired, 'thermal_hold': thermal, 'reason': reason,
             'start_percent': 75, 'stop_percent': 80}
    previous_state = {key: prior.get(key) for key in state}
    if state != previous_state or actual != desired:
        state['changed_at'] = datetime.datetime.now().astimezone().isoformat()
        STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        pending = STATE.with_suffix('.tmp')
        pending.write_text(json.dumps(state, ensure_ascii=False) + '\n')
        pending.replace(STATE)
        print(json.dumps(state, ensure_ascii=False), flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        result = read_state()
        result['actual_mode'] = active_mode()
        result['capacity'] = int((BATTERY / 'capacity').read_text())
        result['temperature_c'] = int((BATTERY / 'temp').read_text()) / 10
        result['external_power_online'] = (CHARGER / 'online').read_text().strip()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (STATE.parent / "controller.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    while True:
        try:
            step()
        except (OSError, ValueError, RuntimeError) as error:
            print('charge-limit error: ' + str(error), flush=True)
            if args.once:
                raise
        if args.once:
            return
        time.sleep(15)


if __name__ == '__main__':
    main()
