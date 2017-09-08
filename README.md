# EventGhost-TaskMonitorPlus

This program is not very useful on its own. It's a plugin for
[EventGhost](http://www.eventghost.net/).
EventGhost is an automation tool for MS Windows
which listens for events -- whether user-triggered (like the press of a hotkey)
or system events (such as the screensaver activating) -- and runs actions
you specify. (It's like [Tasker](http://tasker.dinglisch.net/) for Android, or
[Cuttlefish](https://launchpad.net/cuttlefish) for Ubuntu.)

## Description

TaskMonitorPlus is a fork/expansion of the Task Monitor (aka simply Task)
plugin for EventGhost. The original Task Monitor plugin generates events
when a window opens, closes, flashes, or gains or loses focus. But the event
contains nothing but the name of the executable which created the window.

TaskMonitorPlus still produces these events (as well as a new event for when
a window's title changes), but now they come with a payload.
The `eg.event.payload` produced by an event is an object (named WindowInfo,
if you're curious) with the following attributes and methods:

* `title`: the title of the window
* `window_class`: the internal class name for the window
* `hwnd`: the internal ID for the window
* `pid`: the process ID for thet executable owning the window
* `name`: the executable name of the process owning the window (same as in
  the event itself)
* `GetParent()`: returns a new object representing the parent of this window
* `Focus()`: directs focus to the window
* `HasFocus()`: returns True if the window has focus
* `IsAlive()`: returns True if the window is still open
* `IsActive()`: returns True if this window is the currently active one
* `Animate()`: coming soon
* `SendKeystrokes()`: just like the Send Keys action in EventGhost
* `Flash()`: make the window flash
* `BringToTop()`: raise the window
* `IsVisible()`: returns True if the window isn't hidden
* `EnableKeyboardMouse()`: enable (or disable) mouse and keyboard input
  for the window
* `IsKeyboardMouseEnabled()`: returns True if so
* `Restore()`: restores the window to its previous state
* `Minimize()`: minimize (or un-minimize) the window
* `Maximize()`: maximize the window
* `SetPosition()`: set the window's position
* `SetSize()`: set the window's size
* `SetRect()`: set the window's position and size
* `GetRect()` and `GetRectTuple()`: return window's position and size
* `GetSize()` and `GetSizeTuple()`: return window's size
* `GetPosition()` and `GetPositionTuple()`: return window's position
* `Show()`: show (or hide) the window
* `Hide()`: hide the window
* `Destroy()`: destroy the window
* `Close()`: close the window
* `SendMessage()` and `PostMessage()`: low-level messaging to window

The methods are documented in the source code in detail. This documentation
should appear in your IDE and in PyCharm (the Python shell that EventGhost
includes under the Help menu).

The window title can change over the window's lifetime. The `title` attribute
tries to fetch the most recent window title whenever it's accessed, but if it
can't (like if the window has been closed and no longer exists) it returns
the last known title.

## Usage

You should **remove** the Task Monitor plugin (which ships with EventGhost)
from your Autostart list, if it's there, **before** installing Task Monitor
Plus. Don't just disable Task Monitor, because it may still interfere with Task
Monitor Plus as long as it's installed.

You can install this plugin and activate it like any other.
If you've used the standard Task Monitor plugin, the behaviour is identical,
except that the events produced start with `TaskMonitorPlus.` instead
of `Task.`.

In case you aren't familiar with the standard Task Monitor plugin, here's
how you can use it: at the bottom of the EventGhost window, uncheck the
checkbox that says "Log only assigned and activated events", then open
or switch to a window which you'd like to take action on. You'll see an
entry appear in the log that looks something like this:

    TaskMonitorPlus.NewWindow.notepad <title=u'Untitled - Notepad', window_class=u'Notepad',...>

You can drag this entry from the log into any macro you've created, to cause
the actions in that macro to be played back the next time that action takes
place.

You can access the payload object from follow-on actions via the
`eg.event.payload` object. For a simple example, to flash an on-screen display
of the current window's title when Notepad opens, you could add the
the EventGhost → Show OSD action to a macro, and enter something like
"New window opened: {eg.event.payload.title}" in the "Text to display" field.

For more information on using EventGhost, consult the EventGhost
[website](http://www.eventghost.net/),
[wiki](http://www.eventghost.net/mediawiki/), and
[forums](http://www.eventghost.net/forum/).

## Downloads and Support

Official releases of this plugin are being made available at
[this thread on the EventGhost forums](http://www.eventghost.net/forum/viewtopic.php?f=9&t=9804).
You can also provide feedback and request support there.

I also accept issues and pull requests from the official GitHub repo for
this project,
[Boolean263/EventGhost-TaskMonitorPlus](https://github.com/Boolean263/EventGhost-TaskMonitorPlus).
However, remember that this is not originally my work (although admittedly
we've changed it a fair bit these days) . If you experience problems with Task
Monitor Plus, please check if the problem also happens when you use the
original Task Monitor plugin.

## Author

Boolean263 (aka David Perry) and kgschlosser,
based on work by Bitmonster and blackwind

## History

The original, canonical Task Monitor ships with EventGhost. This version
is based on version 1.0.4 of that plugin (which was
copied from the 0.5.0-rc4 release of EventGhost) and modified, based on ideas
I had in (and feedback I received on) my
[EventGhost-WindowWatcher](https://github.com/Boolean263/EventGhost-WindowWatcher) plugin.

## Changelog

### v0.0.4 = 2017-09-08

* Improve caching of window title and class (should now behave better for
  windows that legitimately have an empty string for either)
* Raise a `WindowInfo.DeadWindow` exception when attempting to modify windows
  that no longer exist (many query functions, such as `IsActive()`, don't
  raise this and simply return `False`; `GetRect()` and the like still
  raise an exception)
* Raise a `WindowInfo.NoParent` exception (instead of the old `ValueError`)
  when calling `GetParent()` on a window with no parent

### v0.0.3 - 2017-09-07

* Removed TaskHook.dll since it's not actually needed (thanks kgschlosser
  for the find)
* Added the TitleChanged event after discovering the `HSHELL_REDRAW` event
  type (the event payload contains the window's new title)
* Improved plugin documentation that shows within EventGhost
* Add new WindowInfo methods (thanks kgschlosser)

### v0.0.2 - 2017-09-02

* Bugfix: this plugin was breaking the event log if it tried to report a
  window that had non-ASCII characters in its title. I don't know if this
  is a bug in EventGhost itself or what, but I fixed it by using `repr()`
  to return the window title.

### v0.0.1 - 2017-08-29

* Initial release of the Plus version of this plugin
