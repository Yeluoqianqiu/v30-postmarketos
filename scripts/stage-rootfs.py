#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Stage the opt-in profile in an empty directory, without enabling services."""
import argparse,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def install(destination, imsd_build=None):
    destination=Path(destination)
    if destination.is_symlink() or destination.resolve()==Path('/'):raise ValueError('Use a new staging directory, never / or a symlink')
    if destination.exists() and any(destination.iterdir()):raise ValueError('Staging directory must be empty')
    destination.mkdir(parents=True,exist_ok=True)
    mapping={}
    def add(src,target,mode=0o755):
        mapping[target]={'source':str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else 'operator-provided imsd build','mode':oct(mode)}
        target_path=destination/target.lstrip('/');target_path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,target_path);target_path.chmod(mode)
    v=ROOT/'runtime/voice';s=ROOT/'runtime/support';sms=ROOT/'runtime/sms'
    for name in ['mobile_common.py','ims_supervisor.py','call_media.py','audio_session.py','media_helpers.py','link.py','physical.conf','gvariant_json.py','ims-pdn-up.sh']:
        add(v/name,'/opt/v30-mobile/libexec/'+name,0o755 if name in ['ims_supervisor.py','call_media.py','ims-pdn-up.sh'] else 0o644)
    for name in ['v30-ipa','v30-cellular','v30-ims']:add(v/name,'/etc/init.d/'+name)
    add(v/'v30-phone','/usr/local/sbin/v30-phone')
    add(v/'net.catcrafts.IMS1.conf','/usr/share/dbus-1/system.d/net.catcrafts.IMS1.conf',0o644)
    add(v/'net.catcrafts.IMS1.policy','/usr/share/polkit-1/actions/net.catcrafts.IMS1.policy',0o644)
    for name in ['sms_core.py','sms_bus.py','smsd.py']:add(sms/name,'/opt/v30-sms/'+name,0o755 if name=='smsd.py' else 0o644)
    add(sms/'v30-sms','/usr/local/sbin/v30-sms');add(sms/'v30-sms.init','/etc/init.d/v30-sms')
    for name,target in [('v30-charge-limit.py','v30-charge-limit'),('v30-display.py','v30-display'),('v30-power-key.py','v30-power-key'),('v30-console-metrics.py','v30-console-metrics'),('v30-console-font.py','v30-console-font'),('v30-console-login','v30-console-login'),('v30-unicom-init','v30-unicom-init'),('v30-unicom-mode','v30-unicom-mode')]:add(s/name,'/usr/local/sbin/'+target)
    for name in ['v30-charge-limit','v30-power-key','v30-console-status','v30-audio','v30-wifi','v30-modem-modules','v30-bluetooth-off']:add(s/(name+'.init'),'/etc/init.d/'+name)
    add(s/'v30-unicom-service','/etc/init.d/v30-unicom');add(s/'v30-console.conf','/etc/v30-console.conf',0o644)
    for src,target in [('v30-ims.env','/etc/v30-ims.env'),('v30-audio-compat.conf','/etc/modprobe.d/v30-audio-compat.conf'),('v30-mobile.conf','/etc/modprobe.d/v30-mobile.conf')]:add(ROOT/'examples'/src,target,0o600 if src.endswith('.env') else 0o644)
    if imsd_build:
        for name in ['imsd','imsd-pcscf','imsd-media']:add(Path(imsd_build)/name,'/opt/v30-mobile/bin/'+name)
    (destination/'STAGING-MANIFEST.json').write_text(json.dumps({'files':mapping,'services_enabled':False,'phone_connected':False,'imsd_binaries_present':bool(imsd_build)},indent=2)+'\n')
    return mapping
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path);p.add_argument('--imsd-build',type=Path);a=p.parse_args()
    print('Staged',len(install(a.destination,a.imsd_build)),'files; no services started')
