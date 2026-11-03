#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Small touch launcher and Unicode scratchpad for an optional graphical session."""
from pathlib import Path
import subprocess,os,ctypes
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk


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
    title.get_style_context().add_class('title-2');outer.pack_start(title,False,False,0)
    terminal=Gtk.Button(label='Terminal')
    terminal.connect('clicked',lambda button:subprocess.Popen(['xterm','-u8','-fa','monospace','-fs','20','-geometry','62x28+0+0']))
    terminal.set_can_focus(False);toolbar.pack_start(terminal,False,False,0)
    keyboard=Gtk.Button(label='Keyboard')
    keyboard.connect('clicked',lambda button:subprocess.Popen(
        ['gdbus','call','--session','--dest','org.onboard.Onboard',
         '--object-path','/org/onboard/Onboard/Keyboard','--method','org.onboard.Onboard.Keyboard.Show'],stdout=subprocess.DEVNULL))
    keyboard.set_can_focus(False);toolbar.pack_start(keyboard,False,False,0)
    leave=Gtk.Button(label='Return to TTY')
    leave.connect('clicked',lambda button:window.close());toolbar.pack_start(leave,False,False,0)
    language=Gtk.Button(label='\u4e2d\u6587 / EN')
    language.set_can_focus(False)
    def toggle_pinyin(button):
        note.grab_focus()
        # Send the same configured toggle to the focused input context.
        x=ctypes.CDLL('libX11.so.6');test=ctypes.CDLL('libXtst.so.6')
        x.XOpenDisplay.argtypes=[ctypes.c_char_p];x.XOpenDisplay.restype=ctypes.c_void_p
        x.XKeysymToKeycode.argtypes=[ctypes.c_void_p,ctypes.c_ulong];x.XKeysymToKeycode.restype=ctypes.c_uint
        x.XFlush.argtypes=[ctypes.c_void_p];x.XCloseDisplay.argtypes=[ctypes.c_void_p]
        test.XTestFakeKeyEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
        display=x.XOpenDisplay(None);assert display,'X11 input connection failed'
        control=x.XKeysymToKeycode(display,0xffe3);space=x.XKeysymToKeycode(display,0x20)
        for key,pressed in [(control,1),(space,1),(space,0),(control,0)]:
            test.XTestFakeKeyEvent(display,key,pressed,0)
        x.XFlush(display);x.XCloseDisplay(display)
    language.connect('clicked',toggle_pinyin);toolbar.pack_start(language,False,False,0)
    toolbar.reorder_child(language,2)
    outer.pack_start(toolbar,False,False,0)
    notebook=Gtk.Notebook();notebook.set_vexpand(True)
    note=Gtk.TextView();note.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    note.set_top_margin(12);note.set_bottom_margin(12)
    note.set_left_margin(12);note.set_right_margin(12)
    # The user edits a scratchpad, never a shell command or SMS composer.
    path=Path.home()/'.local/share/v30-desktop/note.txt'
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.exists():note.get_buffer().set_text(path.read_text())
    scroll=Gtk.ScrolledWindow();scroll.add(note)
    notebook.append_page(scroll,Gtk.Label(label='Notes / Chinese input'))
    info=Gtk.Label(label='Manual graphical session\n\nUse Keyboard to show the on-screen keys.\nUse the Chinese / EN button or Ctrl+Space for Pinyin.\nEnter nihao and press Return for the default characters.\nClose Terminal with exit to return here.\nReturn to TTY ends this session.\n\nCellular/IMS/SMS services continue independently.\nBluetooth remains off.\nGraphical audio is disabled for this profile.',xalign=0,yalign=0)
    info.set_margin_top(16);info.set_margin_start(12)
    notebook.append_page(info,Gtk.Label(label='Session'))
    outer.pack_start(notebook,True,True,0);window.add(outer)
    css=Gtk.CssProvider();css.load_from_data(b'window {background: #141b26; color: #eef3fa;} button {min-height: 38px; padding: 4px 14px;} textview, textview text {background: #202b3b; color: #eef3fa;}')
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    settings=Gtk.Settings.get_default();settings.set_property('gtk-application-prefer-dark-theme',True)
    def save_and_close(widget):
        buffer=note.get_buffer();path.write_text(buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True));path.chmod(0o600)
        (Path(os.environ['XDG_RUNTIME_DIR'])/'session-ended').touch(mode=0o600)
        app.quit()
        return False
    window.connect('delete-event',lambda widget,event:save_and_close(widget))
    window.show_all();window.present();note.grab_focus()


app=Gtk.Application(application_id='org.v30.Desktop')
app.connect('activate',activate)
raise SystemExit(app.run())
