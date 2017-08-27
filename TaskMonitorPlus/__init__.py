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

from os.path import abspath, dirname, join, splitext

# Local imports
import eg
from eg.WinApi import GetClassName, GetTopLevelWindowList, GetWindowText
from eg.WinApi.Dynamic import (
    BOOL, byref, CDLL, DeregisterShellHookWindow, DWORD, EnumWindows,
    FreeLibrary, GA_ROOT, GetAncestor, GetShellWindow, GetWindowLong,
    GetWindowThreadProcessId, GWL_HWNDPARENT, HSHELL_WINDOWACTIVATED,
    HSHELL_WINDOWCREATED, HSHELL_WINDOWDESTROYED, HWND, IsWindowVisible,
    LPARAM, RegisterShellHookWindow, RegisterWindowMessage, WINFUNCTYPE,
    WM_APP,
)
from eg.WinApi.Utils import GetProcessName
import win32gui

eg.RegisterPlugin(
    name = "Task Monitor Plus",
    author = (
        "Bitmonster",
        "blackwind",
        "Boolean263",
    ),
    version = "1.0.4.1",
    guid = "{D1748551-C605-4423-B392-FB77E6842437}",
    description = (
        "Generates events when an application starts, exits, flashes the "
        "taskbar, or gets switched into focus."
    ),
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

ENUM_WINDOWS_PROC_TYPE = WINFUNCTYPE(BOOL, HWND, LPARAM)
EnumWindows.argtypes = [ENUM_WINDOWS_PROC_TYPE, LPARAM]

WM_SHELLHOOKMESSAGE = RegisterWindowMessage("SHELLHOOK")

class Task(eg.PluginBase):
    def __init__(self):
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
        #self.hookDll = CDLL(abspath(join(dirname(__file__), "TaskHook.dll")))
        self.hookDll = CDLL(abspath(join(eg.corePluginDir, "Task", "TaskHook.dll")))
        self.hookDll.StartHook()
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
        self.hookDll.StopHook()
        FreeLibrary(self.hookDll._handle)
        DeregisterShellHookWindow(eg.messageReceiver.hwnd)
        eg.messageReceiver.RemoveHandler(WM_SHELLHOOKMESSAGE, self.MyWndProc)
        eg.messageReceiver.RemoveHandler(WM_APP + 1, self.WindowGotFocusProc)
        eg.messageReceiver.RemoveHandler(WM_APP + 2, self.WindowCreatedProc)
        eg.messageReceiver.RemoveHandler(WM_APP + 3, self.WindowDestroyedProc)

    def CheckWindow(self, hwnd):
        hwnd2 = GetAncestor(hwnd, GA_ROOT)
        if hwnd == 0 or hwnd2 in self.desktopHwnds:
            return #"Desktop", 0, None
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
        elif wParam == 0x8006:
            self.WindowFlashedProc(None, None, lParam, None)
        return 1

    def WindowCreatedProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        self.CheckWindow(hwnd)

    def WindowDestroyedProc(self, dummyHwnd, dummyMesg, hwnd, dummyLParam):
        #hwnd2 = GetAncestor(hwnd, GA_ROOT)
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


class ProcessInfo(object):
    """
    Class representing an individual process, and keeping a list of
    its open windows.
    """
    def __init__(self, pid):
        self.pid = pid
        self.name = splitext(GetProcessName(pid))[0]
        self.hwnds = dict()     # key=hwnd, val=WindowInfo(hwnd)

    def __str__(self):
        return self.name
        # return self.name+"."+str(self.pid)

    def __add__(self, other):
        # Allow string concatenation without extra syntax
        if isinstance(other, basestring):
            return str(self)+other
        # Intentionally raise TypeError
        return self+other

    def __radd__(self, other):
        # Allow string concatenation without extra syntax
        if isinstance(other, basestring):
            return other+str(self)
        # Intentionally raise TypeError
        return self+other


class WindowInfo(object):
    """
    Class representing an individual window. Interesting attributes:
    - hwnd: window ID
    - pid: PID of process that owns this window
    - name: executable name of process that owns this window
    - title: window's title (updated dynamically if possible)
    - window_class: window's class name (updated dynamically if possible)
    - is_visible: whether window is visible
    - is_enabled: whether window is enabled (whatever that means?)
    """
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.pid = GetWindowPid(hwnd)
        self.name = splitext(GetProcessName(self.pid))[0]
        # The following may change during a window's lifetime
        self.title = GetWindowText(hwnd)
        self.window_class = GetClassName(hwnd)

    def __getattribute__(self, name):
        if name == 'is_visible':
            return win32gui.IsWindowVisible(self.hwnd)
        elif name == 'is_enabled':
            return win32gui.IsWindowEnabled(self.hwnd)
        elif name == 'title':
            # If the window is closed, GetWindowText and GetClassName
            # return empty strings, so return the cached versions.
            title = GetWindowText(self.hwnd)
            if title != '':
                self.title = title
            # Intentionally fall through to end of method
        elif name == 'window_class':
            win_class = GetClassName(self.hwnd)
            if win_class != '':
                self.window_class = win_class
            # Intentionally fall through to end of method

        return object.__getattribute__(self, name)

    def __repr__(self):
        """EG uses this to show the event's payload."""
        return "<title='{}', window_class='{}',...>".format(self.title, self.window_class)

    # We could add useful methods from win32gui etc. to this object
    # to allow callers to do interesting stuff with the window referenced.
    # Here are a couple of examples.

    def GetParent(self):
        return WindowInfo(win32gui.GetParent(self.hwnd))

    def Focus(self):
        win32gui.SetFocus(self.hwnd)


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

