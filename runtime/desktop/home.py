#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Small touch launcher and Unicode scratchpad for an optional graphical session."""
from pathlib import Path
import subprocess,os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib


def activate(app):
    window=Gtk.ApplicationWindow(application=app,title='V30 Linux')
    window.set_default_size(720,1440)
    window.set_decorated(False)
    window.maximize()
    outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
    outer.set_margin_top(16);outer.set_margin_bottom(16)
    outer.set_margin_start(20);outer.set_margin_end(20)
    toolbar=Gtk.Box(spacing=12)
    title=Gtk.Label(label='V30 Linux',xalign=0)
    title.add_css_class('title-2');outer.append(title)
    terminal=Gtk.Button(label='Terminal')
    terminal.connect('clicked',lambda button:subprocess.Popen(['xterm','-u8','-fa','monospace','-fs','28','-geometry','120x20+0+0'] if os.environ.get('V30_GUI_BACKEND')=='x11-fbdev' else ['foot','--config=/etc/v30-desktop/foot.ini']))
    toolbar.append(terminal)
    keyboard=Gtk.Button(label='Keyboard')
    keyboard.connect('clicked',lambda button:subprocess.Popen(
        ['gdbus','call','--session','--dest','org.onboard.Onboard',
         '--object-path','/org/onboard/Onboard/Keyboard','--method','org.onboard.Onboard.Keyboard.Show']
        if os.environ.get('V30_GUI_BACKEND')=='x11-fbdev' else
        ['gdbus','call','--session','--dest','sm.puri.OSK0','--object-path','/sm/puri/OSK0',
         '--method','sm.puri.OSK0.SetVisible','true'],stdout=subprocess.DEVNULL))
    toolbar.append(keyboard)
    leave=Gtk.Button(label='Return to TTY')
    leave.connect('clicked',lambda button:window.close());toolbar.append(leave)
    outer.append(toolbar)
    notebook=Gtk.Notebook();notebook.set_vexpand(True)
    note=Gtk.TextView();note.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    note.set_top_margin(12);note.set_bottom_margin(12)
    note.set_left_margin(12);note.set_right_margin(12)
    # The user edits a scratchpad, never a shell command or SMS composer.
    path=Path.home()/'.local/share/v30-desktop/note.txt'
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.exists():note.get_buffer().set_text(path.read_text())
    scroll=Gtk.ScrolledWindow();scroll.set_child(note)
    notebook.append_page(scroll,Gtk.Label(label='Notes / Chinese input'))
    info=Gtk.Label(label='Manual graphical session\n\nTouch a text field to open the keyboard.\nUse the globe key for Pinyin and select Chinese mode.\nClose Terminal with exit to return here.\nReturn to TTY ends this session.\n\nCellular/IMS/SMS services continue independently.\nBluetooth remains off.\nGraphical audio is disabled for this profile.',xalign=0,yalign=0)
    info.set_margin_top(16);info.set_margin_start(12)
    notebook.append_page(info,Gtk.Label(label='Session'))
    outer.append(notebook);window.set_child(outer)
    css=Gtk.CssProvider();css.load_from_string('window {background: #141b26; color: #eef3fa;} button {min-height: 38px; padding: 4px 14px;} textview, textview text {background: #202b3b; color: #eef3fa;}')
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    settings=Gtk.Settings.get_default();settings.set_property('gtk-application-prefer-dark-theme',True)
    def save_and_close(widget):
        buffer=note.get_buffer();path.write_text(buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True));path.chmod(0o600)
        (Path(os.environ['XDG_RUNTIME_DIR'])/'session-ended').touch(mode=0o600)
        app.quit()
        return False
    window.connect('close-request',save_and_close)
    window.present()


app=Gtk.Application(application_id='org.v30.Desktop')
app.connect('activate',activate)
raise SystemExit(app.run())
