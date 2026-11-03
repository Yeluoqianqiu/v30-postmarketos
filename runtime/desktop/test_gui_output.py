# SPDX-License-Identifier: GPL-3.0-only
"""Offline output selection/configuration tests; never starts a GUI or seat."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


HERE=Path(__file__).resolve().parent
loader=importlib.machinery.SourceFileLoader('v30_gui',str(HERE/'v30-gui'))
spec=importlib.util.spec_from_loader(loader.name,loader)
gui=importlib.util.module_from_spec(spec)
loader.exec_module(gui)


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.drm=self.root/'drm'
        self.drm.mkdir()
        self.connector('card0-DSI-1','connected','1440x2880\n')

    def connector(self,name,status,modes=''):
        path=self.drm/name
        path.mkdir(exist_ok=True)
        (path/'status').write_text(status+'\n')
        (path/'modes').write_text(modes)
        return path

    def test_auto_retains_internal_when_dp_absent_or_disconnected(self):
        self.assertEqual(gui.parse_args(['start']).output,'auto')
        for dp in (None,'disconnected'):
            if dp:self.connector('card0-DP-1',dp,'1920x1080\n')
            plan=gui.output_plan('auto',self.drm)
            self.assertEqual((plan['connector'],plan['geometry'],plan['gtk_scale']),
                             ('DSI-1','1440x2880',2))

    def test_auto_selects_dp_but_explicit_internal_stays_internal(self):
        self.connector('card0-DP-1','connected','3840x2160\n1920x1080\n')
        plan=gui.output_plan('auto',self.drm)
        self.assertEqual((plan['output'],plan['mode'],plan['geometry'],plan['gtk_scale']),
                         ('external','1920x1080@60','1920x1080',1))
        self.assertEqual(gui.output_plan('internal',self.drm)['connector'],'DSI-1')

    def test_external_refuses_absent_or_disconnected(self):
        with self.assertRaisesRegex(RuntimeError,'No connected'):
            gui.output_plan('external',self.drm)
        self.connector('card0-DP-1','disconnected','1920x1080\n')
        with self.assertRaisesRegex(RuntimeError,'No connected'):
            gui.output_plan('external',self.drm)

    def test_stale_mode_cache_keeps_fixed_cea_configuration_and_shell_values(self):
        # A connected sink may expose only stale fallback modes until a native
        # DRM GETCONNECTOR probes it. Do not reject before Weston can probe.
        dp=self.connector('card0-DP-1','connected','1280x1024\n')
        self.connector('card0-HDMI-A-1','connected','1920x1080\n')
        plan=gui.output_plan('auto',self.drm)
        runtime=self.root/'run'
        runtime.mkdir()
        gui.write_output_configuration(runtime,plan,HERE/'weston.ini')
        config=(runtime/'weston.ini').read_text()
        sections=[dict(line.split('=',1) for line in part.splitlines() if '=' in line)
                  for part in config.split('[output]\n')[1:]]
        self.assertEqual({section['name']:section['mode'] for section in sections},
                         {'DP-1':'148.500 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync',
                          'DSI-1':'off','HDMI-A-1':'off'})
        self.assertNotIn('mode=preferred',config)
        self.assertNotIn('3840x2160',config)
        self.assertIn('pixman-shadow=true',config)
        # Source the same root-written values that greetd's session will consume.
        resolved=subprocess.check_output(['sh','-c',
            '. "$1"; printf "%s\\n" "$V30_GUI_OUTPUT" "$V30_GUI_DRM_DEVICE" "$V30_GUI_GEOMETRY" "$GDK_SCALE"',
            'sh',str(runtime/'session.env')],text=True)
        self.assertEqual(resolved,'external\ncard0\n1920x1080\n1\n')
        for name in ('weston.ini','session.env'):
            self.assertEqual((runtime/name).stat().st_mode&0o777,0o644)
        self.assertTrue(gui.connected(dp))
        (dp/'status').write_text('disconnected\n')
        self.assertFalse(gui.connected(dp))
        (dp/'status').unlink()
        self.assertFalse(gui.connected(dp))

    def test_internal_configuration_disables_dp_and_preserves_scale(self):
        self.connector('card0-DP-1','connected','1920x1080\n')
        plan=gui.output_plan('internal',self.drm)
        gui.write_output_configuration(self.root,plan,HERE/'weston.ini')
        config=(self.root/'weston.ini').read_text()
        self.assertIn('name=DP-1\nmode=off\n',config)
        self.assertIn('name=DSI-1\nmode=preferred\ntransform=normal\nscale=1\n',config)
        self.assertIn('export GDK_SCALE=2\n',(self.root/'session.env').read_text())

    def test_ambiguous_connectors_and_invalid_cli_are_rejected(self):
        self.connector('card0-DP-1','connected','1920x1080\n')
        self.connector('card1-DP-1','connected','1920x1080\n')
        with self.assertRaisesRegex(RuntimeError,'Ambiguous'):
            gui.output_plan('auto',self.drm)
        for argv in (['start','--output','4k'],['stop','--output','external'],
                     ['status','--output','internal']):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:gui.parse_args(argv)
            self.assertEqual(error.exception.code,2)

    def test_external_checks_live_touch_mapping_without_changing_devices(self):
        inputs=self.root/'input'
        event=inputs/'event3'
        (event/'device').mkdir(parents=True)
        (event/'device/name').write_text('stmfts\n')
        unrelated=inputs/'event4'
        (unrelated/'device').mkdir(parents=True)
        (unrelated/'device/name').write_text('USB mouse\n')
        with mock.patch.object(gui.subprocess,'check_output',return_value='ID_INPUT_TOUCHSCREEN=1\n') as query:
            with self.assertRaisesRegex(RuntimeError,'WL_OUTPUT'):
                gui.check_external_touch_mapping(inputs)
            query.assert_called_once_with(['udevadm','info','--query=property','--path='+str(event)],text=True,timeout=5)
        with mock.patch.object(gui.subprocess,'check_output',return_value='WL_OUTPUT=DSI-1\n') as query:
            gui.check_external_touch_mapping(inputs)
            self.assertEqual(query.call_count,1)

    def test_controller_disconnect_uses_existing_cleanup_and_tty_return(self):
        dp=self.connector('card0-DP-1','connected','1920x1080\n')
        plan=gui.output_plan('external',self.drm)
        runtime=self.root/'runtime'
        tty=self.root/'active-tty'
        tty.write_text('tty1\n')
        socket=self.root/'seatd.sock'
        proc=self.root/'proc'
        proc.mkdir()
        stat=self.root/'self-stat'
        stat.write_text('123 (v30-gui) '+' '.join(['0']*20)+'\n')
        processes=[]

        def mapped_path(value):
            return {'/run/v30-desktop':runtime,'/sys/class/tty/tty0/active':tty,
                    '/run/seatd.sock':socket,'/proc':proc,
                    '/proc/self/stat':stat}.get(str(value),Path(value))

        class Process:
            def __init__(self,argv,**kwargs):
                self.pid=10000+len(processes)
                self.returncode=None
                processes.append((argv,self))
                if argv[0]=='seatd':socket.write_text('')
                else:(dp/'status').write_text('disconnected\n')
            def poll(self):return self.returncode
            def terminate(self):self.returncode=-15
            def wait(self,timeout=None):return self.returncode

        original_write=gui.write_output_configuration
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(gui,'Path',side_effect=mapped_path))
            stack.enter_context(mock.patch.object(gui,'output_plan',return_value=plan))
            stack.enter_context(mock.patch.object(gui,'check_external_touch_mapping'))
            stack.enter_context(mock.patch.object(gui,'write_output_configuration',
                side_effect=lambda root,selected:original_write(root,selected,HERE/'weston.ini')))
            stack.enter_context(mock.patch.object(gui.os,'geteuid',return_value=0))
            stack.enter_context(mock.patch.object(gui.os,'umask'))
            stack.enter_context(mock.patch.object(gui.os,'chown'))
            stack.enter_context(mock.patch.object(gui.os,'open',return_value=100))
            stack.enter_context(mock.patch.object(gui.os,'close'))
            stack.enter_context(mock.patch.object(gui.pwd,'getpwnam',
                return_value=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())))
            stack.enter_context(mock.patch.object(gui.signal,'signal'))
            ioctls=stack.enter_context(mock.patch.object(gui.fcntl,'ioctl'))
            calls=stack.enter_context(mock.patch.object(gui.subprocess,'check_output',return_value='[]'))
            commands=stack.enter_context(mock.patch.object(gui.subprocess,'run'))
            stack.enter_context(mock.patch.object(gui.subprocess,'Popen',side_effect=Process))
            gui.run(gui.parse_args(['run','--output','external']))
        state=json.loads((runtime/'state.json').read_text())
        self.assertFalse(state['active'])
        self.assertEqual(state['stop_reason'],'external-disconnected')
        self.assertEqual(state['output'],'external')
        calls.assert_called_once_with(['/usr/local/sbin/v30-phone','calls'],text=True)
        self.assertEqual([argv[0] for argv,process in processes],['seatd','greetd'])
        self.assertTrue(all(process.returncode==-15 for argv,process in processes))
        self.assertEqual([call.args[1] for call in ioctls.call_args_list],
                         [0x5602,0x4b3a,0x560c,0x5606])
        self.assertEqual(commands.call_args_list[0].args[0],['/usr/local/sbin/v30-display','on'])
        self.assertEqual(commands.call_args_list[1].args[0],['/usr/local/sbin/v30-console-metrics','--force'])


if __name__=='__main__':unittest.main()
