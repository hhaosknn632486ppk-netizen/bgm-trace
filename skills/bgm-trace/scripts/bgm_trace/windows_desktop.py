"""Native Windows backend; no clipboard, app IPC, credentials or draft reads."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
from pathlib import PureWindowsPath
import struct
import time
import zlib

from .media import TraceError


class LastInput(C.Structure):
    _fields_ = [("size", W.UINT), ("time", W.DWORD)]


class MouseInput(C.Structure):
    _fields_ = [("x", W.LONG), ("y", W.LONG), ("data", W.DWORD), ("flags", W.DWORD), ("time", W.DWORD), ("extra", C.c_size_t)]


class KeyInput(C.Structure):
    _fields_ = [("key", W.WORD), ("scan", W.WORD), ("flags", W.DWORD), ("time", W.DWORD), ("extra", C.c_size_t)]


class InputUnion(C.Union):
    _fields_ = [("mouse", MouseInput), ("keyboard", KeyInput)]


class Input(C.Structure):
    _fields_ = [("type", W.DWORD), ("data", InputUnion)]


class BitmapInfo(C.Structure):
    _fields_ = [("size", W.DWORD), ("width", W.LONG), ("height", W.LONG), ("planes", W.WORD), ("bits", W.WORD),
                ("compression", W.DWORD), ("image_size", W.DWORD), ("x", W.LONG), ("y", W.LONG), ("colors", W.DWORD), ("important", W.DWORD)]


def _png(width: int, height: int, bgra: bytes) -> bytes:
    # DIB rows are top-down, 32-bit BGRA. Encode RGB, excluding undefined alpha.
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
    rows = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


class WindowsDesktop:
    def __init__(self):
        self.user = C.WinDLL("user32", use_last_error=True)
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.gdi = C.WinDLL("gdi32", use_last_error=True)
        self.version = C.WinDLL("version", use_last_error=True)
        self.callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        signatures = [
            (self.user, "EnumWindows", W.BOOL, [self.callback_type, W.LPARAM]),
            (self.user, "IsWindowVisible", W.BOOL, [W.HWND]),
            (self.user, "IsIconic", W.BOOL, [W.HWND]),
            (self.user, "ShowWindow", W.BOOL, [W.HWND, C.c_int]),
            (self.user, "GetWindowThreadProcessId", W.DWORD, [W.HWND, C.POINTER(W.DWORD)]),
            (self.user, "GetWindowRect", W.BOOL, [W.HWND, C.POINTER(W.RECT)]),
            (self.user, "GetForegroundWindow", W.HWND, []),
            (self.user, "SetForegroundWindow", W.BOOL, [W.HWND]),
            (self.user, "GetLastInputInfo", W.BOOL, [C.POINTER(LastInput)]),
            (self.user, "SetThreadDpiAwarenessContext", W.HANDLE, [W.HANDLE]),
            (self.user, "WindowFromPoint", W.HWND, [W.POINT]),
            (self.user, "SetCursorPos", W.BOOL, [C.c_int, C.c_int]),
            (self.user, "SendInput", W.UINT, [W.UINT, C.POINTER(Input), C.c_int]),
            (self.user, "GetDC", W.HDC, [W.HWND]),
            (self.user, "ReleaseDC", C.c_int, [W.HWND, W.HDC]),
            (self.kernel, "OpenProcess", W.HANDLE, [W.DWORD, W.BOOL, W.DWORD]),
            (self.kernel, "CloseHandle", W.BOOL, [W.HANDLE]),
            (self.kernel, "QueryFullProcessImageNameW", W.BOOL, [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]),
            (self.kernel, "GetProcessTimes", W.BOOL, [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4),
            (self.gdi, "CreateCompatibleDC", W.HDC, [W.HDC]),
            (self.gdi, "CreateDIBSection", W.HBITMAP, [W.HDC, C.POINTER(BitmapInfo), W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD]),
            (self.gdi, "SelectObject", W.HANDLE, [W.HDC, W.HANDLE]),
            (self.gdi, "BitBlt", W.BOOL, [W.HDC, C.c_int, C.c_int, C.c_int, C.c_int, W.HDC, C.c_int, C.c_int, W.DWORD]),
            (self.gdi, "DeleteObject", W.BOOL, [W.HANDLE]),
            (self.gdi, "DeleteDC", W.BOOL, [W.HDC]),
            (self.version, "GetFileVersionInfoSizeW", W.DWORD, [W.LPCWSTR, C.POINTER(W.DWORD)]),
            (self.version, "GetFileVersionInfoW", W.BOOL, [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p]),
            (self.version, "VerQueryValueW", W.BOOL, [C.c_void_p, W.LPCWSTR, C.POINTER(C.c_void_p), C.POINTER(W.UINT)]),
        ]
        for library, name, result, arguments in signatures:
            method = getattr(library, name)
            method.restype, method.argtypes = result, arguments
        if not self.user.SetThreadDpiAwarenessContext(C.c_void_p(-4)):
            raise TraceError("Cannot use physical window coordinates on this Windows version.")

    def owner(self, handle):
        process = W.DWORD()
        self.user.GetWindowThreadProcessId(handle, C.byref(process))
        return process.value

    def bounds(self, handle):
        rectangle = W.RECT()
        if not self.user.GetWindowRect(handle, C.byref(rectangle)):
            raise TraceError("Observed window is unavailable.")
        return [rectangle.left, rectangle.top, rectangle.right - rectangle.left, rectangle.bottom - rectangle.top]

    def process(self, pid):
        handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            buffer, size = C.create_unicode_buffer(32768), W.DWORD(32768)
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(size)):
                return None
            if PureWindowsPath(buffer.value).name.lower() != "jianyingpro.exe":
                return None
            times = [W.FILETIME() for _ in range(4)]
            if not self.kernel.GetProcessTimes(handle, *(C.byref(t) for t in times)):
                return None
            started = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return {"started": started, "path": buffer.value}
        finally:
            self.kernel.CloseHandle(handle)

    def app_version(self, path):
        size = self.version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        data, value, length = C.create_string_buffer(size), C.c_void_p(), W.UINT()
        if not self.version.GetFileVersionInfoW(path, 0, size, data) or not self.version.VerQueryValueW(data, "\\", C.byref(value), C.byref(length)) or length.value < 16:
            return None
        info = C.cast(value, C.POINTER(W.DWORD))
        return ".".join(str(n) for n in (info[2] >> 16, info[2] & 65535, info[3] >> 16, info[3] & 65535))

    def windows(self):
        windows, processes = {}, {}
        def visit(handle, unused):
            if not self.user.IsWindowVisible(handle):
                return True
            pid = self.owner(handle)
            if pid not in processes:
                processes[pid] = self.process(pid)
            info = processes[pid]
            if info:
                bounds = self.bounds(handle)
                area = bounds[2] * bounds[3]
                if area > windows.get(pid, {}).get("area", 0):
                    windows[pid] = {"process_id": pid, "window_handle": int(handle), "bounds": bounds, "area": area,
                                    "version": self.app_version(info["path"])}
            return True
        if not self.user.EnumWindows(self.callback_type(visit), 0):
            raise TraceError("Cannot enumerate desktop windows.")
        return [{k: v for k, v in row.items() if k != "area"} for row in windows.values()]

    def last_input(self):
        record = LastInput(C.sizeof(LastInput), 0)
        if not self.user.GetLastInputInfo(C.byref(record)):
            raise TraceError("Cannot observe input activity.")
        return record.time

    def capture(self, pid):
        windows = [row for row in self.windows() if pid is None or row["process_id"] == pid]
        if len(windows) != 1:
            raise TraceError("Select one visible Jianying process with --pid; open it normally if none is visible.")
        window = windows[0]
        handle, pid = window["window_handle"], window["process_id"]
        if self.user.IsIconic(handle):
            self.user.ShowWindow(handle, 9)
        if self.owner(self.user.GetForegroundWindow()) != pid:
            self.user.SetForegroundWindow(handle)
            time.sleep(.2)
        active = self.user.GetForegroundWindow()
        if self.owner(active) != pid:
            raise TraceError("Jianying is not foreground; activate its task window and capture again.")
        bounds = self.bounds(handle)
        if not 200 <= bounds[2] <= 8192 or not 100 <= bounds[3] <= 8192:
            raise TraceError("Unsupported window bounds.")
        info = self.process(pid)
        if info is None:
            raise TraceError("Jianying process changed.")
        observed_input = self.last_input()
        png = self.screenshot(bounds)
        if self.user.GetForegroundWindow() != active or self.last_input() != observed_input or self.bounds(handle) != bounds:
            raise TraceError("Window/input changed during capture; observe again.")
        return {"process_id": pid, "process_started": info["started"], "window_handle": handle,
                "active_handle": int(active), "bounds": bounds, "last_input": observed_input,
                "captured_at": datetime.now(timezone.utc).isoformat()}, png

    def screenshot(self, bounds):
        left, top, width, height = bounds
        screen = self.user.GetDC(None)
        memory = self.gdi.CreateCompatibleDC(screen)
        bits = C.c_void_p()
        info = BitmapInfo(C.sizeof(BitmapInfo), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        bitmap = self.gdi.CreateDIBSection(screen, C.byref(info), 0, C.byref(bits), None, 0)
        previous = None
        try:
            if not screen or not memory or not bitmap or not bits:
                raise TraceError("Cannot allocate a window capture.")
            previous = self.gdi.SelectObject(memory, bitmap)
            if not self.gdi.BitBlt(memory, 0, 0, width, height, screen, left, top, 0x40CC0020):
                raise TraceError("Window capture failed.")
            return _png(width, height, C.string_at(bits, width * height * 4))
        finally:
            if previous:
                self.gdi.SelectObject(memory, previous)
            if bitmap:
                self.gdi.DeleteObject(bitmap)
            if memory:
                self.gdi.DeleteDC(memory)
            if screen:
                self.user.ReleaseDC(None, screen)

    def validate(self, frame):
        info = self.process(frame["process_id"])
        if info is None or info["started"] != frame["process_started"] or self.owner(frame["window_handle"]) != frame["process_id"]:
            raise TraceError("Observed app/window changed; capture again.")
        if self.bounds(frame["window_handle"]) != frame["bounds"]:
            raise TraceError("Window moved or resized; capture again.")
        active = self.user.GetForegroundWindow()
        if active != frame["active_handle"] or self.owner(active) != frame["process_id"]:
            raise TraceError("Active window changed; capture again.")
        if self.last_input() != frame["last_input"]:
            raise TraceError("Input activity occurred since capture; observe again before acting.")

    def send(self, item):
        if self.user.SendInput(1, C.byref(item), C.sizeof(Input)) != 1:
            raise TraceError("Windows input was rejected; observe the app before retrying.")

    def key(self, code, flags=0, scan=0):
        self.send(Input(1, InputUnion(keyboard=KeyInput(code, scan, flags, 0, 0))))

    def select_all(self):
        self.key(0x11)
        try:
            self.key(0x41)
            self.key(0x41, 2)
        finally:
            self.key(0x11, 2)

    def act(self, args, frame):
        if args.action == "click":
            x, y = args.x, args.y
            left, top, width, height = frame["bounds"]
            if x is None or y is None or not 0 <= x < width or not 0 <= y < height:
                raise TraceError("Click is outside the observed window.")
            if self.owner(self.user.WindowFromPoint(W.POINT(left + x, top + y))) != frame["process_id"]:
                raise TraceError("Another application covers the target point.")
            if not self.user.SetCursorPos(left + x, top + y):
                raise TraceError("Cannot position pointer.")
            self.send(Input(0, InputUnion(mouse=MouseInput(0, 0, 0, 2, 0, 0))))
            self.send(Input(0, InputUnion(mouse=MouseInput(0, 0, 0, 4, 0, 0))))
        elif args.action == "type":
            if args.select_all:
                self.select_all()
            for (code,) in struct.iter_unpack("<H", args.text.encode("utf-16-le")):
                self.key(0, 4, code)
                self.key(0, 6, code)
            if args.submit:
                self.key(13)
                self.key(13, 2)
        elif args.key == "SelectAll":
            self.select_all()
        else:
            code = 27 if args.key == "Escape" else 13
            self.key(code)
            self.key(code, 2)
