"""호스트를 검은 창 없이 작업 표시줄 알림 영역(트레이) 아이콘으로 실행.

- 처음 실행: 비밀번호 설정 창 (일반 윈도우 창)
- 아이콘 오른쪽 클릭: 연결 정보 보기 · 비밀번호 바꾸기 · Windows 시작 시 자동 실행 · 로그 폴더 · 종료
- 누가 접속하면 윈도우 알림
"""
import asyncio
import os
import subprocess
import sys
import threading

APP_NAME = "Sisico 원격"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "SisicoRemoteHost"


# ---------------------------------------------------------------- 윈도우 도우미
def message_box(text, title=APP_NAME, error=False):
    if sys.platform == "win32":
        import ctypes
        flags = 0x10 if error else 0x40          # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x10000)  # MB_SETFOREGROUND
    else:
        print(f"[{title}] {text}")


def ask_yes_no(text, title=APP_NAME):
    if sys.platform != "win32":
        return False
    import ctypes
    return ctypes.windll.user32.MessageBoxW(None, text, title, 0x4 | 0x20 | 0x10000) == 6   # MB_YESNO, 예=6


_mutex = None


def already_running(wait=3.0):
    """같은 PC에서 트레이가 두 번 뜨지 않게 (이름 있는 뮤텍스). 방금 재시작한 경우를 위해 잠깐 기다려 봄."""
    global _mutex
    if sys.platform != "win32":
        return False
    import ctypes
    import time
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    end = time.time() + wait
    while True:
        h = k32.CreateMutexW(None, False, "Local\\SisicoRemoteHost")
        if k32.GetLastError() != 183:            # ERROR_ALREADY_EXISTS 가 아니면 우리가 첫 번째
            _mutex = h
            return False
        k32.CloseHandle(ctypes.c_void_p(h))
        if time.time() >= end:
            return True
        time.sleep(0.2)


def restart_tray():
    """트레이를 새로 띄우고 지금 것은 끝냄 (서비스 모드를 켜고 끈 뒤)."""
    subprocess.Popen(self_command())
    os._exit(0)


def self_command(*extra):
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra]
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(w):
        exe = w
    return [exe, os.path.abspath(sys.argv[0]), *extra]


def autostart_enabled():
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_VALUE)
            return True
    except OSError:
        return False


def set_autostart(on):
    if sys.platform != "win32":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            cmd = " ".join(f'"{p}"' for p in self_command())
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, RUN_VALUE)
            except OSError:
                pass


# ---------------------------------------------------------------- 비밀번호 설정 창
def setup_dialog(set_password, cfg, first=True):
    """비밀번호 설정 창. 저장하면 True."""
    import tkinter as tk
    from tkinter import messagebox, ttk
    result = {"ok": False}
    root = tk.Tk()
    root.title(f"{APP_NAME} - " + ("처음 설정" if first else "비밀번호 바꾸기"))
    root.resizable(False, False)
    f = ttk.Frame(root, padding=18)
    f.pack()
    intro = ("이 PC를 휴대폰이나 다른 PC에서 조작할 때 쓸 접속 비밀번호를 정하세요.\n"
             "8자 이상, 길수록 안전합니다." if first else
             "새 비밀번호를 정하세요. 바꾸면 휴대폰·다른 PC에서 이 PC를 다시 등록해야 합니다.")
    ttk.Label(f, text=intro, justify="left").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
    ttk.Label(f, text="비밀번호").grid(row=1, column=0, sticky="w", pady=3)
    pw1 = ttk.Entry(f, show="●", width=28)
    pw1.grid(row=1, column=1, pady=3)
    ttk.Label(f, text="한 번 더").grid(row=2, column=0, sticky="w", pady=3)
    pw2 = ttk.Entry(f, show="●", width=28)
    pw2.grid(row=2, column=1, pady=3)
    auto = tk.BooleanVar(value=True if first else autostart_enabled())
    if sys.platform == "win32":
        ttk.Checkbutton(f, text="Windows 시작 시 자동 실행", variable=auto).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def save(*_):
        a, b = pw1.get(), pw2.get()
        if len(a) < 8:
            messagebox.showerror(APP_NAME, "비밀번호는 8자 이상이어야 합니다.", parent=root)
            return
        if a != b:
            messagebox.showerror(APP_NAME, "두 번 입력한 비밀번호가 다릅니다.", parent=root)
            return
        set_password(cfg, a)
        try:
            set_autostart(bool(auto.get()))
        except OSError:
            pass
        result["ok"] = True
        root.destroy()

    ttk.Button(f, text="저장", command=save).grid(row=4, column=1, sticky="e", pady=(12, 0))
    pw2.bind("<Return>", save)
    pw1.focus_set()
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))
    root.mainloop()
    return result["ok"]


# ---------------------------------------------------------------- 트레이 아이콘
def make_icon_image():
    from PIL import Image, ImageDraw
    s = 64
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, s - 3, s - 3), radius=14, fill=(15, 107, 102, 255))
    d.rounded_rectangle((12, 15, 52, 42), radius=3, fill=(255, 255, 255, 255))       # 모니터
    d.rectangle((16, 19, 48, 38), fill=(15, 107, 102, 255))
    d.rectangle((28, 42, 36, 48), fill=(255, 255, 255, 255))                          # 받침
    d.rectangle((22, 48, 42, 51), fill=(255, 255, 255, 255))
    d.polygon([(30, 22), (30, 36), (33, 33), (36, 38), (38, 37), (35, 32), (40, 32)], fill=(255, 255, 255, 255))
    return img


def run_tray(args, cfg, main_async, config_dir, short_fp, local_ips):
    import win_service as svc
    try:
        import pystray
        make_icon_image()
    except Exception as e:
        # 아이콘을 못 만들어도 원격 접속은 되게: 아이콘 없이 서버만 실행
        import traceback
        traceback.print_exc()
        if svc.service_installed():
            message_box(f"작업 표시줄 아이콘을 만들지 못했습니다.\n원격 접속(잠금 화면 모드)은 그대로 켜져 있습니다.\n\n{e!r}",
                        error=True)
            return
        threading.Thread(target=message_box, daemon=True, args=(
            "작업 표시줄 아이콘을 만들지 못해 아이콘 없이 실행합니다. 원격 접속은 됩니다.\n"
            f"(끄려면 작업 관리자에서 sisico_remote_host 를 끝내세요)\n\n{e!r}", APP_NAME, True)).start()
        asyncio.run(main_async(args, cfg))
        return

    service = svc.service_installed()   # 잠금 화면 모드: 원격 접속은 SYSTEM 쪽이 담당, 트레이는 안내만
    state = {"info": None, "active": 0}
    icon = None

    if service and svc.installed_is_outdated():
        if ask_yes_no("새 버전을 받으셨네요.\n잠금 화면용으로 설치된 프로그램도 새 버전으로 바꿀까요?\n"
                      "(관리자 확인 창이 뜹니다)"):
            want = svc.file_hash(sys.executable)
            if svc.run_elevated(["--install-service", config_dir()],
                                lambda: svc.file_hash(svc.installed_exe()) == want):
                message_box("업데이트했습니다.")
            else:
                message_box("업데이트하지 못했습니다. 나중에 다시 실행해 주세요.", error=True)

    # 자동 실행이 꺼져 있으면 한 번 물어봄 (예전 버전에서 비밀번호를 정한 경우 설정 창을 못 봤으므로)
    asked = os.path.join(config_dir(), "autostart_asked")
    if not autostart_enabled() and not os.path.exists(asked):
        try:
            open(asked, "w").close()
        except OSError:
            pass
        if ask_yes_no("Windows 를 켤 때 Sisico 원격도 자동으로 실행할까요?\n(켜 두지 않으면 재부팅 후 직접 실행해야 접속됩니다)"):
            try:
                set_autostart(True)
            except OSError as e:
                message_box(f"설정하지 못했습니다: {e}", error=True)

    def on_ready(info):
        state["info"] = info
        if icon:
            icon.title = f"{APP_NAME} - 실행 중 (포트 {info['port']})"

    def on_event(kind, ip, active):
        state["active"] = active
        if icon is None:
            return
        try:
            if kind == "connected":
                icon.notify(f"{ip} 에서 이 PC에 접속했습니다.", APP_NAME)
            elif kind == "auth_failed":
                icon.notify(f"{ip} 에서 틀린 비밀번호로 접속을 시도했습니다.", APP_NAME)
        except Exception:
            pass

    def server_thread():
        try:
            asyncio.run(main_async(args, cfg, on_ready=on_ready, on_event=on_event))
        except OSError as e:
            message_box(f"시작하지 못했습니다. 포트 {args.port} 를 다른 프로그램이 쓰고 있을 수 있습니다.\n\n{e}",
                        error=True)
            if icon:
                icon.stop()
        except Exception as e:  # 예상 못 한 오류도 알려 줌
            message_box(f"오류로 멈췄습니다:\n{e!r}", error=True)
            if icon:
                icon.stop()

    def service_info():
        import ssl
        from remote_proto import fingerprint
        try:
            with open(os.path.join(svc.machine_dir(), "cert.pem"), encoding="ascii") as f:
                fp = fingerprint(ssl.PEM_cert_to_DER_cert(f.read()))
        except OSError:
            fp = ""
        return {"port": int(cfg.get("port", 8765)), "ips": local_ips(), "fp": fp}

    def show_info(_icon=None, _item=None):
        info = service_info() if service else state["info"]
        if not info:
            message_box("아직 시작 중입니다. 잠시 후 다시 눌러 주세요.")
            return
        lines = []
        for ip in info["ips"]:
            tag = "  (Tailscale: 밖에서 LTE로 접속)" if ip.startswith("100.") else "  (같은 와이파이)"
            lines.append(f"   {ip}{tag}")
        mode = ("잠금 화면·로그인 전에도 접속: 켜짐" if service else
                "잠금 화면·로그인 전에도 접속: 꺼짐 (로그인한 동안만 접속)")
        text = ("앱에 입력할 주소\n" + ("\n".join(lines) or "   (찾지 못함)") +
                f"\n\n포트: {info['port']}\n\n이 PC의 지문: {short_fp(info['fp']) if info['fp'] else '?'}\n"
                "(앱에서 PC를 등록할 때 나오는 지문과 같은지 확인하세요)\n\n" + mode +
                ("" if service else f"\n지금 접속 중: {state['active']}대"))
        threading.Thread(target=message_box, args=(text, f"{APP_NAME} - 연결 정보"), daemon=True).start()

    def change_password(_icon, _item):
        if service:   # 서비스 설정은 관리자만 바꿀 수 있음
            import ctypes
            cmd = self_command("--setup", "--machine")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", cmd[0], " ".join(f'"{a}"' for a in cmd[1:]), None, 1)
        else:
            subprocess.Popen(self_command("--setup"))

    def toggle_service(_icon, _item):
        if not getattr(sys, "frozen", False):
            message_box("설치용 exe 에서만 쓸 수 있습니다.", error=True)
            return
        if not service:
            if not ask_yes_no("PC를 켜기만 하면 로그인 전·잠금 화면에서도 원격 접속되도록 할까요?\n\n"
                              "· 관리자 확인 창이 한 번 뜹니다.\n"
                              "· 프로그램이 C:\\Program Files\\SisicoRemote 에 설치되고 윈도우와 함께 시작됩니다.\n"
                              "· 비밀번호와 지문은 그대로입니다 (앱에서 다시 등록할 필요 없음)."):
                return
            if svc.run_elevated(["--install-service", config_dir()], svc.service_installed):
                message_box("켜졌습니다. 이제 재부팅 후 로그인 전이나 잠금 화면에서도 접속됩니다.")
                restart_tray()
            else:
                message_box("설치하지 못했습니다 (관리자 확인을 취소했거나 오류).", error=True)
        else:
            if not ask_yes_no("잠금 화면·로그인 전 접속을 끌까요?\n(끈 뒤에는 로그인한 동안만 접속됩니다)"):
                return
            if svc.run_elevated(["--uninstall-service"], lambda: not svc.service_installed()):
                restart_tray()
            else:
                message_box("끄지 못했습니다 (관리자 확인을 취소했거나 오류).", error=True)

    def toggle_autostart(_icon, _item):
        try:
            set_autostart(not autostart_enabled())
        except OSError as e:
            message_box(f"설정하지 못했습니다: {e}", error=True)

    def open_folder(_icon, _item):
        os.startfile(svc.machine_dir() if service else config_dir())

    def quit_app(_icon, _item):
        _icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("연결 정보 보기", show_info, default=True),
        pystray.MenuItem("비밀번호 바꾸기", change_password),
        pystray.MenuItem("잠금 화면·로그인 전에도 접속", toggle_service, checked=lambda _: service),
        pystray.MenuItem("Windows 시작 시 자동 실행" + (" (이 아이콘)" if service else ""), toggle_autostart,
                         checked=lambda _: autostart_enabled()),
        pystray.MenuItem("설정·로그 폴더 열기", open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("아이콘 닫기 (원격 접속은 계속 켜짐)" if service else "종료 (원격 접속 끄기)", quit_app),
    )
    title = f"{APP_NAME} - " + ("잠금 화면에서도 접속 가능" if service else "시작 중")
    icon = pystray.Icon("SisicoRemoteHost", make_icon_image(), title, menu)
    if not service:
        threading.Thread(target=server_thread, daemon=True).start()

    def first_notice(ic):
        ic.visible = True
        try:
            ic.notify("실행 중입니다. 아이콘을 누르면 주소와 지문을 볼 수 있습니다." +
                      (" (잠금 화면에서도 접속 가능)" if service else ""), APP_NAME)
        except Exception:
            pass

    icon.run(setup=first_notice)
    os._exit(0)
