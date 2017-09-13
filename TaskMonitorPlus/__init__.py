# -*- coding: utf-8 -*-
#
# This file is a plugin for EventGhost.
# Copyright © 2005-2016 EventGhost Project <http://www.eventghost.org/>
#
# EventGhost is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# EventGhost is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with EventGhost. If not, see <http://www.gnu.org/licenses/>.

import eg

eg.RegisterPlugin(
    name = "Task Monitor Plus",
    author = (
        "Bitmonster",
        "blackwind",
        "Boolean263",
        "kgschlosser",
    ),
    version = "0.0.5",
    url = 'https://github.com/Boolean263/EventGhost-TaskMonitorPlus',
    guid = "{4826ED71-64DE-496A-84A4-955402DEC3BC}",
    createMacrosOnAdd=True,
    canMultiLoad=False,
    description = ("""
<p>Generates events when an application starts, exits, flashes the
taskbar, or gets switched into focus. Events carry a payload with
information about the window that generated them.</p>

<p>Events generated:</p>
<ul>
<li>TaskMonitorPlus.Created.<i>ExeName</i> : new process</li>
<li>TaskMonitorPlus.Destroyed.<i>ExeName</i> : process ended</li>
<li>TaskMonitorPlus.NewWindow.<i>ExeName</i> : new window</li>
<li>TaskMonitorPlus.ClosedWindow.<i>ExeName</i> : closed window</li>
<li>TaskMonitorPlus.Activated.<i>ExeName</i> : window activated (selected)</li>
<li>TaskMonitorPlus.Deactivated.<i>ExeName</i> : window deactivated</li>
<li>TaskMonitorPlus.Flashed.<i>ExeName</i> : window flashed</li>
<li>TaskMonitorPlus.TitleChanged.<i>ExeName</i> : window title changed</li>
</ul>

<p>All events except Created and Destroyed carry a payload with information
about the window affected. <tt>eg.result.payload</tt> has the following
attributes:</p>
<ul>
<li>title</li>
<li>window_class</li>
<li>hwnd (Windows' unique identifier for this window)</li>
<li>pid (process ID of owning process)</li>
<li>name (same as <i>ExeName</i> in the event)</li>
<li>too many methods to list here</li>
</ul>
"""),
    icon = (
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABuklEQVR42o1Sv0tCYRQ9"
        "L1FccpCEB73wVy1NjTrUPxD1lgZp0dWKaAhXxWhoyWgoIUjHBEH65RSE0CAUgWIPLAqR"
        "gkAQIQXR8nW/Z0ai6btweJfDd847934fhz8VCARkqCjTmBGra+sc67kOGQqFZIfDMVCo"
        "1WphMpng9/vxkMvi9u6e4zp/ZmStVkOpVOor1mg00Ol0CIfDKBQK/Q1isRhcLhedJpIn"
        "vHXkI+D5SUSj+0in0wMM4mSw6WqL9whLhHeCYAA/tobo9twQgxsyEMjglUj6IE7YIJxQ"
        "gk9K8DwsgTLCMjGGdvJxJibMUgJ+hUaYGWyQSCQQDO7+ZO8uo1EHn8/2v4Hb7UYmkxl4"
        "jY1GA9lsFrlcDl+fDZxfJNsGHo9H1QNiVa/XlQSiuIAp2wS466ukHNjaUauHXq+H0+n8"
        "HYPrzF+pVHriSpLUxbGHJAgCIpFIr0EqlYI0KmH6Y1o5XC6XaaFBpW+1WqhWq7BYLLRI"
        "X9ciFQNRFJHP53FoO4T3xdsTu9lsolgswm63Kz1b9tPTI6xmAVzk+Eg+PbtUvQNWstxS"
        "xHv7B+1bEBfnVd8CK6vFrIhZ/w1wBAQrC42uqQAAAABJRU5ErkJggg=="
    ),
)

import fnmatch # NOQA
from os.path import splitext

# Local imports
from eg.WinApi import GetClassName, GetTopLevelWindowList
from eg.WinApi.Dynamic import (
    BOOL, byref, DeregisterShellHookWindow, DWORD, EnumWindows,
    GA_ROOT, GetAncestor, GetShellWindow, GetWindowLong,
    GetWindowThreadProcessId, GWL_HWNDPARENT, HSHELL_WINDOWACTIVATED,
    HSHELL_WINDOWCREATED, HSHELL_WINDOWDESTROYED, HWND,
    IsWindowVisible, LPARAM, RegisterShellHookWindow, RegisterWindowMessage,
    WINFUNCTYPE, WM_APP,
)
from eg.WinApi.Utils import GetProcessName

from .ProcessInfo import ProcessInfo
from .WindowInfo import WindowInfo

ENUM_WINDOWS_PROC_TYPE = WINFUNCTYPE(BOOL, HWND, LPARAM)
EnumWindows.argtypes = [ENUM_WINDOWS_PROC_TYPE, LPARAM]

WM_SHELLHOOKMESSAGE = RegisterWindowMessage("SHELLHOOK")

# https://msdn.microsoft.com/en-us/library/windows/desktop/ms644991(v=vs.85).aspx
HSHELL_REDRAW = 6 # "The title of a window in the task bar has been redrawn."


class Text(eg.TranslatableStrings):

    class FindTitle:
        name = 'Search Window Title'
        description = (
            'Search for a specific window title or a part of the title. There '
            'are 2 wildcards that can be used "?" and "*" (without the '
            'quotes). The "?" wildcard is for a single character and the "*" '
            'is for multiple characters. This action returns the WindowInfo '
            'object or None. Either this action needs to be called before any '
            'of the other actions for this plugin, except if the event is '
            'runn the macro was triggered by this plugin.'
        )
        title_lbl = 'Title:'
        stop_macro_lbl = 'Stop macro if title not found:'

    class Flash:
        name = 'Flash Window'
        description = 'Flashes a window'
        caption_lbl = 'Flash caption label:'
        tray_lbl = 'Flash task bar icon:'
        until_active_lbl = 'Flash until activated:'
        continuous_lbl = 'Flash continuously:'
        times_lbl = 'How many times to flash:'
        speed_lbl = 'Duration between flashes:'

    class SetSize:
        name = 'Set Window Size'
        description = 'Sets the size for a window.'
        arg1_lbl = 'Width:'
        arg2_lbl = 'Height:'

    class SetPosition:
        name = 'Set Window Position'
        description = 'Sets the position for a window.'
        arg1_lbl = 'X position:'
        arg2_lbl = 'Y position:'

    class Show:
        name = 'Show Window'
        description = 'Shows a window.'
        activate_lbl = 'Activate:'
        default_lbl = 'Use window defaults:'

    class Minimize:
        name = 'Minimize Window'
        description = 'Minimizes a window.'
        activate_lbl = 'Activate:'
        force_lbl = 'Force:'

    class Restore:
        name = 'Restore Window'
        description = 'Restores a window.'
        default_lbl = 'Use window defaults:'

    class EnableKeyboardMouse:
        name = 'Enable Keyboard & Mouse for a Window'
        description = 'Enables the keyboard & mouse for a window.'

    class DisableKeyboardMouse:
        name = 'Disable Keyboard & Mouse for a  Window'
        description = 'Disables the keyboard & mouse for a window.'

    class IsActive:
        name = 'Is Window Active'
        description = 'Checks if a window is active.'

    class IsAlive:
        name = 'Is Window Alive'
        description = 'Checks if a window still exists.'

    class BringToTop:
        name = 'Bring Window to Top'
        description = 'Brings a window to the top (foremost window).'

    class IsVisible:
        name = 'Is Window Visible'
        description = 'Checks to see if a window is visible.'

    class IsKeyboardMouseEnabled:
        name = 'Is Keyboard & Mouse Enabled for a Window'
        description = (
            'Checks to see if the keyboard & mouse are enabled for a window.'
        )

    class Maximize:
        name = 'Maximize Window'
        description = 'Maximizes a window.'

    class GetRect:
        name = 'Get Window wxRect'
        description = (
            'Gets a windows\'s position and size as '
            'wx.Rect(x, y, width, height).'
        )

    class GetRectTuple:
        name = 'Get Window Rect Tuple'
        description = (
            'Gets a window\'s position and size as (x, y, width, height).'
        )

    class GetSize:
        name = 'Get Window wxSize'
        description = 'Gets a window\'s size as wx.Size(width, height).'

    class GetSizeTuple:
        name = 'Get Window Size Tuple'
        description = 'Gets a window\'s size as (width, height).'

    class GetPosition:
        name = 'Get Window wxPosition'
        description = 'Gets a window\'s position as wx.Point(x, y).'

    class GetPositionTuple:
        name = 'Get Window Position Tuple'
        description = 'Gets a window\'s position as (x, y).'

    class Hide:
        name = 'Hide Window'
        description = 'Hides a window.'

    class Destroy:
        name = 'Destroy Window'
        description = 'Destroys a window.'

    class Close:
        name = 'Close Window'
        description = 'Closes a window.'

    class GetParent:
        name = 'Get Window\'s Parent'
        description = 'Gets the window parent.'

    class Focus:
        name = 'Focus Window'
        description = 'Puts window into focus.'

    class HasFocus:
        name = 'Window Has Focus'
        description = 'Checks if a window has focus.'


class TaskMonitorPlus(eg.PluginBase):
    text = Text

    def __init__(self):
        self.AddAction(FindTitle)
        self.AddAction(BringToTop)
        self.AddAction(Flash)
        self.AddAction(Show)
        self.AddAction(Hide)
        self.AddAction(Close)
        self.AddAction(Destroy)
        self.AddAction(Maximize)
        self.AddAction(Minimize)
        self.AddAction(Restore)
        self.AddAction(SendKeystrokes)
        self.AddAction(Focus)
        self.AddAction(HasFocus)
        self.AddAction(EnableKeyboardMouse)
        self.AddAction(DisableKeyboardMouse)
        self.AddAction(IsKeyboardMouseEnabled)
        self.AddAction(IsActive)
        self.AddAction(IsAlive)
        self.AddAction(IsVisible)
        self.AddAction(SetSize)
        self.AddAction(SetPosition)
        self.AddAction(GetRectTuple)
        self.AddAction(GetSizeTuple)
        self.AddAction(GetPositionTuple)
        self.AddAction(GetRect)
        self.AddAction(GetSize)
        self.AddAction(GetPosition)
        self.AddAction(GetParent)
        self.AddEvents()

    def __start__(self, *dummyArgs):
        self.pids, self.hwnds = EnumProcesses()
        self.flashing = set()
        self.lastActivated = None
        eg.messageReceiver.AddHandler(WM_APP + 1, self.WindowGotFocusProc)
        eg.messageReceiver.AddHandler(WM_APP + 2, self.WindowCreatedProc)
        eg.messageReceiver.AddHandler(WM_APP + 3, self.WindowDestroyedProc)
        eg.messageReceiver.AddHandler(WM_SHELLHOOKMESSAGE, self.MyWndProc)
        RegisterShellHookWindow(eg.messageReceiver.hwnd)
        trayWindow = 0
        for explorerPid in [x for x in self.pids if self.pids[x].name == "explorer"]:
            for hwnd in self.pids[explorerPid].hwnds:
                if GetClassName(hwnd) == "Shell_TrayWnd":
                    trayWindow = hwnd
                    break
            if trayWindow != 0:
                break
        self.desktopHwnds = (GetShellWindow(), trayWindow)

    def __stop__(self):
        DeregisterShellHookWindow(eg.messageReceiver.hwnd)
        eg.messageReceiver.RemoveHandler(WM_SHELLHOOKMESSAGE, self.MyWndProc)
        eg.messageReceiver.RemoveHandler(WM_APP + 1, self.WindowGotFocusProc)
        eg.messageReceiver.RemoveHandler(WM_APP + 2, self.WindowCreatedProc)
        eg.messageReceiver.RemoveHandler(WM_APP + 3, self.WindowDestroyedProc)

    def CheckWindow(self, hwnd):
        hwnd2 = GetAncestor(hwnd, GA_ROOT)
        if hwnd == 0 or hwnd2 in self.desktopHwnds:
            return
        if hwnd != hwnd2:
            return
        if GetWindowLong(hwnd, GWL_HWNDPARENT):
            return
        if not IsWindowVisible(hwnd):
            return

        if hwnd in self.hwnds:
            processInfo = self.pids.get(self.hwnds[hwnd].pid, None)
            return processInfo

        pid = GetWindowPid(hwnd)
        processInfo = self.pids.get(pid, None)
        if not processInfo:
            processInfo = ProcessInfo(pid)
            self.pids[pid] = processInfo
            self.TriggerEvent("Created." + processInfo.name)

        processInfo.hwnds[hwnd] = WindowInfo(hwnd)
        self.hwnds[hwnd] = processInfo
        self.TriggerEvent("NewWindow." + processInfo.name, processInfo.hwnds[hwnd])
        return processInfo

    def MyWndProc(self, dummyHwnd, dummyMesg, wParam, lParam):
        if wParam == HSHELL_WINDOWDESTROYED:
            self.WindowDestroyedProc(None, None, lParam, None)
        elif wParam in (HSHELL_WINDOWACTIVATED, HSHELL_WINDOWCREATED, 0x8004):
            self.WindowGotFocusProc(None, None, lParam, None)
        elif wParam == HSHELL_REDRAW:
            self.WindowTitleChangedProc(None, None, lParam, None)
        elif wParam == 0x8006:
            self.WindowFlashedProc(None, None, lParam, None)
        else:
            eg.PrintDebugNotice("MyWndProc unknown wParam:: 0x{:04X}".format(wParam))
        return 1

    def WindowCreatedProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        self.CheckWindow(hwnd)

    def WindowDestroyedProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        processInfo = self.hwnds.get(hwnd, None)
        if processInfo:
            winDetails = processInfo.hwnds[hwnd]
            del processInfo.hwnds[hwnd]
            del self.hwnds[hwnd]
            pid = processInfo.pid
            if hwnd == self.lastActivated:
                self.TriggerEvent("Deactivated." + processInfo.name, winDetails)
                self.lastActivated = None
            self.TriggerEvent("ClosedWindow." + processInfo.name, winDetails)
            if len(processInfo.hwnds) == 0:
                self.TriggerEvent("Destroyed." + processInfo.name)
                self.pids.pop(pid, None)

    def WindowTitleChangedProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        processInfo = self.hwnds.get(hwnd, None)
        if processInfo:
            windowInfo = processInfo.hwnds[hwnd]
            if windowInfo and windowInfo.cached_title != windowInfo.title:
                self.TriggerEvent("TitleChanged." + processInfo.name, windowInfo)

    def WindowFlashedProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        processInfo = self.hwnds.get(hwnd, None)
        if processInfo and hwnd not in self.flashing:
            self.flashing.add(hwnd)
            self.TriggerEvent("Flashed." + processInfo.name, processInfo.hwnds[hwnd])

    def WindowGotFocusProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        thisProcessInfo = self.CheckWindow(hwnd)
        if thisProcessInfo and hwnd != self.lastActivated:
            if hwnd in self.flashing:
                self.flashing.remove(hwnd)
            if self.lastActivated:
                lastProcessInfo = self.hwnds.get(self.lastActivated, None)
                payload = None
                if lastProcessInfo:
                    payload = lastProcessInfo.hwnds[self.lastActivated]
                    self.TriggerEvent("Deactivated." + lastProcessInfo.name, payload)
            self.TriggerEvent("Activated." + thisProcessInfo.name, thisProcessInfo.hwnds[hwnd])
            self.lastActivated = hwnd

def EnumProcesses():
    pids = {}
    hwnds = {}
    dwProcessId = DWORD()
    for hwnd in GetTopLevelWindowList(False):
        GetWindowThreadProcessId(hwnd, byref(dwProcessId))
        pid = dwProcessId.value
        if pid not in pids:
            processInfo = ProcessInfo(pid)
            pids[pid] = processInfo
        else:
            processInfo = pids[pid]
        processInfo.hwnds[hwnd] = WindowInfo(hwnd)
        hwnds[hwnd] = processInfo
    return pids, hwnds

def GetWindowPid(hwnd):
    dwProcessId = DWORD()
    GetWindowThreadProcessId(hwnd, byref(dwProcessId))
    return dwProcessId.value


def _get_window_info():
    print 'eg.result', eg.result
    print 'eg.event.payload', eg.event.payload

    if eg.eventString.startswith('TaskMonitorPlus'):
        return eg.event.payload
    if isinstance(eg.result, WindowInfo):
        return eg.result


class FindTitle(eg.ActionBase):
    def __call__(self, title, stop_macro=True):

        window_info = _get_window_info()
        if window_info and fnmatch.fnmatchcase(window_info.title, title):
            return window_info

        for process_info in self.plugin.hwnds.values():
            for window_info in process_info.hwnds.values():
                if '*' in title or '?' in title:
                    if fnmatch.fnmatchcase(window_info.title, title):
                        eg.eventString = ''
                        return window_info
                elif title == window_info.title:
                    eg.eventString = ''
                    return window_info

        if stop_macro:
            eg.StopMacro()

    def Configure(self, title='', stop_macro=True):

        text = self.text
        panel = eg.ConfigPanel()

        title_st = panel.StaticText(text.title_lbl)
        title_ctrl = panel.TextCtrl(title)
        stop_macro_st = panel.StaticText(text.stop_macro_lbl)
        stop_macro_ctrl = wx.CheckBox(panel, -1, '')
        stop_macro_ctrl.SetValue(stop_macro)

        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title_sizer.Add(title_st, 0, wx.EXPAND | wx.ALL, 5)
        title_sizer.Add(title_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        stop_macro_sizer = wx.BoxSizer(wx.HORIZONTAL)
        stop_macro_sizer.Add(stop_macro_st, 0, wx.EXPAND | wx.ALL, 5)
        stop_macro_sizer.Add(stop_macro_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        panel.sizer.Add(title_sizer, 0, wx.EXPAND)
        panel.sizer.Add(stop_macro_sizer, 0, wx.EXPAND)

        while panel.Affirmed():
            panel.SetResult(
                title_ctrl.GetValue(),
                stop_macro_ctrl.GetValue()
            )


class Flash(eg.ActionBase):

    def __call__(self, caption, tray, until_active, continuous, times, speed):

        window_info = _get_window_info()

        if window_info is not None:

            kwargs = dict(
                caption=caption,
                tray=tray,
                speed=speed
            )

            if until_active:
                kwargs['until_active'] = until_active
            elif continuous:
                kwargs['continuous'] = continuous
            else:
                kwargs['times'] = times

            window_info.Flash(**kwargs)

            return window_info

    def Configure(
        self,
        caption=True,
        tray=False,
        until_active=False,
        continuous=False,
        times=10,
        speed=250
    ):

        text = self.text
        panel = eg.ConfigPanel()

        sts = []

        def add_checkbox(lbl, value):
            st = panel.StaticText(lbl)
            ctrl = wx.CheckBox(panel, -1, '')
            ctrl.SetValue(value)

            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(st, 0, wx.EXPAND | wx.ALL, 5)
            sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 5)

            panel.sizer.Add(sizer, 0, wx.EXPAND)
            sts.append(st)
            return ctrl

        caption_ctrl = add_checkbox(text.caption_lbl, caption)
        tray_ctrl = add_checkbox(text.tray_lbl, tray)
        until_active_ctrl = add_checkbox(text.until_active_lbl, until_active)
        continuous_ctrl = add_checkbox(text.continuous_lbl, continuous)

        times_st = panel.StaticText(text.times_lbl)
        times_ctrl = panel.SpinIntCtrl(times, min=1)

        times_sizer = wx.BoxSizer(wx.HORIZONTAL)
        times_sizer.Add(times_st, 0, wx.EXPAND | wx.ALL, 5)
        times_sizer.Add(times_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        speed_st = panel.StaticText(text.speed_lbl)
        speed_ctrl = panel.SpinIntCtrl(speed, min=1)
        suffix_st = panel.StaticText('ms')

        speed_sizer = wx.BoxSizer(wx.HORIZONTAL)
        speed_sizer.Add(speed_st, 0, wx.EXPAND | wx.ALL, 5)
        speed_sizer.Add(speed_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        speed_sizer.Add(suffix_st, 0, wx.EXPAND | wx.ALL, 5)

        panel.sizer.Add(times_sizer, 0, wx.EXPAND)
        panel.sizer.Add(speed_sizer, 0, wx.EXPAND)

        sts += [times_st, speed_st]

        eg.EqualizeWidths(tuple(sts))

        while panel.Affirmed():
            panel.SetResult(
                caption_ctrl.GetValue(),
                tray_ctrl.GetValue(),
                until_active_ctrl.GetValue(),
                continuous_ctrl.GetValue(),
                times_ctrl.GetValue(),
                speed_ctrl.GetValue(),
            )


class SizePositionBase(eg.ActionBase):

    def __call__(self, arg1, arg2):

        window_info = _get_window_info()

        if window_info is not None:
            getattr(window_info, self.__class__.__name__)(arg1, arg2)
            return window_info

    def Configure(self, arg1=0, arg2=0):

        text = self.text
        panel = eg.ConfigPanel()

        arg1_st = panel.StaticText(text.arg1_lbl)
        arg1_ctrl = panel.SpinIntCtrl(arg1, min=0)

        arg1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        arg1_sizer.Add(arg1_st, 0, wx.EXPAND | wx.ALL, 5)
        arg1_sizer.Add(arg1_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        arg2_st = panel.StaticText(text.arg2_lbl)
        arg2_ctrl = panel.SpinIntCtrl(arg2, min=0)

        arg2_sizer = wx.BoxSizer(wx.HORIZONTAL)
        arg2_sizer.Add(arg2_st, 0, wx.EXPAND | wx.ALL, 5)
        arg2_sizer.Add(arg2_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        panel.sizer.Add(arg1_sizer, 0, wx.EXPAND)
        panel.sizer.Add(arg2_sizer, 0, wx.EXPAND)

        eg.EqualizeWidths((arg1_st, arg2_st))

        while panel.Affirmed():
            panel.SetResult(
                arg1_ctrl.GetValue(),
                arg2_ctrl.GetValue()
            )


class SetSize(SizePositionBase):
    pass


class SetPosition(SizePositionBase):
    pass


class Show(eg.ActionBase):

    def __call__(self, activate, default):

        window_info = _get_window_info()

        if window_info is not None:
            window_info.Show(True, activate=activate, default=default)
            return window_info

    def Configure(self, activate=True, default=False):

        text = self.text
        panel = eg.ConfigPanel()

        sts = []

        def add_checkbox(lbl, value):
            st = panel.StaticText(lbl)
            ctrl = wx.CheckBox(panel, -1, '')
            ctrl.SetValue(value)

            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(st, 0, wx.EXPAND | wx.ALL, 5)
            sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 5)

            panel.sizer.Add(sizer, 0, wx.EXPAND)
            sts.append(st)
            return ctrl

        activate_ctrl = add_checkbox(text.activate_lbl, activate)
        default_ctrl = add_checkbox(text.default_lbl, default)

        eg.EqualizeWidths(tuple(sts))

        while panel.Affirmed():
            panel.SetResult(
                activate_ctrl.GetValue(),
                default_ctrl.GetValue()
            )


class Minimize(eg.ActionBase):

    def __call__(self, activate, force):

        window_info = _get_window_info()

        if window_info is not None:
            window_info.Minimize(activate=activate, force=force)
            return window_info

    def Configure(self, activate=True, force=False):

        text = self.text
        panel = eg.ConfigPanel()

        sts = []

        def add_checkbox(lbl, value):
            st = panel.StaticText(lbl)
            ctrl = wx.CheckBox(panel, -1, '')
            ctrl.SetValue(value)

            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(st, 0, wx.EXPAND | wx.ALL, 5)
            sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 5)

            panel.sizer.Add(sizer, 0, wx.EXPAND)
            sts.append(st)
            return ctrl

        activate_ctrl = add_checkbox(text.activate_lbl, activate)
        force_ctrl = add_checkbox(text.force_lbl, force)

        eg.EqualizeWidths(tuple(sts))

        while panel.Affirmed():
            panel.SetResult(
                activate_ctrl.GetValue(),
                force_ctrl.GetValue()
            )


class Restore(eg.ActionBase):

    def __call__(self, default):

        window_info = _get_window_info()

        if window_info is not None:
            window_info.Restore(default=default)
            return window_info

    def Configure(self, default=False):
        text = self.text
        panel = eg.ConfigPanel()

        default_st = panel.StaticText(text.default_lbl)
        default_ctrl = wx.CheckBox(panel, -1, '')
        default_ctrl.SetValue(default)

        default_sizer = wx.BoxSizer(wx.HORIZONTAL)
        default_sizer.Add(default_st, 0, wx.EXPAND | wx.ALL, 5)
        default_sizer.Add(default_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        panel.sizer.Add(default_sizer, 0, wx.EXPAND)

        while panel.Affirmed():
            panel.SetResult(default_ctrl.GetValue())


class SendKeystrokes(eg.plugins.Window.plugin.info.actions['SendKeys']):
    iconFile = None

    def __call__(self, data, useAlternateMethod=False, mode=2):
        window_info = _get_window_info()
        if window_info is not None:
            window_info.SendKeystrokes(data, useAlternateMethod, mode)
            return window_info


class EnableKeyboardMouse(eg.ActionBase):
    _state = True

    def __call__(self, *args):
            window_info = _get_window_info()
            if window_info is not None:
                window_info.EnableKeyboardMouse(self._state)
                return window_info


class DisableKeyboardMouse(EnableKeyboardMouse):
    _state = False


class WindowInfoBase(eg.ActionBase):

    def __call__(self, *args):
            window_info = _get_window_info()
            if window_info is not None:
                result = getattr(window_info, self.__class__.__name__)()
                if result is None:
                    result = window_info
                return result


class IsActive(WindowInfoBase):
    pass


class IsAlive(WindowInfoBase):
    pass


class BringToTop(WindowInfoBase):
    pass


class IsVisible(WindowInfoBase):
    pass


class IsKeyboardMouseEnabled(WindowInfoBase):
    pass


class Maximize(WindowInfoBase):
    pass


class GetRect(WindowInfoBase):
    pass


class GetRectTuple(WindowInfoBase):
    pass


class GetSize(WindowInfoBase):
    pass


class GetSizeTuple(WindowInfoBase):
    pass


class GetPosition(WindowInfoBase):
    pass


class GetPositionTuple(WindowInfoBase):
    pass


class Hide(WindowInfoBase):
    pass


class Destroy(WindowInfoBase):
    pass


class Close(WindowInfoBase):
    pass


class GetParent(WindowInfoBase):
    pass


class Focus(WindowInfoBase):
    pass


class HasFocus(WindowInfoBase):
    pass



#
# Editor modelines  -  https://www.wireshark.org/tools/modelines.html
#
# Local variables:
# c-basic-offset: 4
# tab-width: 4
# indent-tabs-mode: nil
# coding: utf-8
# End:
#
# vi: set shiftwidth=4 tabstop=4 expandtab fileencoding=utf-8:
# :indentSize=4:tabSize=4:noTabs=true:coding=utf-8:
#
