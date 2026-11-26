"""Sisico 원격 - PC용 조작 프로그램 (윈도우 PC에서 다른 PC를 조작).

  sisico_remote_viewer.exe             # PC 목록 창
  sisico_remote_viewer.exe --selftest 주소 비밀번호   # 화면 없이 연결 시험 (자동 테스트용)

원격 화면 창 단축키 (Ctrl+Alt+Shift 를 누른 채로):
  H 도움말 · F 전체 화면 · M 다음 모니터 · G 키보드 잡기(Alt+Tab·Win 키 전달) 켜기/끄기
  1/2/3 화질(보통/좋음/최고) · Q 연결 끊기
파일을 창에 끌어다 놓으면 상대 PC의 '다운로드\\Sisico 원격' 폴더로 보냅니다.
클립보드(복사한 글)는 양쪽이 자동으로 맞춰집니다.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid

import win_input as wi
from remote_proto import DEFAULT_PORT, DISCOVER_MAGIC, DISCOVERY_PORT

QUALITY = {  # 이름: (긴 쪽 최대 해상도, fps, kbps)
    "1": ("보통", 1920, 30, 6000),
    "2": ("좋음", 0, 60, 12000),
    "3": ("최고", 0, 60, 25000),
}


# ---------------------------------------------------------------- 저장
def store_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "SisicoRemote")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "viewer.json")


def load_store():
    try:
        with open(store_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("hosts", [])
    data.setdefault("settings", {"quality": "2", "ralt_hangul": True, "rctrl_hanja": True})
    return data


def save_store(data):
    tmp = store_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, store_path())


# ---------------------------------------------------------------- SDL 스캔코드 → 윈도우 가상 키
def build_keymap():
    m = {}
    for i in range(26):
        m[4 + i] = 0x41 + i                      # A~Z
    for i in range(9):
        m[30 + i] = 0x31 + i                     # 1~9
    m[39] = 0x30                                 # 0
    m.update({40: 0x0D, 41: 0x1B, 42: 0x08, 43: 0x09, 44: 0x20, 45: 0xBD, 46: 0xBB, 47: 0xDB, 48: 0xDD,
              49: 0xDC, 50: 0xDC, 51: 0xBA, 52: 0xDE, 53: 0xC0, 54: 0xBC, 55: 0xBE, 56: 0xBF, 57: 0x14,
              70: 0x2C, 71: 0x91, 72: 0x13, 73: 0x2D, 74: 0x24, 75: 0x21, 76: 0x2E, 77: 0x23, 78: 0x22,
              79: 0x27, 80: 0x25, 81: 0x28, 82: 0x26, 83: 0x90, 84: 0x6F, 85: 0x6A, 86: 0x6D, 87: 0x6B,
              88: 0x0D, 98: 0x60, 99: 0x6E, 100: 0xE2, 101: 0x5D, 127: 0xAD, 128: 0xAF, 129: 0xAE,
              144: 0x15, 145: 0x19,               # LANG1 = 한/영, LANG2 = 한자
              224: 0xA2, 225: 0xA0, 226: 0xA4, 227: 0x5B, 228: 0xA3, 229: 0xA1, 230: 0xA5, 231: 0x5C})
    for i in range(12):
        m[58 + i] = 0x70 + i                     # F1~F12
    for i in range(12):
        m[104 + i] = 0x7C + i                    # F13~F24
    for i in range(9):
        m[89 + i] = 0x61 + i                     # 숫자패드 1~9
    return m


KEYMAP = build_keymap()
SC_LCTRL, SC_LSHIFT, SC_LALT, SC_RCTRL, SC_RSHIFT, SC_RALT = 224, 225, 226, 228, 229, 230


# ================================================================ 원격 화면 창 (pygame)
class ViewerWindow:
    def __init__(self, host, store):
        import pygame
        from viewer_net import Session
        self.pg = pygame
        self.host = host
        self.store = store
        self.settings = store["settings"]
        q = QUALITY.get(self.settings.get("quality", "2"), QUALITY["2"])
        self.session = Session(host, {"maxw": q[1], "fps": q[2], "kbps": q[3]})
        self.held = set()          # 상대 PC에 눌린 채로 보낸 키
        self.buttons = set()
        self.grab = True
        self.msg, self.msg_until = "", 0.0
        self.help = False
        self.last_clip_local = None
        self.last_clip_remote = None
        self.next_clip_check = 0.0
        self.pending_move = None
        self.last_move_sent = 0.0
        self.stream = None
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.fullscreen = False
        self.closed_reason = None
        self.pc_name = host.get("name") or host["address"]

    def notify(self, text, seconds=3.0):
        self.msg, self.msg_until = text, time.monotonic() + seconds

    def run(self):
        pg = self.pg
        os.environ.setdefault("SDL_GRAB_KEYBOARD", "1")  # 키보드 잡기: Alt+Tab, Win 키도 전달
        pg.display.init()
        pg.font.init()
        pg.key.set_repeat(400, 33)           # 키를 누르고 있으면 반복 입력
        pg.key.stop_text_input()             # 이 PC의 한글 입력기가 키를 가로채지 않게
        info = pg.display.Info()
        w, h = int(info.current_w * 0.8), int(info.current_h * 0.8)
        self.screen = pg.display.set_mode((w, h), pg.RESIZABLE)
        pg.display.set_caption(f"{self.pc_name} - 연결 중…")
        self.font = self._font(18)
        self.small = self._font(14)
        self.session.start()
        self._layout()
        self.set_grab(True)
        clock = pg.time.Clock()
        seq = 0
        stats_t, stats_frames, stats_bytes, shown = time.monotonic(), 0, 0, 0
        try:
            while True:
                for ev in pg.event.get():
                    if not self.handle(ev):
                        return self.closed_reason
                self.poll_session()
                if self.closed_reason:
                    self.draw_closed()
                    pg.display.flip()
                    clock.tick(30)
                    continue
                self.flush_move()
                self.sync_clipboard()
                frame, seq2 = self.session.take_frame(seq)
                if frame:
                    seq = seq2
                    shown += 1
                    data, fw, fh = frame
                    surf = pg.image.frombuffer(data, (fw, fh), "RGB")
                    self.screen.fill((0, 0, 0))
                    if (fw, fh) != self.rect.size:   # 창 크기가 막 바뀐 경우
                        surf = pg.transform.scale(surf, self.rect.size)
                    self.screen.blit(surf, self.rect.topleft)
                    self.draw_overlay()
                    pg.display.flip()
                elif self.msg_until > time.monotonic() or self.help:
                    self.draw_overlay()
                    pg.display.flip()
                now = time.monotonic()
                if now - stats_t >= 1:
                    fps = shown - stats_frames
                    kbps = (self.session.bytes_in - stats_bytes) * 8 // 1000 // max(1, int(now - stats_t))
                    stats_t, stats_frames, stats_bytes = now, shown, self.session.bytes_in
                    s = self.stream
                    res = f"{s['w']}×{s['h']}" if s else ""
                    grab = "" if self.grab else " · 키보드 잡기 꺼짐"
                    pg.display.set_caption(f"{self.pc_name} · {res} {fps}fps {kbps}kbps{grab}  (Ctrl+Alt+Shift+H 도움말)")
                clock.tick(240)
        finally:
            self.release_all()
            self.session.close()
            pg.quit()

    def _font(self, size):
        pg = self.pg
        for name in ("malgungothic", "malgun gothic", "applesdgothicneo", "notosanscjkkr", "nanumgothic"):
            path = pg.font.match_font(name)
            if path:
                return pg.font.Font(path, size)
        return pg.font.Font(None, size + 6)

    # ------------------------------------------------------------ 배치
    def _layout(self):
        sw, sh = self.screen.get_size()
        s = self.stream
        if not s:
            self.rect = self.pg.Rect(0, 0, sw, sh)
        else:
            scale = min(sw / s["w"], sh / s["h"])
            w, h = max(2, int(s["w"] * scale)) // 2 * 2, max(2, int(s["h"] * scale)) // 2 * 2
            self.rect = self.pg.Rect((sw - w) // 2, (sh - h) // 2, w, h)
        self.session.target = self.rect.size
        self.screen.fill((0, 0, 0))

    def toggle_fullscreen(self):
        pg = self.pg
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = self.screen.get_size()
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        else:
            self.screen = pg.display.set_mode(getattr(self, "windowed_size", (1280, 720)), pg.RESIZABLE)
        self._layout()
        self.session.send({"t": "kf"})

    def set_grab(self, on):
        self.grab = on
        try:
            self.pg.event.set_keyboard_grab(on)
        except Exception:
            pass

    # ------------------------------------------------------------ 세션 알림
    def poll_session(self):
        import queue
        while True:
            try:
                kind, val = self.session.events.get_nowait()
            except queue.Empty:
                return
            if kind == "authed":
                self.pc_name = val or self.pc_name
                self.notify(f"{self.pc_name} 에 연결됨 · Ctrl+Alt+Shift+H 도움말", 4)
            elif kind == "stream":
                self.stream = val
                self._layout()
            elif kind == "clip":
                self.last_clip_remote = val
                self.last_clip_local = val
                try:
                    wi.clipboard_set(val)
                except Exception:
                    pass
            elif kind == "progress":
                name, sent, size = val
                pct = f"{sent * 100 // size}%" if size else f"{sent // 1024} KB"
                self.notify(f"보내는 중: {name}  {pct}", 2)
            elif kind == "fput_ok":
                self.notify(f"보냈습니다 → {val}", 4)
            elif kind == "fput_err":
                self.notify(f"보내지 못했습니다: {val}", 5)
            elif kind == "closed":
                self.closed_reason = val
                self.release_all(send=False)
                self.set_grab(False)

    def sync_clipboard(self):
        now = time.monotonic()
        if now < self.next_clip_check or not self.pg.key.get_focused():
            return
        self.next_clip_check = now + 0.8
        try:
            cur = wi.clipboard_get()
        except Exception:
            return
        if self.last_clip_local is None:
            self.last_clip_local = cur
            return
        if cur and cur != self.last_clip_local and cur != self.last_clip_remote:
            self.last_clip_local = cur
            self.session.send({"t": "clip_set", "s": cur})

    # ------------------------------------------------------------ 입력
    def to_norm(self, pos):
        x, y = pos
        r = self.rect
        if r.w == 0:
            return None
        return (min(max((x - r.x) / r.w, 0.0), 1.0), min(max((y - r.y) / r.h, 0.0), 1.0))

    def flush_move(self, force=False):
        if self.pending_move and (force or time.monotonic() - self.last_move_sent > 0.008):
            nx, ny = self.pending_move
            self.session.send({"t": "mm", "x": round(nx, 5), "y": round(ny, 5)})
            self.pending_move = None
            self.last_move_sent = time.monotonic()

    def vk_for(self, sc):
        if sc == SC_RALT and self.settings.get("ralt_hangul", True):
            return 0x15
        if sc == SC_RCTRL and self.settings.get("rctrl_hanja", True):
            return 0x19
        return KEYMAP.get(sc)

    def release_all(self, send=True):
        if send:
            for vk in list(self.held):
                self.session.send({"t": "key", "vk": vk, "d": False})
            for b in list(self.buttons):
                self.session.send({"t": "mb", "b": b, "d": False})
        self.held.clear()
        self.buttons.clear()

    def hotkey(self, ev):
        pg = self.pg
        mods = pg.key.get_mods()
        if not (mods & pg.KMOD_CTRL and mods & pg.KMOD_ALT and mods & pg.KMOD_SHIFT):
            return False
        k = ev.key
        if k == pg.K_q:
            self.closed_reason = "끊음"
            return "quit"
        if k == pg.K_h:
            self.help = not self.help
        elif k == pg.K_f:
            self.toggle_fullscreen()
        elif k == pg.K_g:
            self.set_grab(not self.grab)
            self.notify("키보드 잡기 " + ("켜짐: Alt+Tab·Win 키도 상대 PC로" if self.grab else "꺼짐: Alt+Tab 은 이 PC에서"))
        elif k == pg.K_m:
            n = max(1, len(self.session.monitors))
            self.session.mon = (self.session.mon + 1) % n
            self.session.start_message("cfg")
            self.notify(f"모니터 {self.session.mon + 1} / {n}")
        elif ev.unicode in QUALITY or k in (pg.K_1, pg.K_2, pg.K_3):
            key = {pg.K_1: "1", pg.K_2: "2", pg.K_3: "3"}.get(k, ev.unicode)
            name, maxw, fps, kbps = QUALITY[key]
            self.settings["quality"] = key
            save_store(self.store)
            self.session.settings.update(maxw=maxw, fps=fps, kbps=kbps)
            self.session.start_message("cfg")
            self.notify(f"화질: {name}")
        else:
            return False
        return True

    def handle(self, ev):
        pg = self.pg
        t = ev.type
        if t == pg.QUIT:
            return False
        if self.closed_reason:
            if t in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                return False
            return True
        if t in (pg.VIDEORESIZE, pg.WINDOWSIZECHANGED):
            if not self.fullscreen and t == pg.VIDEORESIZE:
                self.screen = pg.display.set_mode((max(320, ev.w), max(200, ev.h)), pg.RESIZABLE)
            self._layout()
            self.session.send({"t": "kf"})
        elif t == pg.WINDOWFOCUSLOST:
            self.release_all()                    # 다른 창으로 가면 눌린 키를 모두 뗌
        elif t == pg.MOUSEMOTION:
            n = self.to_norm(ev.pos)
            if n and (self.rect.collidepoint(ev.pos) or self.buttons):
                self.pending_move = n
        elif t in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            name = {1: "left", 2: "middle", 3: "right"}.get(ev.button)
            if name:
                n = self.to_norm(ev.pos)
                if n:
                    self.pending_move = n
                    self.flush_move(force=True)   # 클릭은 정확한 위치에서
                down = t == pg.MOUSEBUTTONDOWN
                (self.buttons.add if down else self.buttons.discard)(name)
                self.session.send({"t": "mb", "b": name, "d": down})
        elif t == pg.MOUSEWHEEL:
            dy = getattr(ev, "precise_y", ev.y)
            dx = getattr(ev, "precise_x", ev.x)
            self.session.send({"t": "wh", "dy": int(dy * 120), "dx": int(dx * 120)})
        elif t == pg.KEYDOWN:
            r = self.hotkey(ev)
            if r == "quit":
                return False
            if r:
                return True
            vk = self.vk_for(ev.scancode)
            if vk:
                self.held.add(vk)
                self.session.send({"t": "key", "vk": vk, "d": True})
        elif t == pg.KEYUP:
            vk = self.vk_for(ev.scancode)
            if vk and vk in self.held:
                self.held.discard(vk)
                self.session.send({"t": "key", "vk": vk, "d": False})
        elif t == pg.DROPFILE:
            path = ev.file
            if os.path.isfile(path):
                self.notify(f"보내는 중: {os.path.basename(path)}", 2)
                self.session.send_file(path)
            else:
                self.notify("폴더는 보낼 수 없습니다. 압축해서 보내 주세요.", 4)
        return True

    # ------------------------------------------------------------ 그리기
    def text_box(self, lines, center=True):
        pg = self.pg
        surfs = [self.font.render(l, True, (255, 255, 255)) for l in lines]
        w = max(s.get_width() for s in surfs) + 32
        h = sum(s.get_height() + 6 for s in surfs) + 24
        sw, sh = self.screen.get_size()
        box = pg.Surface((w, h), pg.SRCALPHA)
        box.fill((0, 0, 0, 190))
        y = 12
        for s in surfs:
            box.blit(s, (16, y))
            y += s.get_height() + 6
        pos = ((sw - w) // 2, (sh - h) // 2) if center else ((sw - w) // 2, sh - h - 24)
        self.screen.blit(box, pos)

    def draw_overlay(self):
        if self.help:
            self.text_box([
                "Ctrl + Alt + Shift 를 누른 채로:",
                "  H  도움말 닫기          F  전체 화면",
                "  M  다음 모니터          G  키보드 잡기 켜기/끄기",
                "  1 / 2 / 3  화질 보통 / 좋음 / 최고",
                "  Q  연결 끊기",
                "",
                "파일을 이 창에 끌어다 놓으면 상대 PC로 보냅니다",
                "(상대 PC의 다운로드\\Sisico 원격 폴더).",
                "복사한 글은 양쪽 PC가 자동으로 맞춰집니다.",
                "오른쪽 Alt = 한/영, 오른쪽 Ctrl = 한자",
            ])
        elif self.msg and time.monotonic() < self.msg_until:
            self.text_box([self.msg], center=False)

    def draw_closed(self):
        self.screen.fill((20, 24, 28))
        lines = (self.closed_reason or "").split("\n") + ["", "아무 키나 누르면 닫힙니다"]
        self.text_box(lines)


# ================================================================ PC 목록 창 (tkinter)
class Launcher:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.store = load_store()
        self.root = tk.Tk()
        self.root.title("Sisico 원격 - PC 조작")
        self.root.geometry("460x420")
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="조작할 PC", font=("Malgun Gothic", 13, "bold")).pack(anchor="w")
        self.lb = tk.Listbox(frm, font=("Malgun Gothic", 11), activestyle="none", height=10)
        self.lb.pack(fill="both", expand=True, pady=8)
        self.lb.bind("<Double-Button-1>", lambda e: self.connect())
        self.lb.bind("<Return>", lambda e: self.connect())
        row = ttk.Frame(frm)
        row.pack(fill="x")
        for label, cmd in (("연결", self.connect), ("추가", lambda: self.edit(None)), ("수정", self.edit_selected),
                           ("삭제", self.delete), ("와이파이에서 찾기", self.discover)):
            ttk.Button(row, text=label, command=cmd).pack(side="left", padx=2)
        opt = ttk.Frame(frm)
        opt.pack(fill="x", pady=(10, 0))
        ttk.Label(opt, text="화질").pack(side="left")
        self.quality = tk.StringVar(value=QUALITY[self.store["settings"].get("quality", "2")][0])
        cb = ttk.Combobox(opt, textvariable=self.quality, values=[v[0] for v in QUALITY.values()],
                          state="readonly", width=8)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_quality())
        self.ralt = tk.BooleanVar(value=self.store["settings"].get("ralt_hangul", True))
        ttk.Checkbutton(opt, text="오른쪽 Alt = 한/영", variable=self.ralt, command=self.save_opts).pack(side="left", padx=8)
        ttk.Label(frm, text="두 번 누르면 연결 · 원격 화면에서 Ctrl+Alt+Shift+H 도움말",
                  foreground="#777").pack(anchor="w", pady=(8, 0))
        self.refresh()

    def save_quality(self):
        for k, v in QUALITY.items():
            if v[0] == self.quality.get():
                self.store["settings"]["quality"] = k
        save_store(self.store)

    def save_opts(self):
        self.store["settings"]["ralt_hangul"] = bool(self.ralt.get())
        save_store(self.store)

    def refresh(self):
        self.lb.delete(0, "end")
        for h in self.store["hosts"]:
            self.lb.insert("end", f"  🖥  {h.get('name') or h['address']}    ({h['address']}:{h['port']})")

    def selected(self):
        sel = self.lb.curselection()
        return self.store["hosts"][sel[0]] if sel else None

    def connect(self):
        h = self.selected()
        if not h:
            return
        self.store = load_store()   # 다른 창에서 바뀐 설정 반영
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--connect", h["id"]]
        else:
            cmd = [sys.executable, os.path.abspath(__file__), "--connect", h["id"]]
        subprocess.Popen(cmd)

    def edit_selected(self):
        h = self.selected()
        if h:
            self.edit(h)

    def delete(self):
        from tkinter import messagebox
        h = self.selected()
        if h and messagebox.askyesno("삭제", f"{h.get('name') or h['address']} 을(를) 목록에서 지울까요?"):
            self.store["hosts"] = [x for x in self.store["hosts"] if x["id"] != h["id"]]
            save_store(self.store)
            self.refresh()

    def edit(self, old, preset=None):
        tk = self.tk
        from tkinter import messagebox, ttk
        from viewer_net import PairError, pair
        win = tk.Toplevel(self.root)
        win.title("PC 추가" if old is None else "PC 수정")
        win.transient(self.root)
        win.grab_set()
        f = ttk.Frame(win, padding=14)
        f.pack()
        p = preset or {}
        fields = {}
        for i, (key, label, val, show) in enumerate((
                ("name", "이름", (old or p).get("name", ""), None),
                ("address", "주소", (old or p).get("address", ""), None),
                ("port", "포트", str((old or p).get("port", DEFAULT_PORT)), None),
                ("password", "비밀번호" + (" (바꿀 때만)" if old else ""), "", "●"))):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=3)
            e = ttk.Entry(f, width=30, show=show or "")
            e.insert(0, val)
            e.grid(row=i, column=1, pady=3)
            fields[key] = e

        def save():
            name = fields["name"].get().strip()
            addr = fields["address"].get().strip()
            pw = fields["password"].get()
            try:
                port = int(fields["port"].get() or DEFAULT_PORT)
            except ValueError:
                messagebox.showerror("포트", "포트는 숫자여야 합니다", parent=win)
                return
            if not addr:
                messagebox.showerror("주소", "주소를 입력하세요", parent=win)
                return
            entry = dict(old or {}, id=(old or {}).get("id") or uuid.uuid4().hex, name=name, address=addr, port=port)
            if not pw:
                if not old:
                    messagebox.showerror("비밀번호", "PC에서 정한 비밀번호를 입력하세요", parent=win)
                    return
            else:
                def confirm(fp, pc_name):
                    if old and old.get("pin") and fp == short(old["pin"]):
                        return True
                    return messagebox.askyesno(
                        "이 PC가 맞나요?",
                        f"PC 이름: {pc_name}\n\n상대 PC의 Sisico 원격 창에 나온 지문과 같은지 확인하세요.\n\n"
                        f"        {fp}\n\n다르면 '아니요'를 누르세요 (다른 기기가 PC인 척하는 것일 수 있습니다).",
                        parent=win)
                win.config(cursor="watch")
                win.update()
                try:
                    info = pair(addr, port, pw, confirm)
                except PairError as e:
                    win.config(cursor="")
                    messagebox.showerror("등록하지 못했습니다", str(e), parent=win)
                    return
                entry.update(key=info["key"], pin=info["pin"], name=name or info["name"])
            hosts = self.store["hosts"]
            idx = next((i for i, x in enumerate(hosts) if x["id"] == entry["id"]), None)
            if idx is None:
                hosts.append(entry)
            else:
                hosts[idx] = entry
            save_store(self.store)
            self.refresh()
            win.destroy()

        ttk.Button(f, text="저장", command=save).grid(row=4, column=1, sticky="e", pady=(10, 0))
        fields["password"].bind("<Return>", lambda e: save())

    def discover(self):
        from tkinter import messagebox
        found = {}
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.3)
        end = time.time() + 1.8
        try:
            while time.time() < end:
                s.sendto(DISCOVER_MAGIC, ("255.255.255.255", DISCOVERY_PORT))
                t1 = time.time() + 0.6
                while time.time() < t1:
                    try:
                        data, addr = s.recvfrom(1024)
                        o = json.loads(data)
                        found[addr[0]] = {"name": o.get("name", ""), "address": addr[0], "port": o.get("port", DEFAULT_PORT)}
                    except socket.timeout:
                        pass
                    except (OSError, ValueError):
                        pass
        finally:
            s.close()
        mine = set()
        try:
            mine = {i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
        except OSError:
            pass
        items = [v for k, v in found.items() if k not in mine]
        if not items:
            messagebox.showinfo("찾지 못했습니다",
                                "상대 PC에서 sisico_remote_host.exe 가 실행 중인지, 같은 네트워크인지,\n"
                                "방화벽에서 '개인 네트워크' 허용을 눌렀는지 확인하세요.\n\n'추가'로 주소를 직접 넣어도 됩니다.")
            return
        if len(items) == 1:
            self.edit(None, items[0])
            return
        top = self.tk.Toplevel(self.root)
        top.title("찾은 PC")
        lb = self.tk.Listbox(top, font=("Malgun Gothic", 11), width=40)
        for it in items:
            lb.insert("end", f"{it['name']}  ({it['address']})")
        lb.pack(padx=10, pady=10)
        lb.bind("<Double-Button-1>", lambda e: (top.destroy(), self.edit(None, items[lb.curselection()[0]])))

    def run(self):
        self.root.mainloop()


def short(pin):
    from remote_proto import short_fp
    return short_fp(pin)


def main():
    ap = argparse.ArgumentParser(description="Sisico 원격 - PC용 조작 프로그램")
    ap.add_argument("--connect", help="저장된 PC id 로 바로 연결")
    ap.add_argument("--selftest", nargs=2, metavar=("주소", "비밀번호"))
    args = ap.parse_args()
    if sys.platform == "win32":
        wi.set_dpi_aware()
    if args.selftest:
        from viewer_net import selftest
        sys.exit(selftest(*args.selftest))
    if args.connect:
        store = load_store()
        host = next((h for h in store["hosts"] if h["id"] == args.connect), None)
        if host:
            ViewerWindow(host, store).run()
        return
    Launcher().run()


if __name__ == "__main__":
    if sys.stdout is None:          # 콘솔 없는 exe
        sys.stdout = sys.stderr = open(os.devnull, "w")
    elif sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
