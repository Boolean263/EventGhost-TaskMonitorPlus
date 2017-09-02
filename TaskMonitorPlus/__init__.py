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
    version = "0.0.1",
    guid = "{4826ED71-64DE-496A-84A4-955402DEC3BC}",
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

class TaskMonitorPlus(eg.PluginBase):
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
        self.hookDll = CDLL(abspath(join(dirname(__file__), "TaskHook.dll")))
        #self.hookDll = CDLL(abspath(join(eg.corePluginDir, "Task", "TaskHook.dll")))
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
    Class representing an individual window.
    
    To use this class append eg.event.payload with one of the 
    following methods/attributes.
    
    Attributes:
        window_class: type of window
        title: window title
        pid: process id of the process that owns this window
        name: executable name of process that owns this window
        hwnd: unique identifier for the window (assigned by Windows)

    Methods:
        SetFocus(): give the window keyboard/mouse focus
        GetFocus(): if the window has focus or not
            returns True/False
        GetParent(): get the parent of this window
            returns WindowInfo class
        PostMessage(): do not use if you do not know how
        SendMessage(): do not use if you do not know how
        Destroy(): closes the window
        Hide(): hides the window
        Show(flag=True, activate=True, default=False): show the window
            flag = to show or not to show
            activate = give window focus 
            default = window startup pos/size
        IsAlive(): if the window is still kicking around
            returns True/False
        IsActive(): if the window is active or not
            returns True / False
        Animate(slide=True, blend=False, direction="", show=True, hide=True, duration=150): animate the showing and hiding of the window
            blend = fade in or out - True/False        
            direction = does not work with blend  - "UP"/"DOWN"/"LEFT"/"RIGHT"/""
            show: if to use this animation while showing
            hide: if to use this animation when hiding
            duration: time in milliseconds for the animation to run for
        SendKeystrokes(text): send keystrokes to the window
            test = the same way the SendKeys action does it
        Flash(caption=True, tray=False, until_active=False, continuous=False, times=6, speed=100): flash the window
            caption = flash the caption - True/False
            tray = flash the tray = True/False
            until_active = don't stop flashing until the window is activated
            continuous = do not stop flashing until told to do so. to stop flashing pass False to both the tray and caption.
            times = number of times to flash (only applicable if until_active and continuous are False)
            speed = length of time in milliseconds between flashes
        IsKeyboardMouseEnabled(): hmmm......
            returns True/False
        EnableKeyboardMouse(flag=True): hmmmm.....
            flag = True/False
        BringToTop(): brings the window to the foreground
        Restore(default=False): hmmm.... 
            default = use original window startup pos/size - True/False
        Maximize(): maximize the window
        Minimize(activate=True, force=False): hmmm....
            activate = set window focus - True/False
            force = do it no matter what even if hung - True/False
        GetPositionTuple():
            returns(x, y)
        GetPosition():
            returns wx.Point(x, y)
        GetSizeTuple():
            returns(width, height)
        GetSize():
            returns wx.Size(width, height)
        GetRect():
            returns wx.Rect(x, y, width, height)
        GetRectTuple():
            returns (x, y, width, height)
        SetRect(*args): sets size and position
            args can be any of the following: 
                SetRect(wx.Rect(x, y, width, height))
                SetRect(((x, y), (width, height)))
                SetRect(x, y, width, height)
        SetSize(*args):
            args can be any of the following:
                SetSize(wx.Size(width, height))
                SetSize((width, height))
                SetSize(width, height)
        SetPosition(*args):
            args can be any of the following:
                SetPosition(wx.Point(x, y)
                SetPosition((x, y))
                SetPosition(x, y)
    """

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.pid = GetWindowPid(hwnd)
        self.name = splitext(GetProcessName(self.pid))[0]
        # The following may change during a window's lifetime
        self.title = GetWindowText(hwnd)
        self.window_class = GetClassName(hwnd)

    def IsAlive(self):
        return win32gui.IsWindow(self.hwnd)

    def IsActive(self):
        return self.hwnd == win32gui.GetActiveWindow()

    def Animate(
        self,
        slide=True,
        blend=False,
        direction='',
        show=True,
        hide=True,
        duration=150
    ):

        if slide and blend:
            eg.PrintNotice(
                'You are only allowed to select one type of effect, '
                'or set both to False for roll effect.'
            )
            return

        style = 0

        if direction.upper() == 'UP':
            style |= win32con.AW_HOR_NEGATIVE
        elif direction.upper() == 'DOWN':
            style |= win32con.AW_HOR_POSITIVE
        elif direction.upper() == 'LEFT':
            style |= win32con.AW_VER_NEGATIVE
        elif direction.upper() == 'RIGHT':
            style |= win32con.AW_VER_POSITIVE
        else:
            style |= win32con.AW_CENTER

        if hide:
            style |= win32con.AW_HIDE
        if show:
            style |= win32con.AW_ACTIVATE

        if slide:
            style |= win32con.AW_SLIDE

        elif blend:
            style |= win32con.AW_BLEND

        win32gui.AnimateWindow(self.hwnd, duration, style)

    def SendKeystrokes(self, text):
        eg.SendKeys(self.hwnd, text, False, 2)

    def Flash(self, caption=True, tray=False, until_active=False,
        continuous=False, times=6, speed=100):

        flag = 0

        if until_active:
            flag |= win32con.FLASHW_TIMERNOFG
        elif continuous:
            flag |= win32con.FLASHW_TIMER

        if tray and caption:
            flag |= win32con.FLASHW_ALL

        elif tray:
            flag |= win32con.FLASHW_TRAY

        elif caption:
            flag |= win32con.FLASHW_CAPTION

        else:
            flag = win32con.FLASHW_STOP

        win32gui.FlashWindowEx(self.hwnd, flag, times, speed)

    def BringToTop(self):
        win32gui.BringWindowToTop(self.hwnd)

    def IsVisible(self):
        return win32gui.IsWindowVisible(self.hwnd)

    def EnableKeyboardMouse(self, flag=True):
        win32gui.EnableWindow(self.hwnd, flag)

    def IsKeyboardMouseEnabled(self):
        return win32gui.IsWindowEnabled(self.hwnd)

    def Restore(self, default=False):
        if self.IsVisible():
            if default:
                activate = win32con.SW_SHOWNORMAL
            else:
                activate = win32con.SW_RESTORE
        else:
            activate = win32con.SW_SHOWNORMAL

        win32gui.ShowWindow(self.hwnd, activate)

    def Minimize(self, activate=True, force=False):
        if self.IsVisible():
            if activate:
                activate = win32con.SW_MINIMIZE
            else:
                activate = win32con.SW_SHOWMINNOACTIVE
        else:
            if activate:
                activate = win32con.SW_SHOWMINIMIZED
            else:
                activate = win32con.SW_SHOWMINNOACTIVE

        if force:
            activate = win32con.SW_FORCEMINIMIZE

        win32gui.ShowWindow(self.hwnd, activate)

    def Maximize(self):
        if self.IsVisible():
            activate = win32con.SW_MAXIMIZE
        else:
            activate = win32con.SW_SHOWMAXIMIZED
        win32gui.ShowWindow(self.hwnd, activate)

    def SetPosition(self, *args):
        if len(args) == 1:
            args = args[0]

        if isinstance(args, wx.Point):
            args = args.Get()

        win32gui.SetWindowPos(
            self.hwnd,
            args[0],
            args[1],
            0,
            0,
            win32con.SWP_NOSIZE
        )

    def SetSize(self, *args):
        if len(args) == 1:
            args = args[0]

        if isinstance(args, wx.Size):
            args = args.Get()

        win32gui.SetWindowPos(
            self.hwnd,
            0,
            0,
            args[0],
            args[1],
            win32con.SWP_NOMOVE
        )

    def SetRect(self, *args):
        if len(args) == 1:
            args = args[0]

        elif len(args) == 2:
            size = args[0]
            pos = args[1]
            if isinstance(size, wx.Size):
                size = size.Get()
            if isinstance(pos, wx.Point):
                pos = pos.Get()

            args = size + pos

        if isinstance(args, wx.Rect):
            args = args.Get()

        self.SetSize(args[2:])
        self.SetPosition(args[:2])

    def GetRect(self):
        x, y, b_x, b_y = win32gui.GetWindowRect(self.hwnd)
        return wx.Rect(x, y, x + b_x, y + b_y)

    def GetRectTuple(self):
        x, y, b_x, b_y = win32gui.GetWindowRect(self.hwnd)
        return x, y, x + b_x, y + b_y

    def GetSize(self):
        rect = self.GetRect()
        return wx.Size(rect.width, rect.height)

    def GetSizeTuple(self):
        rect = self.GetRect()
        return rect.width, rect.height

    def GetPosition(self):
        rect = self.GetRect()
        return wx.Position(rect.x, rect.y)

    def GetPositionTuple(self):
        rect = self.GetRect()
        return rect.x, rect.y

    def Show(self, flag=True, activate=True, default=False):
        if activate:
            if default:
                activate = win32con.SW_SHOWDEFAULT
            else:
                activate = win32con.SW_SHOW
        else:
            if default:
                activate = win32con.SW_SHOWNA

            else:
                activate = win32con.SW_SHOWNOACTIVATE

        if not flag:
            activate = win32con.SW_HIDE

        win32gui.ShowWindow(self.hwnd, activate)

    def Hide(self):
        self.Show(False)

    def Destroy(self):
        win32gui.DestroyWindow(self.hwnd)

    def SendMessage(self, message, wparam=None, lparam=None):
        win32gui.SendMessage(self.hwnd, message, wparam, lparam)

    def PostMessage(self, message, wparam=0, lparam=0):
        win32gui.PostMessage(self.hwnd, message, wparam, lparam)

    def __getitem__(self, item):
        return getattr(self, item)

    def __repr__(self):
        """EG uses this to show the event's payload."""
        return "<dynamic class '%s'>" % self.title

    def __str__(self):
        return self.__class__.__doc__

    # We could add useful methods from win32gui etc. to this object
    # to allow callers to do interesting stuff with the window referenced.
    # Here are a couple of examples.

    def GetParent(self):
        return WindowInfo(win32gui.GetParent(self.hwnd))

    def GetFocus(self):
        return self.hwnd == win32gui.GetFocus()

    def SetFocus(self):
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

