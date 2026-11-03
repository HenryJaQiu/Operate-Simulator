# -*- coding: utf-8 -*-
"""游戏后台按键助手（Windows 单文件版）

启动:
    python game_assistant.py

功能:
    1. 选择目标窗口（支持子窗口，可用鼠标拾取），目标未激活、最小化、
       或前台正在操作其它程序时，仍可后台发送键盘/鼠标信号。
    2. 每个任务独立设置：按键（支持组合键，可直接点“捕获按键”按键盘录入，
       如 Alt、方向键、Ctrl+Shift+A）、间隔秒数、按住秒数（长按）、执行次数
       或持续分钟数。
    3. 并行计时 / 顺序循环 两种模式，可设置总运行时长（分钟），支持长时间挂机，
       界面实时显示计划时长、已运行时间、已发送次数和剩余时间。
    4. 后台消息模式（PostMessage）与前台模拟模式（SendInput）可切换。
    5. 全局停止快捷键 Ctrl+Alt+Shift+Q，任何时刻可结束全部任务。

已知限制:
    - 使用 DirectInput / Raw Input 的程序（部分 Unity、虚幻引擎游戏，以及
      冒险岛等 MapleStoryClass 客户端）收不到后台消息，必须使用前台模拟。
    - 前台模拟模式会抢占前台焦点；可勾选“保持目标焦点”，运行结束后自动恢复。
    - 部分程序最小化后会暂停消息处理，恢复窗口后才响应。
    - 若目标程序以管理员权限运行，本工具也需以管理员身份运行（UIPI 限制），
      可直接使用同目录的 run_admin.bat 启动。
"""

import ctypes
import json
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox, simpledialog, ttk

user32 = ctypes.WinDLL("user32", use_last_error=True)

try:
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

ULONG_PTR = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, ULONG_PTR, LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ULONG_PTR, LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ULONG_PTR, LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, ULONG_PTR, LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ULONG_PTR)]
user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, ULONG_PTR, LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ULONG_PTR, LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WM_GETTEXT = 0x000D
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WA_ACTIVE = 1
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
GA_ROOT = 2
SW_RESTORE = 9
SMTO_ABORTIFHUNG = 0x0002
WH_KEYBOARD_LL = 13
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

VK_MAP = {
    "backspace": 0x08, "退格": 0x08,
    "tab": 0x09, "制表": 0x09,
    "enter": 0x0D, "回车": 0x0D,
    "shift": 0x10, "ctrl": 0x11, "control": 0x11, "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14, "大小写": 0x14,
    "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "空格": 0x20,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "左": 0x25, "up": 0x26, "上": 0x26,
    "right": 0x27, "右": 0x27, "down": 0x28, "下": 0x28,
    "insert": 0x2D, "插入": 0x2D,
    "delete": 0x2E, "del": 0x2E, "删除": 0x2E,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "numlock": 0x90,
    "numdiv": 0x6F, "nummul": 0x6A, "numadd": 0x6B,
    "numsub": 0x6D, "numdot": 0x6E,
    "lshift": 0xA0, "rshift": 0xA1, "lctrl": 0xA2,
    "rctrl": 0xA3, "lalt": 0xA4, "ralt": 0xA5,
}
for _ch in "abcdefghijklmnopqrstuvwxyz":
    VK_MAP[_ch] = ord(_ch.upper())
for _ch in "0123456789":
    VK_MAP[_ch] = ord(_ch)
for _i in range(1, 25):
    VK_MAP["f%d" % _i] = 0x6F + _i
for _i in range(10):
    VK_MAP["num%d" % _i] = 0x60 + _i
for _ch, _vk in (
    (";", 0xBA), ("=", 0xBB), (",", 0xBC), ("-", 0xBD), (".", 0xBE),
    ("/", 0xBF), ("`", 0xC0), ("[", 0xDB), ("\\", 0xDC), ("]", 0xDD),
    ("'", 0xDE),
):
    VK_MAP[_ch] = _vk

VK_TO_NAME = {
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x13: "pause",
    0x14: "capslock", 0x1B: "esc", 0x20: "space",
    0x21: "pageup", 0x22: "pagedown", 0x23: "end", 0x24: "home",
    0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
    0x2D: "insert", 0x2E: "delete", 0x5B: "win", 0x5C: "win",
    0x90: "numlock", 0x6A: "nummul", 0x6B: "numadd",
    0x6D: "numsub", 0x6E: "numdot", 0x6F: "numdiv",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".",
    0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]",
    0xDE: "'",
}
for _i in range(10):
    VK_TO_NAME[0x60 + _i] = "num%d" % _i
for _i in range(1, 25):
    VK_TO_NAME[0x6F + _i] = "f%d" % _i

MODIFIER_NAMES = {
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x5B: "win", 0x5C: "win",
}
MODIFIER_VKS = set(MODIFIER_NAMES)

EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
    0x2D, 0x2E, 0x5B, 0x5C, 0x90, 0x6F, 0xA3, 0xA5,
}


def window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def safe_child_text(hwnd):
    buf = ctypes.create_unicode_buffer(64)
    result = ULONG_PTR()
    try:
        ok = user32.SendMessageTimeoutW(
            hwnd, WM_GETTEXT, 64, ctypes.addressof(buf),
            SMTO_ABORTIFHUNG, 60, ctypes.byref(result))
        if ok:
            return buf.value
    except Exception:
        pass
    return ""


def is_window(hwnd):
    return bool(hwnd) and bool(user32.IsWindow(hwnd))


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def window_display(hwnd):
    title = window_text(hwnd) or "(无标题)"
    return "%s [%s] (0x%X)" % (title, class_name(hwnd), hwnd)


def list_top_windows():
    results = []
    my_pid = os.getpid()

    def callback(hwnd, lparam):
        if not hwnd:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == my_pid:
            return True
        title = window_text(hwnd)
        if not title:
            return True
        results.append((hwnd, title, class_name(hwnd)))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return results


def list_child_windows(parent):
    results = []

    def callback(hwnd, lparam):
        if hwnd and hwnd != parent:
            results.append(hwnd)
        return len(results) < 200

    user32.EnumChildWindows(parent, WNDENUMPROC(callback), 0)
    return results


def focused_hwnd(hwnd):
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    if not tid:
        return None
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return info.hwndFocus or None
    return None


def force_foreground(root):
    if not root or not is_window(root):
        return False
    if user32.IsIconic(root):
        user32.ShowWindow(root, SW_RESTORE)
        time.sleep(0.25)
    if user32.GetForegroundWindow() == root:
        return True
    user32.BringWindowToTop(root)
    user32.SetForegroundWindow(root)
    for _ in range(4):
        if user32.GetForegroundWindow() == root:
            return True
        time.sleep(0.05)
    current_tid = kernel32.GetCurrentThreadId()
    foreground = user32.GetForegroundWindow()
    foreground_tid = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    target_tid = user32.GetWindowThreadProcessId(root, None)
    attached = []
    try:
        if foreground_tid and foreground_tid != current_tid:
            if user32.AttachThreadInput(current_tid, foreground_tid, True):
                attached.append(foreground_tid)
        if target_tid and target_tid != current_tid and target_tid != foreground_tid:
            if user32.AttachThreadInput(current_tid, target_tid, True):
                attached.append(target_tid)
        user32.BringWindowToTop(root)
        user32.SetForegroundWindow(root)
        user32.SetFocus(root)
    finally:
        for tid in attached:
            user32.AttachThreadInput(current_tid, tid, False)
    for _ in range(6):
        if user32.GetForegroundWindow() == root:
            return True
        time.sleep(0.05)
    return False


def parse_combo(text):
    parts = [p.strip().lower() for p in str(text).split("+") if p.strip()]
    if not parts:
        raise ValueError("按键不能为空")
    vks = []
    for part in parts:
        if part.startswith("vk_0x"):
            try:
                vk = int(part[5:], 16)
            except ValueError:
                raise ValueError("未知按键: %s" % part)
            if not 1 <= vk <= 0xFF:
                raise ValueError("未知按键: %s" % part)
            vks.append(vk)
        elif part in VK_MAP:
            vks.append(VK_MAP[part])
        else:
            raise ValueError("未知按键: %s" % part)
    return vks


def vk_to_name(vk):
    if vk in MODIFIER_NAMES:
        return MODIFIER_NAMES[vk]
    if vk in VK_TO_NAME:
        return VK_TO_NAME[vk]
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    return "vk_0x%02X" % vk


class KeyCaptureState:
    def __init__(self):
        self.down = set()
        self.mod_vks = []
        self.mod_names = []
        self.finished = None

    def preview_text(self):
        if self.finished:
            return self.finished
        if self.mod_names:
            return "+".join(self.mod_names) + "+…"
        return "等待输入…"

    def feed(self, msg, vk):
        if self.finished:
            return self.finished
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if vk in self.down:
                return None
            self.down.add(vk)
            if vk in MODIFIER_VKS:
                name = MODIFIER_NAMES[vk]
                if name not in self.mod_names:
                    self.mod_names.append(name)
                if vk not in self.mod_vks:
                    self.mod_vks.append(vk)
                return None
            parts = self.mod_names + [vk_to_name(vk)]
            self.finished = "+".join(parts)
            return self.finished
        if msg in (WM_KEYUP, WM_SYSKEYUP):
            self.down.discard(vk)
            if vk in MODIFIER_VKS:
                if vk in self.mod_vks:
                    self.mod_vks.remove(vk)
                if not self.mod_vks and self.mod_names:
                    self.finished = "+".join(self.mod_names)
                    return self.finished
            return None
        return None


class KeyCaptureDialog(tk.Toplevel):
    def __init__(self, master, on_result):
        super().__init__(master)
        self.on_result = on_result
        self.done = False
        self.pending = None
        self.pressed = set()
        self.state = KeyCaptureState()
        self.events = queue.Queue()
        self.hook = None
        self._hook_proc = None

        self.title("捕获按键")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="请按下要使用的按键或组合键",
                  font=("Microsoft YaHei UI", 12)).pack()
        self.preview = tk.StringVar(value="等待输入…")
        ttk.Label(body, textvariable=self.preview, foreground="#0055aa",
                  font=("Consolas", 14)).pack(pady=10)
        ttk.Label(body, text="支持字母/数字、方向键、Alt/Ctrl/Shift、F1-F24、小键盘等。\n"
                             "组合键请按住不放，例如 Alt+↑、Ctrl+Shift+A。",
                  justify="center").pack()
        ttk.Button(body, text="取消（用鼠标点击）", command=self.cancel).pack(pady=(12, 0))
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Destroy>", self._on_destroy)
        self._install_hook()
        self.after(30, self._poll)
        self.focus_force()

    def _install_hook(self):
        try:
            self._hook_proc = HOOKPROC(self._hook_callback)
            self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, None, 0)
            if not self.hook:
                raise OSError("SetWindowsHookExW 返回空")
        except Exception as exc:
            self.hook = None
            self._finish(None)
            messagebox.showerror("捕获失败", "无法安装键盘钩子: %s" % exc, parent=self.master)

    def _hook_callback(self, code, wparam, lparam):
        if code >= 0:
            try:
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                self.events.put((int(wparam), int(info.vkCode)))
            except Exception:
                pass
            return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _poll(self):
        if self.done:
            return
        while True:
            try:
                msg, vk = self.events.get_nowait()
            except queue.Empty:
                break
            if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
                self.pressed.add(vk)
            elif msg in (WM_KEYUP, WM_SYSKEYUP):
                self.pressed.discard(vk)
            if self.pending is None:
                result = self.state.feed(msg, vk)
                if result:
                    self.pending = result
        if self.pending:
            self.preview.set("已捕获: %s（松开按键后生效）" % self.pending)
            if not self.pressed:
                self._finish(self.pending)
                return
        else:
            self.preview.set(self.state.preview_text())
        self.after(30, self._poll)

    def _unhook(self):
        if self.hook:
            try:
                user32.UnhookWindowsHookEx(self.hook)
            except Exception:
                pass
            self.hook = None

    def _finish(self, result):
        if self.done:
            return
        self.done = True
        self._unhook()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        try:
            self.on_result(result)
        except Exception:
            pass

    def cancel(self):
        self._finish(None)

    def _on_destroy(self, event):
        if event.widget is self:
            self.done = True
            self._unhook()


def post_key_message(hwnd, vk, down):
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    lparam = 1 | (scan << 16) | (1 << 30)
    if vk in EXTENDED_VKS:
        lparam |= 1 << 24
    if not down:
        lparam |= 1 << 31
    msg = WM_KEYDOWN if down else WM_KEYUP
    return bool(user32.PostMessageW(hwnd, msg, vk, LPARAM(lparam)))


def post_mouse_down(hwnd, x, y, button):
    lparam = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    ok = bool(user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, LPARAM(lparam)))
    if button == "right":
        ok = bool(user32.PostMessageW(
            hwnd, WM_RBUTTONDOWN, MK_RBUTTON, LPARAM(lparam))) and ok
    else:
        ok = bool(user32.PostMessageW(
            hwnd, WM_LBUTTONDOWN, MK_LBUTTON, LPARAM(lparam))) and ok
    return ok


def post_mouse_up(hwnd, x, y, button):
    lparam = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    if button == "right":
        return bool(user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, LPARAM(lparam)))
    return bool(user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, LPARAM(lparam)))


def post_mouse_message(hwnd, x, y, button, hold=0.0):
    ok = post_mouse_down(hwnd, x, y, button)
    if hold > 0:
        time.sleep(hold)
    ok = post_mouse_up(hwnd, x, y, button) and ok
    return ok


def send_input_key(vk, down):
    inp = INPUT(type=INPUT_KEYBOARD)
    flags = 0 if down else KEYEVENTF_KEYUP
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    inp.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return bool(user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)))


def send_input_key_scancode(vk, down):
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    if not scan:
        return send_input_key(vk, down)
    inp = INPUT(type=INPUT_KEYBOARD)
    flags = KEYEVENTF_SCANCODE
    if not down:
        flags |= KEYEVENTF_KEYUP
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    inp.ki = KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return bool(user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)))


def send_input_mouse(button, down):
    inp = INPUT(type=INPUT_MOUSE)
    if button == "right":
        flags = MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP
    else:
        flags = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
    inp.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return bool(user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)))


def to_float(text, name, minimum=None, allow_empty=False):
    text = str(text).strip()
    if not text:
        if allow_empty:
            return 0.0
        raise ValueError("%s不能为空" % name)
    try:
        value = float(text)
    except ValueError:
        raise ValueError("%s必须是数字" % name)
    if minimum is not None and value < minimum:
        raise ValueError("%s不能小于 %g" % (name, minimum))
    return value


def format_minutes(seconds):
    return "%g" % round(float(seconds) / 60.0, 2)


def format_minutes_value(minutes):
    minutes = float(minutes)
    if minutes >= 100:
        return "%.0f" % minutes
    if minutes >= 10:
        return "%.1f" % minutes
    return "%.2f" % minutes


class SequenceDialog(tk.Toplevel):
    def __init__(self, master, keys, gap, on_result):
        super().__init__(master)
        self.on_result = on_result
        self.title("编辑组合序列")
        self.transient(master)
        self.resizable(False, False)
        self.grab_set()
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="按键序列（逗号分隔，按顺序执行）").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.keys_entry = ttk.Entry(body, width=42)
        self.keys_entry.insert(0, ",".join(keys))
        self.keys_entry.grid(row=1, column=0, columnspan=2, sticky="we",
                             pady=(2, 8))
        ttk.Label(body, text="每个键之间间隔(秒):").grid(
            row=2, column=0, sticky="w")
        self.gap_entry = ttk.Entry(body, width=8)
        self.gap_entry.insert(0, "%g" % gap)
        self.gap_entry.grid(row=2, column=1, sticky="w")
        ttk.Label(
            body,
            text="示例: v,f 或 alt,left,ctrl+1（组合键用 + 连接）",
            foreground="#666666").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="确定", command=self._ok,
                   style="Small.TButton").pack(side="left", padx=4)
        ttk.Button(buttons, text="取消", command=self._cancel,
                   style="Small.TButton").pack(side="left", padx=4)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.keys_entry.focus_set()
        self.focus_force()

    def _ok(self):
        raw = self.keys_entry.get().replace("，", ",")
        keys = [part.strip().lower() for part in raw.split(",") if part.strip()]
        if not keys:
            messagebox.showerror("组合序列", "请至少填写一个按键", parent=self)
            return
        try:
            for key in keys:
                parse_combo(key)
            gap = to_float(self.gap_entry.get(), "序列间隔", minimum=0,
                           allow_empty=True)
        except ValueError as exc:
            messagebox.showerror("组合序列", str(exc), parent=self)
            return
        self.grab_release()
        self.destroy()
        self.on_result(keys, gap)

    def _cancel(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class ActiveClock:
    def __init__(self):
        self.start_time = None
        self.paused_total = 0.0
        self.pause_started = None
        self.lock = threading.Lock()
        self.resume_event = threading.Event()
        self.resume_event.set()

    def start(self):
        with self.lock:
            self.start_time = time.time()

    def elapsed(self):
        with self.lock:
            if self.start_time is None:
                return 0.0
            now = time.time()
            paused = self.paused_total
            if self.pause_started is not None:
                paused += now - self.pause_started
            return max(now - self.start_time - paused, 0.0)

    def pause(self):
        with self.lock:
            if self.pause_started is None:
                self.pause_started = time.time()
                self.resume_event.clear()

    def resume(self):
        with self.lock:
            if self.pause_started is not None:
                self.paused_total += time.time() - self.pause_started
                self.pause_started = None
                self.resume_event.set()

    def paused(self):
        with self.lock:
            return self.pause_started is not None

    def force_resume(self):
        with self.lock:
            self.resume_event.set()


class PressPacer:
    def __init__(self, gap):
        self.gap = max(float(gap), 0.0)
        self.cond = threading.Condition()
        self.queue = []
        self.next_ticket = 0
        self.pressing = False
        self.last_end = None

    def wait_slot(self, stop_event, clock, resume_event, limit):
        with self.cond:
            ticket = self.next_ticket
            self.next_ticket += 1
            self.queue.append(ticket)
            try:
                while True:
                    if stop_event.is_set():
                        return "stop"
                    if limit is not None and clock.elapsed() >= limit:
                        return "deadline"
                    if not resume_event.is_set():
                        self.cond.wait(0.1)
                        continue
                    now = clock.elapsed()
                    if (self.queue and self.queue[0] == ticket
                            and not self.pressing
                            and (self.last_end is None
                                 or now >= self.last_end + self.gap)):
                        self.queue.pop(0)
                        self.pressing = True
                        return "ok"
                    wait_time = 0.05
                    if self.queue and self.queue[0] == ticket and self.last_end is not None:
                        remain = self.last_end + self.gap - now
                        if remain > 0:
                            wait_time = min(remain, 0.1)
                    self.cond.wait(wait_time)
            finally:
                if ticket in self.queue:
                    self.queue.remove(ticket)
                self.cond.notify_all()

    def mark(self, clock):
        with self.cond:
            self.last_end = clock.elapsed()
            self.pressing = False
            self.cond.notify_all()


class GlobalHotkey:
    HOTKEY_ID = 1

    def __init__(self, out_queue, modifiers, vk):
        self.out = out_queue
        self.modifiers = modifiers
        self.vk = vk
        self.thread_id = 0
        self.ready = threading.Event()
        self.ok = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        self.ready.wait(2.0)
        return self.ok

    def _run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        try:
            self.ok = bool(user32.RegisterHotKey(
                None, self.HOTKEY_ID, self.modifiers, self.vk))
        except Exception:
            self.ok = False
        self.ready.set()
        if not self.ok:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                self.out.put(("hotkey_stop",))
        try:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)
        except Exception:
            pass

    def stop(self):
        if self.thread_id:
            try:
                user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass


class SendEngine:
    def __init__(self, hwnd, opts, stop_event, out_queue, clock, limit=None,
                 pacer=None, on_press=None):
        self.hwnd = hwnd
        self.mode = opts["input_mode"]
        self.activate_first = opts["activate_first"]
        self.hold = max(1, int(opts["hold_ms"])) / 1000.0
        self.keep_focus = bool(opts.get("keep_focus", False))
        self.settle = max(0, int(opts.get("settle_ms", 100))) / 1000.0
        self.scancode = bool(opts.get("scancode", False))
        self.on_press = on_press
        self.post_warned = False
        self.stop_event = stop_event
        self.out = out_queue
        self.clock = clock
        self.limit = limit
        self.pacer = pacer
        self.resume_event = clock.resume_event
        self.last_abort = None

    def log(self, level, message):
        self.out.put(("log", message, level))

    def elapsed(self):
        return self.clock.elapsed()

    def _wait_resume(self):
        while not self.resume_event.is_set():
            if self.stop_event.wait(0.05):
                return False
        return not self.stop_event.is_set()

    def wait(self, seconds):
        target = self.clock.elapsed() + seconds
        while True:
            if self.stop_event.is_set():
                return "stop"
            if self.limit is not None and self.clock.elapsed() >= self.limit:
                return "deadline"
            if not self.resume_event.is_set():
                while not self.resume_event.is_set():
                    if self.stop_event.wait(0.05):
                        return "stop"
                continue
            remaining = target - self.clock.elapsed()
            if remaining <= 0:
                return "ok"
            self.stop_event.wait(min(remaining, 0.1))

    def press(self, task):
        self.last_abort = None
        if self.pacer is None:
            return self._press_task(task)
        state = self.pacer.wait_slot(
            self.stop_event, self.clock, self.resume_event, self.limit)
        if state != "ok":
            return False
        try:
            return self._press_task(task)
        finally:
            self.pacer.mark(self.clock)

    def _press_task(self, task):
        if not self._wait_resume():
            return False
        if not is_window(self.hwnd):
            self.log("err", "目标窗口已失效（可能已关闭）")
            return False
        try:
            if task["kind"] == "seq":
                ok = self._press_sequence(task)
            elif task["kind"] == "key":
                ok = self._press_key(task)
            else:
                ok = self._press_mouse(task)
        except Exception as exc:
            self.log("err", "发送异常: %s" % exc)
            return False
        if ok and self.on_press is not None:
            try:
                self.on_press()
            except Exception:
                pass
        return ok

    def _press_sequence(self, task):
        hold = self._hold_for(task)
        gap = float(task.get("seq_gap", 0.5) or 0)
        ok = True
        for index, vks in enumerate(task["vks_list"]):
            if index > 0:
                if gap > 0:
                    time.sleep(gap)
                if not self._wait_resume():
                    return False
            if not is_window(self.hwnd):
                self.log("err", "目标窗口已失效（可能已关闭）")
                return False
            ok = self._send_vks(vks, hold) and ok
        return ok

    def _activate_messages(self):
        if self.activate_first:
            user32.PostMessageW(self.hwnd, WM_ACTIVATE, WA_ACTIVE, LPARAM(0))
            user32.PostMessageW(self.hwnd, WM_SETFOCUS, 0, LPARAM(0))

    def _hold_for(self, task):
        hold = float(task.get("hold", 0) or 0)
        return hold if hold > 0 else self.hold

    def _hold_wait(self, seconds):
        end = time.time() + seconds
        while True:
            if self.stop_event.is_set():
                self.last_abort = "stop"
                return False
            if not self.resume_event.is_set():
                self.last_abort = "pause"
                return False
            if self.limit is not None and self.clock.elapsed() >= self.limit:
                self.last_abort = "deadline"
                return False
            remaining = end - time.time()
            if remaining <= 0:
                return True
            self.stop_event.wait(min(remaining, 0.05))

    def _press_key(self, task):
        return self._send_vks(task["vks"], self._hold_for(task))

    def _send_vks(self, vks, hold):
        main_vk = vks[-1]
        modifiers = vks[:-1]
        if self.mode == "background":
            self._activate_messages()
            ok = True
            for vk in modifiers:
                ok = post_key_message(self.hwnd, vk, True) and ok
            ok = post_key_message(self.hwnd, main_vk, True) and ok
            held = self._hold_wait(hold)
            ok = post_key_message(self.hwnd, main_vk, False) and ok
            for vk in reversed(modifiers):
                ok = post_key_message(self.hwnd, vk, False) and ok
            if not ok and not self.post_warned:
                self.post_warned = True
                self.log("warn", "后台消息被拒绝（游戏可能以管理员运行或被保护），"
                                 "请改用前台模拟，或用 run_admin.bat 以管理员身份运行")
            return ok and held
        previous, root = self._prepare_foreground()
        if root is None:
            return False
        try:
            if not self._verify_foreground(root):
                return False
            send_key = send_input_key_scancode if self.scancode else send_input_key
            ok = True
            for vk in modifiers:
                ok = send_key(vk, True) and ok
            ok = send_key(main_vk, True) and ok
            held = self._hold_wait(hold)
            ok = send_key(main_vk, False) and ok
            for vk in reversed(modifiers):
                ok = send_key(vk, False) and ok
            if not ok:
                self.log("warn", "SendInput 未生效（可能被系统拦截），"
                                 "请尝试以管理员身份运行本工具")
            return ok and held
        finally:
            self._restore_focus(previous)

    def _press_mouse(self, task):
        hold = self._hold_for(task)
        if self.mode == "background":
            self._activate_messages()
            ok = post_mouse_down(self.hwnd, task["x"], task["y"], task["button"])
            held = self._hold_wait(hold)
            ok = post_mouse_up(self.hwnd, task["x"], task["y"], task["button"]) and ok
            return ok and held
        previous, root = self._prepare_foreground()
        if root is None:
            return False
        try:
            if not self._verify_foreground(root):
                return False
            point = wintypes.POINT(task["x"], task["y"])
            user32.ClientToScreen(self.hwnd, ctypes.byref(point))
            user32.SetCursorPos(point.x, point.y)
            time.sleep(0.03)
            ok = send_input_mouse(task["button"], True)
            held = self._hold_wait(hold)
            ok = send_input_mouse(task["button"], False) and ok
            if not ok:
                self.log("warn", "SendInput 未生效（可能被系统拦截），"
                                 "请尝试以管理员身份运行本工具")
            return ok and held
        finally:
            self._restore_focus(previous)

    def _prepare_foreground(self):
        previous = user32.GetForegroundWindow()
        root = user32.GetAncestor(self.hwnd, GA_ROOT) or self.hwnd
        if not is_window(root):
            self.log("err", "目标窗口已失效，无法切到前台")
            return None, None
        if user32.GetForegroundWindow() != root:
            if not force_foreground(root):
                current = user32.GetForegroundWindow()
                name = window_display(current) if current and is_window(current) else "无"
                self.log("err", "无法激活目标窗口，当前前台窗口: %s。"
                                 "如游戏以管理员身份运行，请同样以管理员身份运行本工具" % name)
                return None, None
            if self.settle > 0:
                time.sleep(self.settle)
        return previous, root

    def _verify_foreground(self, root):
        current = user32.GetForegroundWindow()
        if current == root:
            return True
        name = window_display(current) if current and is_window(current) else "无"
        self.log("warn", "发送瞬间目标窗口不在前台（当前: %s），已跳过本次发送" % name)
        return False

    def _restore_focus(self, previous):
        if self.keep_focus:
            return
        time.sleep(0.12)
        if previous and is_window(previous) and user32.GetForegroundWindow() != previous:
            force_foreground(previous)


class RunSession:
    def __init__(self, hwnd, tasks, opts, out_queue):
        self.hwnd = hwnd
        self.tasks = tasks
        self.opts = opts
        self.out = out_queue
        self.stop_event = threading.Event()
        self.clock = ActiveClock()
        self.limit_seconds = None
        if opts["total_minutes"] > 0:
            self.limit_seconds = opts["total_minutes"] * 60.0
        self.loop_count = int(opts.get("loop_count", 0) or 0)
        gap = float(opts.get("press_gap", 0) or 0)
        has_sequence = any(task.get("kind") == "seq" for task in tasks)
        self.pacer = PressPacer(gap) if (gap > 0 or has_sequence) else None
        self.threads = []
        self.previous_foreground = None
        self.press_lock = threading.Lock()
        self.press_count = 0
        self.planned_seconds = None
        self.planned_presses = None
        self._compute_plan()

    def _compute_plan(self):
        hold = max(1, int(self.opts["hold_ms"])) / 1000.0
        gap = float(self.opts.get("press_gap", 0) or 0)
        cap = self.limit_seconds
        if self.opts["run_mode"] == "sequential":
            cycle = sum(
                hold + max(float(task["interval"]), gap)
                for task in self.tasks)
            if self.loop_count > 0:
                estimate = self.loop_count * cycle
                if self.tasks:
                    estimate -= max(float(self.tasks[-1]["interval"]), gap)
                estimate = max(estimate, 0.0)
                presses = self.loop_count * len(self.tasks)
            elif cap is not None:
                estimate = cap
                presses = int(cap / max(cycle, 0.001)) * len(self.tasks)
            else:
                self.planned_seconds = None
                self.planned_presses = None
                return
            if cap is not None:
                estimate = min(estimate, cap)
            self.planned_seconds = estimate
            self.planned_presses = presses
            return
        durations = []
        counts = []
        for task in self.tasks:
            interval = max(float(task["interval"]), 0.001)
            spacing = max(interval, gap)
            effective = cap
            if task["mode"] == "count":
                count = int(task["value"])
                duration = count * hold + max(count - 1, 0) * spacing
                if effective is not None and duration > effective:
                    count = max(1, int(effective / (hold + spacing)))
                    duration = effective
            else:
                duration = float(task["value"]) + hold
                if effective is not None:
                    duration = min(duration, effective)
                period = hold + spacing
                count = int(math.floor(max(duration - hold, 0) / period)) + 1
            durations.append(duration)
            counts.append(max(count, 0))
        planned = max(durations) if durations else 0.0
        if cap is not None:
            planned = min(planned, cap)
        self.planned_seconds = planned
        self.planned_presses = sum(counts)

    def _count_press(self):
        with self.press_lock:
            self.press_count += 1

    def snapshot(self):
        with self.press_lock:
            presses = self.press_count
        elapsed = self.clock.elapsed()
        remaining = None
        if self.planned_seconds is not None:
            remaining = max(self.planned_seconds - elapsed, 0.0)
        return {
            "elapsed": elapsed,
            "presses": presses,
            "planned": self.planned_seconds,
            "remaining": remaining,
            "planned_presses": self.planned_presses,
            "paused": self.clock.paused(),
        }

    def active(self):
        if self.stop_event.is_set():
            return False
        if self.limit_seconds is not None and self.clock.elapsed() >= self.limit_seconds:
            return False
        return True

    def start(self):
        self.clock.start()
        self.previous_foreground = user32.GetForegroundWindow()
        if self.opts["run_mode"] == "sequential":
            self.threads = [threading.Thread(target=self._sequential, daemon=True)]
        else:
            self.threads = [
                threading.Thread(target=self._parallel, args=(i, t), daemon=True)
                for i, t in enumerate(self.tasks)
            ]
        for thread in self.threads:
            thread.start()
        threading.Thread(target=self._monitor, daemon=True).start()

    def stop(self):
        self.stop_event.set()
        self.clock.force_resume()

    def pause(self):
        self.clock.pause()

    def resume(self):
        self.clock.resume()

    def is_paused(self):
        return self.clock.paused()

    def _monitor(self):
        for thread in self.threads:
            thread.join()
        if self.opts["input_mode"] == "foreground" and self.opts.get("keep_focus"):
            previous = self.previous_foreground
            if previous and is_window(previous) and user32.GetForegroundWindow() != previous:
                force_foreground(previous)
        if self.stop_event.is_set():
            reason = "stopped"
        elif self.limit_seconds is not None and self.clock.elapsed() >= self.limit_seconds:
            reason = "deadline"
        else:
            reason = "finished"
        self.out.put(("session_end", reason))

    def _press_retry(self, engine, task):
        attempts = 0
        while True:
            if not self.active():
                return "abort"
            if engine.press(task):
                return "ok"
            if not self.active():
                return "abort"
            if engine.last_abort == "pause":
                continue
            attempts += 1
            if attempts >= 5:
                return "error"
            if engine.wait(0.2) != "ok":
                return "abort"

    def _abort_reason(self):
        if self.stop_event.is_set():
            return "已停止"
        return "已结束"

    def _parallel(self, index, task):
        ui_index = task.get("ui_index", index)
        self.out.put(("status", ui_index, "运行中"))
        engine = SendEngine(self.hwnd, self.opts, self.stop_event, self.out,
                            self.clock, self.limit_seconds,
                            pacer=self.pacer, on_press=self._count_press)
        result = "已完成"
        try:
            if task["mode"] == "count":
                total = task["value"]
                for i in range(total):
                    if not self.active():
                        result = self._abort_reason()
                        break
                    state = self._press_retry(engine, task)
                    if state == "error":
                        result = "错误"
                        engine.log("err", "任务%d: 连续发送失败，目标窗口可能已关闭"
                                   % (ui_index + 1))
                        break
                    if state != "ok":
                        result = self._abort_reason()
                        break
                    if i < total - 1:
                        if engine.wait(task["interval"]) != "ok":
                            result = self._abort_reason()
                            break
            else:
                end = engine.elapsed() + task["value"]
                while True:
                    if not self.active():
                        result = self._abort_reason()
                        break
                    remaining = end - engine.elapsed()
                    if remaining <= 0:
                        break
                    state = self._press_retry(engine, task)
                    if state == "error":
                        result = "错误"
                        engine.log("err", "任务%d: 连续发送失败，目标窗口可能已关闭"
                                   % (ui_index + 1))
                        break
                    if state != "ok":
                        result = self._abort_reason()
                        break
                    if engine.wait(min(task["interval"], max(remaining, 0.001))) != "ok":
                        result = self._abort_reason()
                        break
        except Exception as exc:
            result = "错误"
            engine.log("err", "任务%d 异常: %s" % (ui_index + 1, exc))
        self.out.put(("status", ui_index, result))
        self.out.put(("log", "任务%d 结束: %s" % (ui_index + 1, result),
                      "warn" if result != "已完成" else "info"))

    def _sequential(self):
        count = len(self.tasks)
        engine = SendEngine(self.hwnd, self.opts, self.stop_event, self.out,
                            self.clock, self.limit_seconds,
                            pacer=self.pacer, on_press=self._count_press)
        for idx, task in enumerate(self.tasks):
            self.out.put(("status", task.get("ui_index", idx), "待命"))
        if self.loop_count > 0:
            mode_text = "循环 %d 次" % self.loop_count
        elif self.limit_seconds is not None:
            mode_text = "按总时长运行"
        else:
            mode_text = "循环直到手动停止"
        self.out.put(("log", "顺序模式：%s（任务的次数/时长在顺序模式下不生效）"
                      % mode_text, "info"))
        fatal = False
        cycles_done = 0
        try:
            while (not fatal and self.active()
                   and (self.loop_count <= 0 or cycles_done < self.loop_count)):
                cycle_aborted = False
                for idx, task in enumerate(self.tasks):
                    if fatal or not self.active():
                        cycle_aborted = True
                        break
                    ui_index = task.get("ui_index", idx)
                    self.out.put(("status", ui_index, "运行中"))
                    state = self._press_retry(engine, task)
                    if state == "error":
                        engine.log("err", "连续发送失败，目标窗口可能已关闭")
                        fatal = True
                        cycle_aborted = True
                        break
                    if state != "ok":
                        cycle_aborted = True
                        break
                    last_press = (self.loop_count > 0
                                  and cycles_done == self.loop_count - 1
                                  and idx == count - 1)
                    if not last_press:
                        if engine.wait(task["interval"]) != "ok":
                            cycle_aborted = True
                            break
                    self.out.put(("status", ui_index, "待命"))
                if cycle_aborted:
                    break
                cycles_done += 1
        except Exception as exc:
            fatal = True
            engine.log("err", "顺序模式异常: %s" % exc)
        completed = self.loop_count > 0 and cycles_done >= self.loop_count
        if completed:
            for idx, task in enumerate(self.tasks):
                self.out.put(("status", task.get("ui_index", idx), "已完成"))
            self.out.put(("log", "顺序模式结束: 已完成 %d 次循环" % cycles_done, "info"))
            return
        if self.stop_event.is_set():
            label = "已停止"
        elif self.limit_seconds is not None and self.clock.elapsed() >= self.limit_seconds:
            label = "已结束"
        elif fatal:
            label = "错误"
        else:
            label = "已停止"
        for idx, task in enumerate(self.tasks):
            self.out.put(("status", task.get("ui_index", idx), label))
        self.out.put(("log", "顺序模式结束: %s（完成 %d 次循环）"
                      % (label, cycles_done), "info"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("游戏后台按键助手")
        self.geometry("980x700")
        self.minsize(800, 540)

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except Exception:
            pass
        font = ("Microsoft YaHei UI", 9)
        style.configure(".", font=font)
        style.configure("Treeview", rowheight=24)
        style.configure("Small.TButton", padding=(5, 1))
        style.configure("TLabelframe", padding=4)
        style.configure("Profile.TButton", padding=(6, 1))
        style.configure("ProfileActive.TButton", padding=(6, 1),
                        font=("Microsoft YaHei UI", 9, "bold"))
        self.option_add("*Font", font)

        self.tasks = []
        self.profiles = []
        self.active_profile = 0
        self.seq_keys = []
        self.seq_gap = 0.5
        self.top_windows = []
        self.child_windows = []
        self.msg_queue = queue.Queue()
        self.session = None
        self.running = False

        self._build_ui()
        self.refresh_windows()
        self._load_config()
        if not self.profiles:
            self.profiles = self._default_profiles()
            current_settings = self._collect_settings()
            for profile in self.profiles:
                profile["settings"] = dict(current_settings)
        self._activate_profile(
            min(max(self.active_profile, 0), len(self.profiles) - 1),
            log=False, store=False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._on_window_resize)
        self.after(120, self._poll)
        self.log("提示：游戏客户端（DirectInput/原始输入）请使用“前台模拟”，")
        if getattr(sys, "frozen", False):
            self.log("      若游戏以管理员运行导致无法发送输入，请右键本程序 → 以管理员身份运行。", "warn")
        else:
            self.log("      并可由 run_admin.bat 以管理员身份启动，避免游戏权限更高导致失效。", "warn")
        if is_admin():
            self.log("当前以管理员权限运行")
        else:
            self.log("当前为普通权限；若游戏以管理员运行，本工具可能无法发送输入", "warn")
        self.hotkey = GlobalHotkey(
            self.msg_queue,
            MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT,
            0x51)
        if self.hotkey.start():
            self.log("全局停止快捷键已启用：Ctrl+Alt+Shift+Q")
        else:
            self.log("全局停止快捷键 Ctrl+Alt+Shift+Q 注册失败"
                     "（可能被其它程序或另一个本工具实例占用）", "warn")
        self.log("运行控制：总时长/循环次数填 0 表示不限；循环次数仅用于顺序循环")

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)
        self.rowconfigure(3, weight=2)

        target = ttk.LabelFrame(self, text="① 目标窗口")
        target.grid(row=0, column=0, sticky="we", padx=8, pady=(6, 3))
        target.columnconfigure(1, weight=1)

        ttk.Label(target, text="窗口列表:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.window_combo = ttk.Combobox(target, state="readonly")
        self.window_combo.grid(row=0, column=1, sticky="we", padx=4)
        self.window_combo.bind("<<ComboboxSelected>>", self._on_window_selected)
        ttk.Button(target, text="刷新窗口", command=self.refresh_windows,
                   width=7, style="Small.TButton").grid(row=0, column=2, padx=4)
        ttk.Button(target, text="鼠标拾取窗口", command=self._pick_window,
                   width=11, style="Small.TButton").grid(row=0, column=3, padx=4)

        ttk.Label(target, text="发送目标:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.child_combo = ttk.Combobox(target, state="readonly")
        self.child_combo.grid(row=1, column=1, sticky="we", padx=4)
        ttk.Label(target, text="无效时可选子窗口（渲染/输入窗口）").grid(
            row=1, column=2, columnspan=2, sticky="w", padx=4)

        frame = ttk.LabelFrame(self, text="② 任务设置（每一行是一个任务，各自独立计时）")
        frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=3)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = ("use", "idx", "type", "target", "interval", "hold", "mode", "value", "status")
        headers = ("启用", "序号", "类型", "按键/坐标", "间隔(秒)", "按住(秒)",
                   "方式", "次数/分钟", "状态")
        widths = (46, 46, 80, 170, 80, 80, 90, 90, 80)
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=4)
        for column, header, width in zip(columns, headers, widths):
            self.tree.heading(column, text=header)
            self.tree.column(column, width=width, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.tag_configure("run", foreground="#0055cc")
        self.tree.tag_configure("done", foreground="#007700")
        self.tree.tag_configure("err", foreground="#cc0000")
        self.tree.bind("<Double-1>", self._on_tree_double)
        self.tree.bind("<Button-1>", self._on_tree_click)

        bar = ttk.Frame(frame)
        bar.grid(row=1, column=0, columnspan=2, sticky="we", padx=4, pady=(0, 2))
        self.all_var = tk.BooleanVar(value=True)
        self.all_check = ttk.Checkbutton(
            bar, text="全选", variable=self.all_var, command=self._set_all_enabled)
        self.all_check.pack(side="left", padx=(0, 8))
        self.profile_tabs = ttk.Frame(bar)
        self.profile_tabs.pack(side="left")
        profile_actions = ttk.Frame(bar)
        profile_actions.pack(side="right")
        ttk.Button(profile_actions, text="新建", command=self._new_profile,
                   width=4, style="Small.TButton").pack(side="left", padx=2)
        ttk.Button(profile_actions, text="改名", command=self._rename_profile,
                   width=4, style="Small.TButton").pack(side="left", padx=2)
        ttk.Button(profile_actions, text="删除", command=self._delete_profile,
                   width=4, style="Small.TButton").pack(side="left", padx=2)

        editor = ttk.Frame(frame)
        editor.grid(row=2, column=0, columnspan=2, sticky="we", padx=4, pady=(0, 2))

        ttk.Label(editor, text="类型:").grid(row=0, column=0, sticky="w", padx=(0, 2), pady=2)
        self.type_combo = ttk.Combobox(
            editor, values=("按键", "组合序列", "鼠标左键", "鼠标右键"),
            state="readonly", width=7)
        self.type_combo.current(0)
        self.type_combo.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_editor_state())

        ttk.Label(editor, text="按键:").grid(row=0, column=2, sticky="w", padx=(8, 2))
        key_box = ttk.Frame(editor)
        key_box.grid(row=0, column=3, sticky="w", padx=2)
        self.key_entry = ttk.Entry(key_box, width=7)
        self.key_entry.pack(side="left")
        self.capture_btn = ttk.Button(
            key_box, text="捕获", command=self._capture_key, width=5, style="Small.TButton")
        self.capture_btn.pack(side="left", padx=(3, 0))

        ttk.Label(editor, text="坐标:").grid(row=0, column=4, sticky="w", padx=(8, 2))
        self.pos_entry = ttk.Entry(editor, width=6)
        self.pos_entry.grid(row=0, column=5, sticky="w", padx=2)
        self.pick_pos_btn = ttk.Button(editor, text="拾取", command=self._pick_pos,
                                       width=4, style="Small.TButton")
        self.pick_pos_btn.grid(row=0, column=6, sticky="w", padx=2)

        ttk.Label(editor, text="按住(秒,0=默认):").grid(
            row=0, column=7, sticky="w", padx=(8, 2))
        self.task_hold_entry = ttk.Entry(editor, width=5)
        self.task_hold_entry.insert(0, "0")
        self.task_hold_entry.grid(row=0, column=8, sticky="w", padx=2)

        ttk.Label(editor, text="间隔(秒):").grid(row=1, column=0, sticky="w", padx=(0, 2), pady=2)
        self.interval_entry = ttk.Entry(editor, width=5)
        self.interval_entry.insert(0, "1")
        self.interval_entry.grid(row=1, column=1, sticky="w", padx=2)

        ttk.Label(editor, text="方式:").grid(row=1, column=2, sticky="w", padx=(8, 2))
        self.mode_combo = ttk.Combobox(
            editor, values=("次数", "时长(分钟)"), state="readonly", width=7)
        self.mode_combo.current(0)
        self.mode_combo.grid(row=1, column=3, sticky="w", padx=2)

        ttk.Label(editor, text="次数:").grid(row=1, column=4, sticky="w", padx=(8, 2))
        self.value_entry = ttk.Entry(editor, width=6)
        self.value_entry.insert(0, "100")
        self.value_entry.grid(row=1, column=5, sticky="w", padx=2)

        buttons = ttk.Frame(editor)
        buttons.grid(row=1, column=6, columnspan=4, sticky="w", padx=(12, 0))
        ttk.Button(buttons, text="添加", command=self._add_task,
                   width=4, style="Small.TButton").pack(side="left", padx=2)
        ttk.Button(buttons, text="更新", command=self._update_task,
                   width=4, style="Small.TButton").pack(side="left", padx=2)
        ttk.Button(buttons, text="删除", command=self._delete_task,
                   width=4, style="Small.TButton").pack(side="left", padx=2)
        ttk.Button(buttons, text="清空", command=self._clear_tasks,
                   width=4, style="Small.TButton").pack(side="left", padx=2)
        ttk.Button(buttons, text="测试", command=self._test_once,
                   width=4, style="Small.TButton").pack(side="left", padx=2)

        run = ttk.LabelFrame(self, text="③ 运行控制（随任务序列保存）")
        run.grid(row=2, column=0, sticky="we", padx=8, pady=3)

        self.mode_var = tk.StringVar(value="parallel")
        ttk.Radiobutton(run, text="并行计时",
                        variable=self.mode_var, value="parallel").grid(
            row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Radiobutton(run, text="顺序循环",
                        variable=self.mode_var, value="sequential").grid(
            row=0, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(run, text="总时长(分):").grid(
            row=0, column=2, sticky="e", padx=(16, 2))
        self.total_entry = ttk.Entry(run, width=6)
        self.total_entry.insert(0, "0")
        self.total_entry.grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(run, text="按住(ms):").grid(
            row=0, column=4, sticky="e", padx=(16, 2))
        self.hold_entry = ttk.Entry(run, width=5)
        self.hold_entry.insert(0, "30")
        self.hold_entry.grid(row=0, column=5, sticky="w", padx=2)

        self.input_var = tk.StringVar(value="background")
        ttk.Radiobutton(run, text="后台消息",
                        variable=self.input_var, value="background").grid(
            row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Radiobutton(run, text="前台模拟",
                        variable=self.input_var, value="foreground").grid(
            row=1, column=1, sticky="w", padx=6, pady=2)
        self.keep_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            run, text="保持焦点",
            variable=self.keep_var).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=(16, 2))
        ttk.Label(run, text="激活(ms):").grid(
            row=1, column=4, sticky="e", padx=(16, 2))
        self.settle_entry = ttk.Entry(run, width=5)
        self.settle_entry.insert(0, "100")
        self.settle_entry.grid(row=1, column=5, sticky="w", padx=2)
        ttk.Label(run, text="按键间隔(秒):").grid(
            row=1, column=6, sticky="e", padx=(16, 2))
        self.gap_entry = ttk.Entry(run, width=5)
        self.gap_entry.insert(0, "3")
        self.gap_entry.grid(row=1, column=7, sticky="w", padx=2)

        self.activate_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run, text="先发激活",
            variable=self.activate_var).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6)
        self.scan_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run, text="扫描码",
            variable=self.scan_var).grid(
            row=2, column=2, columnspan=2, sticky="w", padx=(16, 2))

        self.start_btn = ttk.Button(
            run, text="开始运行", command=self._start, width=8, style="Small.TButton")
        self.start_btn.grid(row=2, column=4, sticky="w", padx=6, pady=(4, 6))
        self.stop_btn = ttk.Button(
            run, text="停止", command=self._stop, width=5, state="disabled",
            style="Small.TButton")
        self.stop_btn.grid(row=2, column=5, sticky="w", padx=6, pady=(4, 6))
        self.pause_btn = ttk.Button(
            run, text="暂停", command=self._pause_resume, width=5, state="disabled",
            style="Small.TButton")
        self.pause_btn.grid(row=2, column=6, sticky="w", padx=6, pady=(4, 6))
        ttk.Label(run, text="循环(0=∞):").grid(
            row=2, column=7, sticky="e", padx=(16, 2))
        self.loop_entry = ttk.Entry(run, width=5)
        self.loop_entry.insert(0, "0")
        self.loop_entry.grid(row=2, column=8, sticky="w", padx=2)
        self.status_var = tk.StringVar(value="就绪")

        bottom = ttk.Frame(self)
        bottom.grid(row=3, column=0, sticky="nsew", padx=8, pady=(3, 6))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)

        log_frame = ttk.LabelFrame(bottom, text="日志")
        log_frame.grid(row=0, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=3, width=40, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns", pady=4)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.tag_configure("err", foreground="#cc0000")
        self.log_text.tag_configure("ok", foreground="#007700")
        self.log_text.tag_configure("warn", foreground="#aa6600")

        progress_frame = ttk.LabelFrame(bottom, text="进度")
        progress_frame.grid(row=1, column=0, sticky="we", pady=(4, 0))
        self.progress_var = tk.StringVar(value="未开始")
        self.progress_label = ttk.Label(
            progress_frame, textvariable=self.progress_var,
            justify="left", wraplength=860)
        self.progress_label.pack(anchor="w", fill="x", padx=6, pady=(3, 1))
        self.progress_bar = ttk.Progressbar(
            progress_frame, maximum=100.0, value=0.0)
        self.progress_bar.pack(fill="x", padx=6, pady=(0, 4))

        self._sync_editor_state()

    def _on_window_resize(self, event):
        if event.widget is not self:
            return
        wrap = max(320, event.width - 80)
        if wrap == getattr(self, "_wrap_width", None):
            return
        self._wrap_width = wrap
        try:
            self.progress_label.configure(wraplength=wrap)
        except Exception:
            pass

    def log(self, message, level="info"):
        stamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "[%s] %s\n" % (stamp, message), level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        if int(self.log_text.index("end-1c").split(".")[0]) > 1500:
            self.log_text.delete("1.0", "500.0")

    def _poll(self):
        while True:
            try:
                message = self.msg_queue.get_nowait()
            except queue.Empty:
                break
            kind = message[0]
            if kind == "log":
                self.log(message[1], message[2])
            elif kind == "status":
                self._set_task_status(message[1], message[2])
            elif kind == "session_end":
                self._on_session_end(message[1])
            elif kind == "hotkey_stop":
                self._on_hotkey_stop()
        if self.running and self.session is not None:
            self._update_progress()
        self.after(150, self._poll)

    def _update_progress(self):
        snapshot = self.session.snapshot()
        elapsed_min = snapshot["elapsed"] / 60.0
        planned = snapshot["planned"]
        parts = []
        if snapshot.get("paused"):
            parts.append("已暂停")
        if planned:
            total_min = planned / 60.0
            remaining_min = (snapshot["remaining"] or 0.0) / 60.0
            count = snapshot["planned_presses"]
            if count is not None:
                parts.append("计划约 %s 分钟（预计 %d 次）"
                             % (format_minutes_value(total_min), count))
            else:
                parts.append("计划约 %s 分钟" % format_minutes_value(total_min))
            parts.append("已运行 %s 分钟" % format_minutes_value(elapsed_min))
            parts.append("已发送 %d 次" % snapshot["presses"])
            parts.append("剩余约 %s 分钟" % format_minutes_value(remaining_min))
            self.progress_bar.configure(
                value=min(100.0, snapshot["elapsed"] / planned * 100.0))
        else:
            parts.append("未设置总时长")
            parts.append("已运行 %s 分钟" % format_minutes_value(elapsed_min))
            parts.append("已发送 %d 次" % snapshot["presses"])
            self.progress_bar.configure(value=0.0)
        self.progress_var.set(" ｜ ".join(parts))

    def refresh_windows(self, select_hwnd=None):
        current = select_hwnd
        if current is None:
            current = self._current_root_hwnd()
        self.top_windows = list_top_windows()
        self.window_combo["values"] = [
            window_display(item[0]) for item in self.top_windows]
        if current:
            for index, (hwnd, _title, _cls) in enumerate(self.top_windows):
                if hwnd == current:
                    self.window_combo.current(index)
                    self._on_window_selected()
                    break
        if not self.top_windows:
            self.child_combo["values"] = []
            self.child_combo.set("")
            self.child_windows = []
        self.log("窗口列表已刷新，共 %d 个窗口" % len(self.top_windows))

    def _current_root_hwnd(self):
        index = self.window_combo.current()
        if 0 <= index < len(self.top_windows):
            return self.top_windows[index][0]
        return None

    def _on_window_selected(self, event=None):
        hwnd = self._current_root_hwnd()
        if not hwnd:
            return
        self._populate_children(hwnd)
        self.log("已选择窗口: %s" % self.window_combo.get())

    def _populate_children(self, parent, preferred=None):
        focus = focused_hwnd(parent)
        self.child_windows = [(parent, "<主窗口> [%s]" % class_name(parent))]
        for child in list_child_windows(parent):
            depth = 0
            walker = user32.GetParent(child)
            while walker and walker != parent and depth < 6:
                depth += 1
                walker = user32.GetParent(walker)
            title = safe_child_text(child)
            name = "  " * depth + class_name(child)
            if title:
                name += " - " + title[:30]
            if focus and child == focus:
                name += "  【输入焦点】"
            self.child_windows.append((child, name))
        self.child_combo["values"] = [item[1] for item in self.child_windows]
        selected = 0
        if preferred:
            for index, (hwnd, _name) in enumerate(self.child_windows):
                if hwnd == preferred:
                    selected = index
                    break
        else:
            for index, (hwnd, _name) in enumerate(self.child_windows):
                if focus and hwnd == focus:
                    selected = index
                    break
        self.child_combo.current(selected)

    def _target_hwnd(self):
        if self.child_windows:
            index = self.child_combo.current()
            if 0 <= index < len(self.child_windows):
                return self.child_windows[index][0]
        return self._current_root_hwnd()

    def _pick_window(self):
        self.iconify()
        self.after(400, lambda: self.after(2600, self._pick_window_capture))

    def _pick_window_capture(self):
        try:
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            hwnd = user32.WindowFromPoint(point)
            my_root = user32.GetAncestor(self.winfo_id(), GA_ROOT)
            if not hwnd or user32.GetAncestor(hwnd, GA_ROOT) == my_root:
                self.log("拾取失败：请把鼠标移到目标程序窗口上（不要停在本程序上）", "err")
                return
            root = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
            self.refresh_windows(select_hwnd=root)
            if self._current_root_hwnd() != root:
                self.log("拾取到的窗口不在列表中，请先刷新窗口列表", "err")
                return
            self._populate_children(root, preferred=hwnd)
            self.log("已拾取目标: %s" % window_display(root), "ok")
            if hwnd != root:
                self.log("已自动选中子窗口: %s [%s]" % (
                    safe_child_text(hwnd) or "(无标题)", class_name(hwnd)), "ok")
            self.status_var.set("窗口拾取完成")
        finally:
            self.deiconify()
            self.lift()

    def _pick_pos(self):
        hwnd = self._target_hwnd()
        if not hwnd or not is_window(hwnd):
            messagebox.showerror("无法拾取", "请先在①中选择有效的目标窗口", parent=self)
            return
        if user32.IsIconic(hwnd):
            messagebox.showwarning("无法拾取", "目标窗口已最小化，无法用鼠标拾取坐标", parent=self)
            return
        self.iconify()
        self.after(400, lambda: self.after(2600, self._pick_pos_capture))

    def _pick_pos_capture(self):
        try:
            hwnd = self._target_hwnd()
            if not hwnd or not is_window(hwnd):
                self.log("拾取坐标失败：目标窗口无效", "err")
                return
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.ScreenToClient(hwnd, ctypes.byref(point))
            if self.type_combo.get() == "按键":
                self.type_combo.set("鼠标左键")
                self._sync_editor_state()
            self.pos_entry.delete(0, "end")
            self.pos_entry.insert(0, "%d,%d" % (point.x, point.y))
            self.log("已拾取坐标: %d,%d（相对目标窗口客户区）" % (point.x, point.y), "ok")
            self.status_var.set("坐标拾取完成")
        finally:
            self.deiconify()
            self.lift()

    def _sync_editor_state(self):
        kind = self.type_combo.get()
        if kind == "按键":
            self.key_entry.configure(state="normal")
            self.capture_btn.configure(
                state="normal", text="捕获", command=self._capture_key)
            self.pos_entry.configure(state="disabled")
            self.pick_pos_btn.configure(state="disabled")
        elif kind == "组合序列":
            self.key_entry.configure(state="normal")
            self.key_entry.delete(0, "end")
            self.key_entry.insert(
                0, " → ".join(self.seq_keys) if self.seq_keys else "（点击编辑序列）")
            self.key_entry.configure(state="readonly")
            self.capture_btn.configure(
                state="normal", text="编辑序列", command=self._edit_sequence)
            self.pos_entry.configure(state="disabled")
            self.pick_pos_btn.configure(state="disabled")
        else:
            self.key_entry.configure(state="disabled")
            self.capture_btn.configure(
                state="disabled", text="捕获", command=self._capture_key)
            self.pos_entry.configure(state="normal")
            self.pick_pos_btn.configure(state="normal")

    def _edit_sequence(self):
        SequenceDialog(self, self.seq_keys, self.seq_gap, self._on_sequence_edited)

    def _on_sequence_edited(self, keys, gap):
        self.seq_keys = list(keys)
        self.seq_gap = float(gap)
        self.type_combo.set("组合序列")
        self._sync_editor_state()
        self.log("组合序列已设置: %s（键间隔 %g 秒）" % (
            " → ".join(self.seq_keys), self.seq_gap), "ok")

    def _capture_key(self):
        dialog = getattr(self, "capture_dialog", None)
        if dialog is not None and dialog.winfo_exists():
            dialog.focus_force()
            return
        self.capture_dialog = KeyCaptureDialog(self, self._on_key_captured)

    def _on_key_captured(self, combo):
        self.capture_dialog = None
        if not combo:
            self.log("已取消按键捕获")
            return
        self.type_combo.set("按键")
        self._sync_editor_state()
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, combo)
        self.log("已捕获按键: %s" % combo, "ok")

    def _collect_editor(self):
        kind_cn = self.type_combo.get()
        interval = to_float(self.interval_entry.get(), "间隔")
        if interval <= 0:
            raise ValueError("间隔必须大于 0")
        mode_cn = self.mode_combo.get()
        mode = "count" if mode_cn == "次数" else "time"
        raw_value = self.value_entry.get()
        if mode == "count":
            value = int(to_float(raw_value, "次数", minimum=1))
        else:
            value = to_float(raw_value, "时长(分钟)", minimum=0.01) * 60.0
        hold_value = to_float(
            self.task_hold_entry.get(), "按住时长(秒)", minimum=0, allow_empty=True)
        if kind_cn == "组合序列":
            if not self.seq_keys:
                raise ValueError("请先点“编辑序列”设置组合序列")
            return {
                "kind": "seq", "text": " → ".join(self.seq_keys),
                "seq_keys": list(self.seq_keys), "seq_gap": float(self.seq_gap),
                "interval": interval, "mode": mode, "value": value,
                "hold": hold_value,
            }
        if kind_cn == "按键":
            text = self.key_entry.get().strip().lower()
            parse_combo(text)
            return {
                "kind": "key", "text": text, "interval": interval,
                "mode": mode, "value": value, "hold": hold_value,
            }
        pos_text = self.pos_entry.get().strip().replace("，", ",")
        parts = [p for p in pos_text.split(",") if p.strip()]
        if len(parts) != 2:
            raise ValueError("坐标格式应为 X,Y")
        try:
            x = int(float(parts[0]))
            y = int(float(parts[1]))
        except ValueError:
            raise ValueError("坐标必须是数字")
        button = "left" if kind_cn == "鼠标左键" else "right"
        return {
            "kind": "mouse", "button": button, "x": x, "y": y,
            "text": "%d,%d" % (x, y), "interval": interval,
            "mode": mode, "value": value, "hold": hold_value,
        }

    def _runtime_task(self, task):
        result = dict(task)
        if task["kind"] == "seq":
            keys = task.get("seq_keys") or []
            if not keys:
                raise ValueError("组合序列为空")
            result["vks_list"] = [parse_combo(key) for key in keys]
            result["seq_gap"] = max(0.0, float(task.get("seq_gap", 0.5) or 0))
        elif task["kind"] == "key":
            result["vks"] = parse_combo(task["text"])
        interval = float(task["interval"])
        if interval <= 0:
            raise ValueError("间隔必须大于 0")
        result["interval"] = interval
        if result["mode"] == "count":
            result["value"] = int(result["value"])
            if result["value"] < 1:
                raise ValueError("次数必须 >= 1")
        else:
            result["value"] = float(result["value"])
            if result["value"] <= 0:
                raise ValueError("时长必须大于 0")
        result["hold"] = max(0.0, float(result.get("hold", 0) or 0))
        return result

    def _row_values(self, index, task):
        if task["kind"] == "seq":
            type_cn = "组合序列"
        elif task["kind"] == "key":
            type_cn = "按键"
        elif task.get("button") == "right":
            type_cn = "鼠标右键"
        else:
            type_cn = "鼠标左键"
        mode_cn = "次数" if task["mode"] == "count" else "时长(分钟)"
        if task["mode"] == "count":
            value_text = "%g" % task["value"]
        else:
            value_text = format_minutes(task["value"])
        hold = float(task.get("hold", 0) or 0)
        hold_text = "%g" % hold if hold > 0 else "-"
        check = "☑" if task.get("enabled", True) else "☐"
        return (
            check,
            index + 1,
            type_cn,
            task["text"],
            "%g" % task["interval"],
            hold_text,
            mode_cn,
            value_text,
            task.get("status", "待机"),
        )

    def _row_tags(self, status):
        return {"运行中": ("run",), "已完成": ("done",), "错误": ("err",)}.get(status, ())

    def _rebuild_tree(self):
        self.tree.delete(*self.tree.get_children())
        for index, task in enumerate(self.tasks):
            self.tree.insert(
                "", "end", iid=str(index),
                values=self._row_values(index, task),
                tags=self._row_tags(task.get("status", "待机")))

    def _set_task_status(self, index, status):
        if index >= len(self.tasks):
            return
        self.tasks[index]["status"] = status
        iid = str(index)
        if self.tree.exists(iid):
            self.tree.set(iid, "status", status)
            self.tree.item(iid, tags=self._row_tags(status))

    def _describe(self, task):
        if task["kind"] == "seq":
            type_cn = "组合序列"
        elif task["kind"] == "key":
            type_cn = "按键"
        else:
            type_cn = "鼠标"
        if task["mode"] == "count":
            tail = "共 %d 次" % task["value"]
        else:
            tail = "持续 %s 分钟" % format_minutes(task["value"])
        hold = float(task.get("hold", 0) or 0)
        if hold > 0:
            tail += "，按住 %g 秒" % hold
        if task["kind"] == "seq":
            tail += "，序列内间隔 %g 秒" % float(task.get("seq_gap", 0) or 0)
        return "%s %s，间隔 %g 秒，%s" % (type_cn, task["text"], task["interval"], tail)

    def _add_task(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能修改任务，请先停止", parent=self)
            return
        try:
            task = self._collect_editor()
        except ValueError as exc:
            messagebox.showerror("配置错误", str(exc), parent=self)
            return
        task["enabled"] = True
        task["status"] = "待机"
        self.tasks.append(task)
        self._rebuild_tree()
        self._update_select_all()
        self.log("已添加任务 %d: %s" % (len(self.tasks), self._describe(task)), "ok")

    def _update_task(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能修改任务，请先停止", parent=self)
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先在列表中选中要更新的任务", parent=self)
            return
        index = int(selection[0])
        try:
            task = self._collect_editor()
        except ValueError as exc:
            messagebox.showerror("配置错误", str(exc), parent=self)
            return
        task["enabled"] = self.tasks[index].get("enabled", True)
        task["status"] = "待机"
        self.tasks[index] = task
        self._rebuild_tree()
        self.tree.selection_set(str(index))
        self._update_select_all()
        self.log("已更新任务 %d: %s" % (index + 1, self._describe(task)), "ok")

    def _delete_task(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能修改任务，请先停止", parent=self)
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先在列表中选中要删除的任务", parent=self)
            return
        index = int(selection[0])
        self.tasks.pop(index)
        for task in self.tasks:
            task["status"] = "待机"
        self._rebuild_tree()
        self._update_select_all()
        self.log("已删除任务，剩余 %d 个" % len(self.tasks))

    def _clear_tasks(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能修改任务，请先停止", parent=self)
            return
        if not self.tasks:
            return
        if not messagebox.askyesno("确认", "清空当前任务序列的全部任务？", parent=self):
            return
        self.tasks = []
        self.profiles[self.active_profile]["tasks"] = self.tasks
        self._rebuild_tree()
        self._update_select_all()
        self.log("任务列表已清空")

    def _on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        index = int(iid)
        task = self.tasks[index]
        task["enabled"] = not task.get("enabled", True)
        self.tree.item(iid, values=self._row_values(index, task),
                       tags=self._row_tags(task.get("status", "待机")))
        self._update_select_all()

    def _set_all_enabled(self):
        value = self.all_var.get()
        for task in self.tasks:
            task["enabled"] = value
        self._rebuild_tree()

    def _update_select_all(self):
        self.all_var.set(all(task.get("enabled", True) for task in self.tasks))

    def _default_profiles(self):
        return [{"name": "任务序列%d" % (i + 1), "tasks": [], "settings": {}}
                for i in range(3)]

    def _collect_settings(self):
        return {
            "run_mode": self.mode_var.get(),
            "input_mode": self.input_var.get(),
            "activate_first": self.activate_var.get(),
            "keep_focus": self.keep_var.get(),
            "scancode": self.scan_var.get(),
            "total": self.total_entry.get(),
            "hold": self.hold_entry.get(),
            "settle": self.settle_entry.get(),
            "press_gap": self.gap_entry.get(),
            "loop": self.loop_entry.get(),
        }

    def _apply_settings(self, settings):
        if not isinstance(settings, dict):
            return
        if settings.get("run_mode") in ("parallel", "sequential"):
            self.mode_var.set(settings["run_mode"])
        if settings.get("input_mode") in ("background", "foreground"):
            self.input_var.set(settings["input_mode"])
        self.activate_var.set(bool(settings.get("activate_first", False)))
        self.keep_var.set(bool(settings.get("keep_focus", True)))
        self.scan_var.set(bool(settings.get("scancode", False)))
        for entry, key in (
                (self.total_entry, "total"),
                (self.hold_entry, "hold"),
                (self.settle_entry, "settle"),
                (self.gap_entry, "press_gap"),
                (self.loop_entry, "loop")):
            if settings.get(key) is not None:
                entry.delete(0, "end")
                entry.insert(0, str(settings[key]))

    def _store_current_settings(self):
        if not self.profiles:
            return
        index = min(max(self.active_profile, 0), len(self.profiles) - 1)
        self.profiles[index]["settings"] = self._collect_settings()

    def _activate_profile(self, index, log=True, store=True):
        if store:
            self._store_current_settings()
        index = max(0, min(index, len(self.profiles) - 1))
        self.active_profile = index
        self.tasks = self.profiles[index]["tasks"]
        for task in self.tasks:
            task.setdefault("enabled", True)
            task.setdefault("status", "待机")
        self._rebuild_profile_tabs()
        self._rebuild_tree()
        self._update_select_all()
        self._apply_settings(self.profiles[index].get("settings"))
        if log:
            self.log("已切换到 %s（%d 个任务）" % (
                self.profiles[index]["name"], len(self.tasks)))

    def _rebuild_profile_tabs(self):
        for child in self.profile_tabs.winfo_children():
            child.destroy()
        font = ("Microsoft YaHei UI", 9)
        active_font = ("Microsoft YaHei UI", 9, "bold")
        for index, profile in enumerate(self.profiles):
            active = index == self.active_profile
            text = ("● " if active else "") + profile["name"]
            tk.Button(
                self.profile_tabs, text=text,
                font=active_font if active else font,
                relief="sunken" if active else "raised",
                bd=1, padx=6, pady=1,
                bg="#dce9f7" if active else "#f0f0f0",
                activebackground="#dce9f7",
                command=lambda idx=index: self._switch_profile(idx),
            ).pack(side="left", padx=2)

    def _switch_profile(self, index):
        if self.running:
            messagebox.showinfo("提示", "运行中不能切换任务序列，请先停止", parent=self)
            return
        if index == self.active_profile:
            return
        self._activate_profile(index)

    def _new_profile(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能新建任务序列，请先停止", parent=self)
            return
        existing = {profile["name"] for profile in self.profiles}
        number = len(self.profiles) + 1
        name = "任务序列%d" % number
        while name in existing:
            number += 1
            name = "任务序列%d" % number
        self.profiles.append({
            "name": name,
            "tasks": [],
            "settings": self._collect_settings(),
        })
        self._activate_profile(len(self.profiles) - 1)
        self.log("已新建任务序列: %s" % name, "ok")

    def _rename_profile(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能重命名任务序列，请先停止", parent=self)
            return
        profile = self.profiles[self.active_profile]
        name = simpledialog.askstring(
            "重命名任务序列", "请输入名称：", initialvalue=profile["name"], parent=self)
        if name is None:
            return
        name = name.strip()[:15]
        if not name:
            messagebox.showerror("重命名", "名称不能为空", parent=self)
            return
        for index, other in enumerate(self.profiles):
            if index != self.active_profile and other["name"] == name:
                messagebox.showerror("重命名", "该名称已存在", parent=self)
                return
        profile["name"] = name
        self._rebuild_profile_tabs()
        self.log("任务序列已重命名为: %s" % name, "ok")

    def _delete_profile(self):
        if self.running:
            messagebox.showinfo("提示", "运行中不能删除任务序列，请先停止", parent=self)
            return
        if len(self.profiles) <= 1:
            messagebox.showinfo("提示", "至少保留一个任务序列", parent=self)
            return
        profile = self.profiles[self.active_profile]
        if not messagebox.askyesno(
                "确认", "删除“%s”及其 %d 个任务？" % (profile["name"], len(profile["tasks"])),
                parent=self):
            return
        index = self.active_profile
        self._store_current_settings()
        self.profiles.pop(index)
        self._activate_profile(max(0, index - 1), store=False)
        self.log("已删除任务序列", "warn")

    def _pause_resume(self):
        if not (self.session and self.running):
            return
        if self.session.is_paused():
            self.session.resume()
            self.pause_btn.configure(text="暂停")
            self.status_var.set("运行中…")
            self.log("继续运行", "ok")
        else:
            self.session.pause()
            self.pause_btn.configure(text="继续")
            self.status_var.set("已暂停")
            self.log("已暂停：按“继续”恢复（暂停时间不计入时长）", "warn")
        self._update_progress()

    def _on_tree_double(self, event):
        if event is not None and self.tree.identify_column(event.x) == "#1":
            return
        selection = self.tree.selection()
        if not selection:
            return
        task = self.tasks[int(selection[0])]
        if task["kind"] == "seq":
            self.type_combo.set("组合序列")
            self.seq_keys = list(task.get("seq_keys", []))
            self.seq_gap = float(task.get("seq_gap", 0.5) or 0)
        elif task["kind"] == "key":
            self.type_combo.set("按键")
            self.key_entry.delete(0, "end")
            self.key_entry.insert(0, task["text"])
        else:
            self.type_combo.set("鼠标右键" if task.get("button") == "right" else "鼠标左键")
            self.pos_entry.delete(0, "end")
            self.pos_entry.insert(0, task["text"])
        self.interval_entry.delete(0, "end")
        self.interval_entry.insert(0, "%g" % task["interval"])
        self.mode_combo.set("次数" if task["mode"] == "count" else "时长(分钟)")
        self.value_entry.delete(0, "end")
        if task["mode"] == "count":
            self.value_entry.insert(0, "%g" % task["value"])
        else:
            self.value_entry.insert(0, format_minutes(task["value"]))
        self.task_hold_entry.delete(0, "end")
        self.task_hold_entry.insert(0, "%g" % float(task.get("hold", 0) or 0))
        self._sync_editor_state()

    def _collect_run_opts(self):
        total = to_float(self.total_entry.get(), "总运行时长", minimum=0, allow_empty=True)
        hold = to_float(self.hold_entry.get(), "按键按住时长", minimum=1)
        settle = to_float(self.settle_entry.get(), "激活等待", minimum=0, allow_empty=True)
        gap = to_float(self.gap_entry.get(), "按键间隔", minimum=0, allow_empty=True)
        loop_count = int(to_float(self.loop_entry.get(), "循环次数", minimum=0, allow_empty=True))
        return {
            "run_mode": self.mode_var.get(),
            "input_mode": self.input_var.get(),
            "activate_first": self.activate_var.get(),
            "keep_focus": self.keep_var.get(),
            "scancode": self.scan_var.get(),
            "hold_ms": int(hold),
            "settle_ms": int(settle),
            "press_gap": gap,
            "loop_count": loop_count,
            "total_minutes": total,
        }

    def _test_once(self):
        hwnd = self._target_hwnd()
        if not hwnd or not is_window(hwnd):
            messagebox.showerror("无法测试", "请先在①中选择有效的目标窗口", parent=self)
            return
        try:
            task = self._runtime_task(self._collect_editor())
            opts = self._collect_run_opts()
        except ValueError as exc:
            messagebox.showerror("配置错误", str(exc), parent=self)
            return
        if opts["input_mode"] == "foreground":
            opts["keep_focus"] = False
            opts["settle_ms"] = max(opts["settle_ms"], 250)
        description = self._describe(task)

        def worker():
            engine = SendEngine(hwnd, opts, threading.Event(), self.msg_queue, ActiveClock())
            ok = engine.press(task)
            self.msg_queue.put((
                "log",
                "测试发送%s: %s" % ("成功" if ok else "失败", description),
                "ok" if ok else "err",
            ))

        self.log("正在测试发送（长按任务会持续按住设定的秒数）…")
        threading.Thread(target=worker, daemon=True).start()

    def _start(self):
        if self.running:
            return
        hwnd = self._target_hwnd()
        if not hwnd or not is_window(hwnd):
            messagebox.showerror("无法开始", "请先在①中选择有效的目标窗口", parent=self)
            return
        if not self.tasks:
            messagebox.showerror("无法开始", "请先添加至少一个任务", parent=self)
            return
        try:
            opts = self._collect_run_opts()
        except ValueError as exc:
            messagebox.showerror("配置错误", str(exc), parent=self)
            return
        runtime_tasks = []
        for index, task in enumerate(self.tasks):
            if not task.get("enabled", True):
                self._set_task_status(index, "未启用")
                continue
            try:
                runtime = self._runtime_task(task)
            except ValueError as exc:
                messagebox.showerror("任务错误", "任务 %d: %s" % (index + 1, exc), parent=self)
                return
            runtime["ui_index"] = index
            runtime_tasks.append(runtime)
        if not runtime_tasks:
            messagebox.showerror("无法开始", "请至少勾选一个任务（表格“启用”列）", parent=self)
            return
        for index, task in enumerate(self.tasks):
            if task.get("enabled", True):
                self._set_task_status(index, "待命")
        if any(float(task.get("hold", 0) or 0) >= 2.0 for task in runtime_tasks):
            self.log("提示：长按任务会占用按键通道，期间其它任务会等待；"
                     "停止/暂停会立即中断长按并松开按键", "warn")
        self._save_config()
        self.session = RunSession(hwnd, runtime_tasks, opts, self.msg_queue)
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pause_btn.configure(state="normal", text="暂停")
        self.progress_bar.configure(value=0.0)
        self.progress_var.set("正在启动…")
        mode_cn = "并行计时" if opts["run_mode"] == "parallel" else "顺序循环"
        self.status_var.set("运行中…")
        profile_name = self.profiles[self.active_profile]["name"]
        self.log("开始运行（%s，%s）: 任务序列 = %s（%d 个任务），目标 = %s / %s" % (
            mode_cn,
            "后台消息" if opts["input_mode"] == "background" else "前台模拟",
            profile_name, len(runtime_tasks),
            self.window_combo.get(), self.child_combo.get()), "ok")
        if opts["input_mode"] == "foreground":
            if opts["keep_focus"]:
                self.log("前台模拟：运行期间目标窗口保持在前台，停止后恢复原窗口", "warn")
            self.log("若字母键无效：把系统输入法切到英文；测试请用方向键/Ctrl 等游戏内有效按键", "warn")
        else:
            self.log("后台消息模式对 DirectInput/原始输入游戏（如冒险岛类客户端）无效，"
                     "无反应请改用前台模拟", "warn")
            self.log("若后台模式反复发送失败，请尝试右键以管理员身份运行本工具", "warn")
        if opts["total_minutes"] > 0:
            self.log("将在 %g 分钟后自动停止" % opts["total_minutes"])
        if opts["press_gap"] > 0:
            self.log("不同任务的按键将按顺序执行，最小间隔 %g 秒" % opts["press_gap"])
        if opts["run_mode"] == "sequential":
            if opts["loop_count"] > 0:
                self.log("顺序模式：循环 %d 次（任务的次数/时长不生效）"
                         % opts["loop_count"])
            else:
                self.log("顺序模式：任务次数/时长不生效，按总时长或手动停止结束")
        elif opts["loop_count"] > 0:
            self.log("循环次数仅用于顺序循环模式，当前并行计时已忽略", "warn")
        self.session.start()

    def _stop(self):
        if self.session and self.running:
            self.log("正在停止…", "warn")
            self.session.stop()

    def _on_hotkey_stop(self):
        if self.session is not None:
            self.log("收到全局停止快捷键 Ctrl+Alt+Shift+Q，正在停止…", "warn")
            self.session.stop()
        else:
            self.log("当前没有运行中的任务（快捷键 Ctrl+Alt+Shift+Q）")

    def _on_session_end(self, reason):
        snapshot = self.session.snapshot() if self.session is not None else None
        self.running = False
        self.session = None
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled", text="暂停")
        stats = ""
        if snapshot is not None:
            stats = "共运行 %s 分钟，发送 %d 次" % (
                format_minutes_value(snapshot["elapsed"] / 60.0), snapshot["presses"])
        if reason == "stopped":
            self.status_var.set("已停止")
            self.log("运行已停止" + ("（%s）" % stats if stats else ""), "warn")
            self.progress_var.set("已停止" + (" ｜ " + stats if stats else ""))
        elif reason == "deadline":
            self.status_var.set("到达总运行时长，已结束")
            self.log("总运行时长已到，全部任务结束" + ("（%s）" % stats if stats else ""), "ok")
            self.progress_bar.configure(value=100.0)
            self.progress_var.set("已结束" + (" ｜ " + stats if stats else ""))
        else:
            self.status_var.set("全部任务已完成")
            self.log("全部任务已完成" + ("（%s）" % stats if stats else ""), "ok")
            self.progress_bar.configure(value=100.0)
            self.progress_var.set("已完成" + (" ｜ " + stats if stats else ""))

    def _config_path(self):
        return os.path.join(app_base_dir(), "assistant_config.json")

    def _save_config(self):
        self._store_current_settings()
        data = {
            "window": self.window_combo.get(),
            "child": self.child_combo.get(),
            "profiles": [
                {
                    "name": profile["name"],
                    "settings": dict(profile.get("settings", {})),
                    "tasks": [
                        {key: task[key] for key in
                         ("kind", "text", "button", "x", "y", "interval",
                          "mode", "value", "enabled", "hold", "seq_keys", "seq_gap")
                         if key in task}
                        for task in profile["tasks"]
                    ],
                }
                for profile in self.profiles
            ],
            "active_profile": self.active_profile,
            "settings": self._collect_settings(),
        }
        try:
            with open(self._config_path(), "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.log("保存配置失败: %s" % exc, "warn")

    def _sanitize_task(self, raw):
        try:
            candidate = dict(raw)
            candidate["interval"] = float(candidate["interval"])
            if candidate["interval"] <= 0:
                raise ValueError
            if candidate["kind"] == "seq":
                keys = [str(key).strip().lower() for key in candidate.get("seq_keys", [])
                        if str(key).strip()]
                if not keys:
                    raise ValueError
                for key in keys:
                    parse_combo(key)
                candidate["seq_keys"] = keys
                candidate["seq_gap"] = max(
                    0.0, float(candidate.get("seq_gap", 0.5) or 0))
                candidate["text"] = " → ".join(keys)
            elif candidate["kind"] == "key":
                candidate["text"] = str(candidate["text"]).strip().lower()
                parse_combo(candidate["text"])
            elif candidate["kind"] == "mouse":
                candidate["x"] = int(candidate["x"])
                candidate["y"] = int(candidate["y"])
                candidate["text"] = "%d,%d" % (candidate["x"], candidate["y"])
                if candidate.get("button") not in ("left", "right"):
                    candidate["button"] = "left"
            else:
                raise ValueError
            candidate["mode"] = "count" if candidate.get("mode") == "count" else "time"
            if candidate["mode"] == "count":
                candidate["value"] = max(1, int(candidate["value"]))
            else:
                candidate["value"] = max(0.1, float(candidate["value"]))
            candidate["enabled"] = bool(candidate.get("enabled", True))
            candidate["hold"] = max(0.0, float(candidate.get("hold", 0) or 0))
            candidate["status"] = "待机"
            return candidate
        except Exception:
            return None

    def _load_config(self):
        path = self._config_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            self.log("读取配置失败: %s" % exc, "warn")
            return
        settings = data.get("settings", {})
        self._apply_settings(settings)
        default_settings = self._collect_settings()

        profiles = []
        raw_profiles = data.get("profiles")
        if isinstance(raw_profiles, list) and raw_profiles:
            for raw in raw_profiles:
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name", "")).strip()[:15]
                if not name:
                    name = "任务序列%d" % (len(profiles) + 1)
                tasks = []
                for raw_task in raw.get("tasks", []):
                    task = self._sanitize_task(raw_task)
                    if task is not None:
                        tasks.append(task)
                merged_settings = dict(default_settings)
                if isinstance(raw.get("settings"), dict):
                    merged_settings.update(raw["settings"])
                profiles.append({
                    "name": name,
                    "tasks": tasks,
                    "settings": merged_settings,
                })
        elif isinstance(data.get("tasks"), list):
            tasks = []
            for raw_task in data.get("tasks", []):
                task = self._sanitize_task(raw_task)
                if task is not None:
                    tasks.append(task)
            profiles = self._default_profiles()
            profiles[0]["tasks"] = tasks
            for profile in profiles:
                profile["settings"] = dict(default_settings)
        if profiles:
            self.profiles = profiles
            try:
                self.active_profile = int(data.get("active_profile", 0))
            except Exception:
                self.active_profile = 0
            total = sum(len(profile["tasks"]) for profile in profiles)
            self.log("已恢复 %d 个任务序列，共 %d 个任务" % (len(profiles), total))
        window_value = data.get("window")
        if window_value:
            values = list(self.window_combo["values"])
            index = -1
            if window_value in values:
                index = values.index(window_value)
            else:
                base = window_value.split(" (0x")[0]
                for i, value in enumerate(values):
                    if value.split(" (0x")[0] == base:
                        index = i
                        break
            if index >= 0:
                self.window_combo.current(index)
                self._on_window_selected()
                child_value = data.get("child")
                child_values = list(self.child_combo["values"])
                if child_value in child_values:
                    self.child_combo.current(child_values.index(child_value))
                elif child_value and self.child_windows:
                    self.child_combo.current(0)
                self.log("已恢复上次的目标窗口")

    def _on_close(self):
        try:
            self.hotkey.stop()
        except Exception:
            pass
        if self.session and self.running:
            self.session.stop()
            time.sleep(0.05)
        self._save_config()
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
