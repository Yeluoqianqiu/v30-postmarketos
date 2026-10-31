#!/usr/bin/python3
"""专用电源键短按切换屏幕；不更改限充、服务器唤醒或系统关机。"""
import fcntl,json,os,select,struct,subprocess,time
from pathlib import Path
EVENT=struct.Struct('llHHi');EVIOCGRAB=0x40044590

def log(message):
    record={'time':time.strftime('%Y-%m-%dT%H:%M:%S%z'),**message}
    p=Path('/run/v30-display/key-last.json');p.parent.mkdir(mode=0o700,exist_ok=True)
    p.write_text(json.dumps(record)+'\n')
    print(json.dumps(record),flush=True)

while True:
    fd=None
    try:
        matches=[p for p in Path('/sys/class/input').glob('event*') if (p/'device/name').read_text().strip()=='pm8941_pwrkey']
        if len(matches)!=1:raise OSError('Expected one pm8941_pwrkey event device')
        fd=os.open('/dev/input/'+matches[0].name,os.O_RDONLY|os.O_NONBLOCK)
        # 只独占电源键，避免 VT 将同一次按键当作自动亮屏再触发一次翻转。
        fcntl.ioctl(fd,EVIOCGRAB,1)
        log({'state':'listening','device':matches[0].name})
        pressed=None;last_toggle=0
        while True:
            readable,_,_=select.select([fd],[],[],1)
            if not readable:continue
            data=os.read(fd,EVENT.size*64)
            if not data:raise OSError('Input device closed')
            for offset in range(0,len(data),EVENT.size):
                seconds,micros,kind,code,value=EVENT.unpack_from(data,offset)
                if kind!=1 or code!=116:continue
                now=time.monotonic()
                if value==1:pressed=seconds+micros/1e6
                elif value==0 and pressed is not None:
                    duration=seconds+micros/1e6-pressed;pressed=None
                    if .02<=duration<=1.5 and now-last_toggle>=.6:
                        before=Path('/sys/class/graphics/fb0/blank').read_text().strip()
                        subprocess.run(['/usr/local/sbin/v30-display','toggle'],check=True,timeout=5)
                        after=Path('/sys/class/graphics/fb0/blank').read_text().strip();last_toggle=now
                        log({'state':'toggled','duration':round(duration,3),'before':before,'after':after})
                    else:log({'state':'ignored-hold-or-bounce','duration':round(duration,3)})
    except (OSError,subprocess.SubprocessError) as error:
        log({'state':'retry','error':str(error)})
    finally:
        if fd is not None:os.close(fd)
    time.sleep(3)
