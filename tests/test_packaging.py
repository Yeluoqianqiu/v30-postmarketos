# SPDX-License-Identifier: GPL-3.0-only
import gzip,importlib.util,json,struct,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
boot=load('boot','scripts/repack-boot.py');stage=load('stage','scripts/stage-rootfs.py')
class PackagingTests(unittest.TestCase):
    def fixture(self):
        header=bytearray(4096);header[:8]=b'ANDROID!';struct.pack_into('<10I',header,8,5,0x8000,7,0x2000000,0,0,0x100,4096,0,0)
        header[64:70]=b'rotate';header[1800:1810]=b'KEEPHEADER'
        return bytes(header)+b'old-k'+bytes(4096-5)+b'RAMDISK'+bytes(4096-7)
    def kernel(self):
        raw=bytearray(1024);raw[56:60]=b'ARM\x64';struct.pack_into('<Q',raw,16,1024);return gzip.compress(raw)
    def dtb(self):
        data=bytearray(40);data[:4]=b'\xd0\x0d\xfe\xed';struct.pack_into('>I',data,4,40);return bytes(data)
    def test_preserves_owner_ramdisk_and_unrelated_header(self):
        result=boot.repack(self.fixture(),self.kernel(),self.dtb())
        self.assertIn(b'RAMDISK',result);self.assertEqual(result[1800:1810],b'KEEPHEADER');self.assertEqual(result[64:70],b'rotate');self.assertNotEqual(result[576:596],bytes(20))
    def test_rejects_truncation_other_formats_and_placeholder_cmdline(self):
        b=self.fixture()
        for bad in [b[:-1],b+b'APPENDED',b'bad',b[:40]+struct.pack('<I',1)+b[44:]]:
            with self.assertRaises(ValueError):boot.repack(bad,self.kernel(),self.dtb())
        with self.assertRaises(ValueError):boot.repack(b,self.kernel(),self.dtb(),'pmos_root_uuid=YOUR_ROOT_FS_UUID')
    def test_staging_never_enables_services_and_refuses_nonempty_or_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'root';files=stage.install(dest)
            self.assertIn('/etc/init.d/v30-sms',files);self.assertIn('/etc/init.d/v30-ims',files)
            self.assertIn('/etc/init.d/v30-incoming',files)
            self.assertIn('/opt/v30-mobile/libexec/alert_view.py',files)
            self.assertIn('/opt/v30-mobile/libexec/console_status.py',files)
            self.assertIn('/opt/v30-mobile/libexec/console_icons.py',files)
            self.assertIn('/opt/v30-mobile/libexec/console-glyphs.json',files)
            self.assertNotIn('/usr/local/sbin/v30-gui',files)
            self.assertIn('/opt/v30-mobile/libexec/call_history.py',files)
            self.assertEqual((dest/'etc/v30-incoming.json').stat().st_mode&0o777,0o600)
            self.assertEqual((dest/'opt/v30-mobile/libexec/incoming_alerts.py').stat().st_mode&0o777,0o755)
            self.assertFalse((dest/'etc/runlevels').exists());self.assertFalse((dest/'etc/inittab').exists());self.assertFalse((dest/'opt/v30-mobile/bin/imsd').exists())
            self.assertEqual((dest/'usr/local/sbin/v30-phone').stat().st_mode&0o777,0o755)
            graphical=Path(d)/'manual-desktop';desktop_files=stage.install(graphical,desktop=True)
            self.assertIn('/usr/local/sbin/v30-gui',desktop_files)
            self.assertIn('/opt/v30-desktop/x11-session.sh',desktop_files)
            self.assertIn('/opt/v30-desktop/x11-home.py',desktop_files)
            self.assertIn('/opt/v30-desktop/fb-refresh.py',desktop_files)
            self.assertIn('/opt/v30-desktop/weston-session.sh',desktop_files)
            self.assertIn('/opt/v30-desktop/weston-x11.sh',desktop_files)
            self.assertIn('/etc/v30-desktop/weston.ini',desktop_files)
            self.assertIn('/etc/v30-desktop/xorg.conf',desktop_files)
            self.assertIn('/etc/v30-desktop/uim.scm',desktop_files)
            self.assertIn('/etc/v30-desktop/gtk-3.0/settings.ini',desktop_files)
            self.assertIn('/opt/v30-desktop/weston-session.sh',(graphical/'etc/v30-desktop/greetd.toml').read_text())
            self.assertFalse((graphical/'etc/greetd/config.toml').exists())
            self.assertFalse((graphical/'etc/runlevels').exists())
            with self.assertRaises(ValueError):stage.install(dest)
            link=Path(d)/'alias';link.symlink_to(dest)
            with self.assertRaises(ValueError):stage.install(link)
if __name__=='__main__':unittest.main()
