#!/usr/bin/python3
"""Read-only console status bar; cache in /run and stop updates while blanked."""
import datetime,fcntl,json,os,subprocess,sys,time,struct,termios
from pathlib import Path
RUN=Path('/run/v30-console')
RUN.mkdir(mode=0o700,exist_ok=True)

def read(path,default=''):
    try:return Path(path).read_text().strip()
    except OSError:return default

def number(path,divisor=1):
    try:return float(read(path))/divisor
    except ValueError:return None

def cmd(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=2)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None

def temp(types):
    values=[]
    for p in Path('/sys/class/thermal').glob('thermal_zone*'):
        if read(p/'type').startswith(types):
            v=number(p/'temp',1000)
            if v is not None:values.append(v)
    return f'{max(values):.0f}℃' if values else '--'

def sample(previous):
    now=time.monotonic()
    ticks=[int(v) for v in read('/proc/stat').splitlines()[0].split()[1:9]]
    total=sum(ticks);idle=sum(ticks[3:5]);old=previous.get('cpu',{})
    dt=total-old.get('total',total);di=idle-old.get('idle',idle)
    cpu=f'{max(0,min(100,100*(dt-di)/dt)):.0f}%' if dt>0 else '--'
    mem={l.split(':')[0]:int(l.split()[1]) for l in read('/proc/meminfo').splitlines() if l.startswith(('MemTotal:','MemAvailable:'))}
    ram=f"{(mem['MemTotal']-mem['MemAvailable'])/1048576:.1f}/{mem['MemTotal']/1048576:.1f}G"
    disk=os.statvfs('/');used=(disk.f_blocks-disk.f_bfree)*disk.f_frsize/(1024**3);size=disk.f_blocks*disk.f_frsize/(1024**3)
    capacity=read('/sys/class/power_supply/qcom-battery/capacity','--')
    state=read('/sys/class/power_supply/qcom-battery/status')
    state={'Discharging':'DISCHG','Charging':'CHARGE','Not charging':'HOLD','Full':'FULL'}.get(state,'UNKNOWN')
    t=number('/sys/class/power_supply/qcom-battery/temp',10)
    battery_temp=f'{t:.1f}℃' if t is not None else '--'
    bt=previous.get('bluetooth','--');bt_at=previous.get('bluetooth_at',-60)
    if now-bt_at>=30:
        info=cmd(['bluetoothctl','show'])
        if info is None:bt='--'
        elif 'Powered: yes' not in info:bt='OFF'
        else:
            connected=cmd(['bluetoothctl','devices','Connected'])
            count=sum(l.startswith('Device ') for l in connected.splitlines()) if connected is not None else None
            bt=f'ON({count})' if count is not None else 'ON'
        bt_at=now
    wifi='UP' if read('/sys/class/net/wlan0/operstate')=='up' else 'DOWN'
    gpu_state=read('/sys/bus/platform/devices/5000000.gpu/power/runtime_status')
    if gpu_state=='suspended':gpu='SLEEP'
    elif gpu_state=='active':
        freq=number('/sys/class/devfreq/5000000.gpu/cur_freq',1e6)
        gpu=f'{freq:.0f}MHz' if freq is not None else 'ACTIVE'
    else:gpu='--'
    uptime=float(read('/proc/uptime','0').split()[0]);hours=int(uptime//3600);minutes=int(uptime%3600//60)
    with open('/dev/tty1','rb',buffering=0) as terminal:
        rows,columns,_,_=struct.unpack('HHHH',fcntl.ioctl(terminal,termios.TIOCGWINSZ,bytes(8)))
    clock=datetime.datetime.now().strftime('%H:%M')
    def cell(label,value,width,color='cyan'):
        plain=f'{label} {value}' if label else value
        space=max(0,width-len(plain));left=' '*(space//2);right=' '*(space-space//2)
        styled=left+f'#[fg=white,nobold]{label+" " if label else ""}#[fg={color},nobold]{value}#[fg=white,nobold]'+right
        return left+plain+right,styled
    def row(items):
        # Allow for rounded corners: four cells (96px) per side in landscape, three in portrait.
        margin=4 if columns>=90 else 3
        width=max(1,(columns-2*margin-3*(len(items)-1))//len(items))
        cells=[cell(*item,width) for item in items]
        plain=' │ '.join(p for p,f in cells)
        styled=' #[fg=blue,nobold]│ '.join(f for p,f in cells)
        spare=max(0,columns-len(plain));left=' '*(spare//2);right=' '*(spare-spare//2)
        return left+plain+right,left+styled+right
    if columns>=90:
        pairs=[row([('BAT',f'{capacity}% {state} {battery_temp}'),('BT',bt),('WiFi',wifi),('',clock)]),
               row([('CPU',f'{cpu} {temp(("cpu","clust"))}'),('GPU',f'{gpu} {temp(("gpu-",))}'),('RAM',ram),('SD',f'{used:.1f}/{size:.0f}G')])]
    else:
        pairs=[row([('BAT',f'{capacity}% {state}'),('TEMP',battery_temp+'  '+clock)]),
               row([('CPU',f'{cpu}  {temp(("cpu","clust"))}'),('GPU',f'{gpu}  {temp(("gpu-",))}')]),
               row([('RAM',ram),('SD',f'{used:.1f}/{size:.0f}G')]),
               row([('BT',bt),('WiFi',wifi+f'  {hours}h{minutes:02}')])]
    lines=[p for p,f in pairs];formats=[f for p,f in pairs]
    return {'sampled_at':now,'cpu':{'total':total,'idle':idle},'bluetooth':bt,'bluetooth_at':bt_at,'lines':lines,'formats':formats}

def visible():
    return read('/sys/class/graphics/fb0/blank')=='0' and read('/run/v30-display/requested')!='off'

def refresh():
    with (RUN/'metrics.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:previous=json.loads((RUN/'metrics.json').read_text())
        except (OSError,ValueError):previous={}
        if not visible():return previous
        if previous and time.monotonic()-previous.get('sampled_at',0)<4:return previous
        result=sample(previous)
        pending=RUN/'metrics.tmp';pending.write_text(json.dumps(result));pending.replace(RUN/'metrics.json')
        if (RUN/'tmux.sock').exists():
            args=['tmux','-S',str(RUN/'tmux.sock'),'set-option','-g','status',str(len(result['lines']))]
            for i,line in enumerate(result['formats']):
                args.append(';')
                args.extend(['set-option','-g',f'status-format[{i}]',line.replace('%','%%')])
            display=Path('/run/v30-display');display.mkdir(mode=0o700,exist_ok=True)
            with (display/'control.lock').open('a') as display_lock:
                fcntl.flock(display_lock,fcntl.LOCK_EX)
                if visible():
                    subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
        return result

if __name__=='__main__':
    daemon='--daemon' in sys.argv
    while True:
        try:
            result=refresh()
            if not daemon:print(json.dumps(result,ensure_ascii=False))
        except (OSError,ValueError,KeyError,IndexError,subprocess.TimeoutExpired) as error:
            print('status refresh: '+str(error),file=sys.stderr,flush=True)
        if not daemon:break
        time.sleep(5)
