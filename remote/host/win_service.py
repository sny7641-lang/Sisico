"""잠금 화면·로그인 전에도 접속되게 하는 '서비스 모드' (윈도우 전용).

구조
  작업 스케줄러 (부팅 시, SYSTEM)  →  sisico_remote_host.exe --supervisor        (세션 0, 화면 없음)
      감시 프로그램이 지금 화면 세션(콘솔 세션)에 SYSTEM 권한으로 호스트를 띄움
  →  sisico_remote_host.exe --machine --system-child                            (세션 1 등, SYSTEM)
      지금 보이는 데스크톱(로그인·잠금 화면 = Winlogon, UAC 창, 일반 바탕 화면)으로
      스레드를 옮겨 가며 캡처·입력

보안
  - SYSTEM 으로 실행되는 exe 는 관리자만 고칠 수 있는 Program Files 에 복사해서 씀
  - 설정·인증서는 %ProgramData%\\SisicoRemote (개인 키·설정은 SYSTEM·관리자만 읽기)
  - 감시 프로그램이 죽으면 호스트도 같이 끝나도록 Job 객체로 묶음
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

IS_WINDOWS = sys.platform == "win32"
TASK_NAME = "SisicoRemoteHost"
HOST_EXE = "sisico_remote_host.exe"


def machine_dir():
    d = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "SisicoRemote")
    return d


def install_dir():
    return os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "SisicoRemote")


def installed_exe():
    return os.path.join(install_dir(), HOST_EXE)


def marker_path():
    return os.path.join(machine_dir(), "service.json")


def service_installed():
    return IS_WINDOWS and os.path.exists(marker_path()) and os.path.exists(installed_exe())


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def installed_is_outdated():
    """지금 실행한 exe 가 설치된 것과 다르면 True (새 버전을 받은 경우)."""
    if not (service_installed() and getattr(sys, "frozen", False)):
        return False
    try:
        return file_hash(sys.executable) != file_hash(installed_exe())
    except OSError:
        return False


def log(msg):
    try:
        os.makedirs(machine_dir(), exist_ok=True)
        with open(os.path.join(machine_dir(), "service.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


# ======================================================================== Win32 (ctypes)
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    a32 = ctypes.WinDLL("advapi32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)

    TOKEN_ALL_ACCESS = 0xF01FF
    MAXIMUM_ALLOWED = 0x02000000
    SecurityImpersonation, TokenPrimary, TokenSessionId = 2, 1, 12
    CREATE_NO_WINDOW, CREATE_UNICODE_ENVIRONMENT, CREATE_BREAKAWAY_FROM_JOB = 0x08000000, 0x400, 0x01000000
    INFINITE_WAIT_0 = 0
    WAIT_TIMEOUT = 0x102
    GENERIC_ALL = 0x10000000
    UOI_NAME = 2

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                    ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                    ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                    ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                    ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                    ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount",
                                                   "OtherOperationCount", "ReadTransferCount",
                                                   "WriteTransferCount", "OtherTransferCount")]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    # 핸들은 64비트 값이라 형을 꼭 지정해야 함 (안 하면 int 로 넘어가 OverflowError)
    H, D, B = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
    PH = ctypes.POINTER(wintypes.HANDLE)

    def _sig(fn, res, *args):
        fn.restype, fn.argtypes = res, list(args)

    _sig(k32.WTSGetActiveConsoleSessionId, D)
    _sig(k32.GetCurrentProcess, H)
    _sig(k32.CloseHandle, B, H)
    _sig(k32.WaitForSingleObject, D, H, D)
    _sig(k32.TerminateProcess, B, H, wintypes.UINT)
    _sig(k32.CreateJobObjectW, H, ctypes.c_void_p, wintypes.LPCWSTR)
    _sig(k32.SetInformationJobObject, B, H, ctypes.c_int, ctypes.c_void_p, D)
    _sig(k32.AssignProcessToJobObject, B, H, H)
    _sig(a32.OpenProcessToken, B, H, D, PH)
    _sig(a32.DuplicateTokenEx, B, H, D, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, PH)
    _sig(a32.SetTokenInformation, B, H, ctypes.c_int, ctypes.c_void_p, D)
    _sig(a32.CreateProcessAsUserW, B, H, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
         B, D, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p)
    _sig(u32.OpenInputDesktop, H, D, B, D)
    _sig(u32.OpenDesktopW, H, wintypes.LPCWSTR, D, B, D)
    _sig(u32.SetThreadDesktop, B, H)
    _sig(u32.CloseDesktop, B, H)
    _sig(u32.GetUserObjectInformationW, B, H, ctypes.c_int, ctypes.c_void_p, D, ctypes.POINTER(D))
    _sig(wts.WTSQuerySessionInformationW, B, H, D, ctypes.c_int, ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(D))
    _sig(wts.WTSFreeMemory, None, ctypes.c_void_p)

    def active_session():
        return k32.WTSGetActiveConsoleSessionId()

    def _kill_on_close_job():
        job = k32.CreateJobObjectW(None, None)
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))  # ExtendedLimitInformation
        return job

    def spawn_in_session(session, cmdline):
        """지금 프로세스(SYSTEM)의 토큰을 복제해 다른 세션에서 실행. (프로세스 핸들, pid) 반환."""
        tok = wintypes.HANDLE()
        if not a32.OpenProcessToken(k32.GetCurrentProcess(), TOKEN_ALL_ACCESS, ctypes.byref(tok)):
            raise ctypes.WinError(ctypes.get_last_error())
        dup = wintypes.HANDLE()
        try:
            if not a32.DuplicateTokenEx(tok, MAXIMUM_ALLOWED, None, SecurityImpersonation, TokenPrimary,
                                        ctypes.byref(dup)):
                raise ctypes.WinError(ctypes.get_last_error())
            sid = wintypes.DWORD(session)
            if not a32.SetTokenInformation(dup, TokenSessionId, ctypes.byref(sid), ctypes.sizeof(sid)):
                raise ctypes.WinError(ctypes.get_last_error())
            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(si)
            si.lpDesktop = "winsta0\\default"
            pi = PROCESS_INFORMATION()
            buf = ctypes.create_unicode_buffer(cmdline)
            if not a32.CreateProcessAsUserW(dup, None, buf, None, None, False,
                                            CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
                                            None, None, ctypes.byref(si), ctypes.byref(pi)):
                raise ctypes.WinError(ctypes.get_last_error())
            k32.CloseHandle(pi.hThread)
            return pi.hProcess, pi.dwProcessId
        finally:
            k32.CloseHandle(tok)
            if dup:
                k32.CloseHandle(dup)

    def process_alive(h):
        return k32.WaitForSingleObject(h, 0) == WAIT_TIMEOUT

    def session_user(session):
        """세션에 로그인한 사용자 이름 (없으면 빈 문자열)."""
        buf = wintypes.LPWSTR()
        size = wintypes.DWORD()
        if not wts.WTSQuerySessionInformationW(None, session, 5, ctypes.byref(buf), ctypes.byref(size)):  # WTSUserName
            return ""
        try:
            return buf.value or ""
        finally:
            wts.WTSFreeMemory(buf)

    # ---------------------------------------------------------------- 데스크톱 따라가기
    _tls = threading.local()

    def _desk_name(h):
        buf = ctypes.create_unicode_buffer(256)
        need = wintypes.DWORD()
        u32.GetUserObjectInformationW(h, UOI_NAME, buf, ctypes.sizeof(buf), ctypes.byref(need))
        return buf.value

    def follow_input_desktop():
        """이 스레드를 지금 입력을 받는 데스크톱(일반 Default / 잠금·로그인 Winlogon / UAC)으로 옮김.
        옮겼으면 새 데스크톱 이름, 아니면 None."""
        h = u32.OpenInputDesktop(0, False, GENERIC_ALL)
        if not h:
            return None
        name = _desk_name(h)
        if getattr(_tls, "name", None) == name:
            u32.CloseDesktop(h)
            return None
        if not u32.SetThreadDesktop(h):
            err = ctypes.get_last_error()
            u32.CloseDesktop(h)
            log(f"SetThreadDesktop({name}) failed: {err}")
            return None
        old = getattr(_tls, "handle", None)
        _tls.handle, _tls.name = h, name
        if old:
            u32.CloseDesktop(old)
        return name

    def self_check():
        """SYSTEM 호스트 시작 때: 지금 데스크톱과 로그인·잠금 화면(Winlogon) 데스크톱을 실제로 캡처해 보고 기록."""
        def try_desktop(name):
            try:
                h = u32.OpenInputDesktop(0, False, GENERIC_ALL) if name is None else u32.OpenDesktopW(name, 0, False, GENERIC_ALL)
                if not h:
                    return f"open failed ({ctypes.get_last_error()})"
                real = _desk_name(h)
                if not u32.SetThreadDesktop(h):
                    return f"{real}: SetThreadDesktop failed ({ctypes.get_last_error()})"
                import mss
                with mss.mss() as s:
                    shot = s.grab(s.monitors[1])
                    raw = shot.raw
                    lit = sum(1 for i in range(0, len(raw), 4 * 997) if raw[i] or raw[i + 1] or raw[i + 2])
                return f"{real}: capture ok {shot.width}x{shot.height}, non-black samples {lit}"
            except Exception as e:
                return f"error {e!r}"
        # 화면에 보이는 데스크톱만 캡처할 수 있음 (잠겨 있으면 Winlogon, 아니면 Default)
        out = {}
        t = threading.Thread(target=lambda: out.update(r=try_desktop(None)))   # 새 스레드: 창·훅 없음
        t.start()
        t.join(20)
        log(f"self-check input desktop: {out.get('r', 'timeout')}")

else:
    def self_check():
        pass

    def active_session():
        return 1

    def follow_input_desktop():
        return None

    def session_user(session):
        return ""


def user_home():
    """파일을 저장·탐색할 '사용자 폴더'. SYSTEM 으로 돌 때는 지금 로그인한 사람의 폴더."""
    if IS_WINDOWS and os.environ.get("SISICO_MACHINE") == "1":
        name = session_user(active_session())
        base = os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "Users")
        if name and os.path.isdir(os.path.join(base, name)):
            return os.path.join(base, name)
        return os.path.join(base, "Public")
    return os.path.expanduser("~")


# ======================================================================== 감시 프로그램
def supervisor(extra_args=()):
    """세션 0 에서 계속 돌며, 지금 화면 세션에 호스트(SYSTEM)가 떠 있게 유지."""
    log("supervisor start")
    job = _kill_on_close_job()
    exe = installed_exe() if os.path.exists(installed_exe()) else sys.executable
    child, child_session, last_start = None, None, 0.0
    while True:
        try:
            s = active_session()
            if s == 0xFFFFFFFF:          # 세션이 바뀌는 중
                time.sleep(1)
                continue
            alive = child is not None and process_alive(child)
            if alive and s != child_session:
                log(f"console session {child_session} -> {s}, restarting host")
                k32.TerminateProcess(child, 0)
                alive = False
            if not alive and time.time() - last_start > 3:
                if child:
                    k32.CloseHandle(child)
                cmd = f'"{exe}" --machine --system-child ' + " ".join(extra_args)
                child, pid = spawn_in_session(s, cmd.strip())
                k32.AssignProcessToJobObject(job, child)
                child_session, last_start = s, time.time()
                log(f"host started in session {s} (pid {pid})")
        except Exception as e:
            log(f"supervisor error: {e!r}")
            time.sleep(5)
        time.sleep(2)


# ======================================================================== 설치 / 제거 (관리자)
TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Sisico 원격: 잠금 화면·로그인 전에도 원격 접속</Description></RegistrationInfo>
  <Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>4</Priority>
    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author"><Exec><Command>{exe}</Command><Arguments>--supervisor{extra}</Arguments></Exec></Actions>
</Task>
"""


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000 if IS_WINDOWS else 0)
    log(f"{' '.join(cmd)} -> {r.returncode} {r.stdout.strip()} {r.stderr.strip()}")
    return r.returncode


def _stop_installed_processes():
    """Program Files 의 호스트 exe 로 돌고 있는 프로세스를 모두 끝냄 (업데이트 전에 파일 잠금 해제)."""
    path = installed_exe().replace("'", "''")
    _run(["powershell", "-NoProfile", "-Command",
          f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -eq '{path}' }} | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"])


def install(user_config_dir, extra_args=()):
    """관리자 권한으로 실행됨. 성공하면 "", 실패하면 사람이 읽을 이유."""
    if not getattr(sys, "frozen", False):
        return "설치용 exe 에서만 설치할 수 있습니다."
    _run(["schtasks", "/End", "/TN", TASK_NAME])          # 업데이트: 돌던 것을 먼저 멈춤
    _stop_installed_processes()
    time.sleep(1.5)
    os.makedirs(install_dir(), exist_ok=True)
    md = machine_dir()
    os.makedirs(md, exist_ok=True)
    last = None
    for _ in range(40):                                    # 백신 검사 등으로 파일이 잠시 잡혀 있을 수 있음
        try:
            if os.path.abspath(sys.executable).lower() != installed_exe().lower():
                shutil.copy2(sys.executable, installed_exe())
            break
        except OSError as e:
            last = e
            _stop_installed_processes()
            time.sleep(1)
    else:
        log(f"install: copy failed: {last!r}")
        return (f"프로그램 파일을 바꾸지 못했습니다.\n{installed_exe()}\n{last}\n\n"
                "백신(알약 등)이 막고 있을 수 있습니다. 알약 '검역소'에 sisico_remote_host 가 있는지 확인하세요.")
    for name in ("config.json", "cert.pem", "key.pem"):    # 비밀번호·지문 그대로 옮김
        src, dst = os.path.join(user_config_dir, name), os.path.join(md, name)
        if not os.path.exists(src) or os.path.abspath(src) == os.path.abspath(dst):
            continue
        if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
            shutil.copy2(src, dst)
    # 폴더는 SYSTEM·관리자만, 인증서(공개 정보)만 일반 사용자도 읽기 (트레이에서 지문 표시용)
    _run(["icacls", md, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"])
    _run(["icacls", os.path.join(md, "cert.pem"), "/grant", "*S-1-5-32-545:R"])
    _run(["icacls", md, "/grant", "*S-1-5-32-545:(RX)"])
    _run(["icacls", install_dir(), "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F",
          "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-32-545:(OI)(CI)RX"])
    extra = "".join(" " + a for a in extra_args)
    xml = os.path.join(md, "task.xml")
    with open(xml, "w", encoding="utf-16") as f:
        f.write(TASK_XML.replace("{exe}", installed_exe()).replace("{extra}", extra))
    if _run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", xml, "/F"]) != 0:
        return "작업 스케줄러에 등록하지 못했습니다. (설정·로그 폴더의 service.log 참고)"
    os.remove(xml)
    with open(marker_path(), "w", encoding="utf-8") as f:
        json.dump({"installed": time.time()}, f)
    _run(["icacls", marker_path(), "/grant", "*S-1-5-32-545:R"])
    _run(["icacls", os.path.join(md, "service.log"), "/grant", "*S-1-5-32-545:R"])
    _run(["schtasks", "/Run", "/TN", TASK_NAME])
    return ""


def uninstall():
    _run(["schtasks", "/End", "/TN", TASK_NAME])
    _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    _stop_installed_processes()
    try:
        os.remove(marker_path())
    except OSError:
        pass
    time.sleep(1)
    shutil.rmtree(install_dir(), ignore_errors=True)
    return ""


def run_elevated(args, timeout=300):
    """관리자 확인 창(UAC)을 띄워 이 exe 를 args 로 실행하고 끝날 때까지 기다림. (성공 여부, 이유) 반환."""
    import tempfile
    result = os.path.join(tempfile.gettempdir(), f"sisico_remote_result_{os.getpid()}_{int(time.time())}.txt")
    params = " ".join(f'"{a}"' for a in list(args) + ["--result", result])
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 0)
    if r <= 32:
        return False, "관리자 확인 창에서 '아니요'를 눌렀거나 창이 뜨지 못했습니다."
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(result):
            time.sleep(0.3)
            try:
                with open(result, encoding="utf-8") as f:
                    text = f.read().strip()
                os.remove(result)
            except OSError:
                continue
            return text == "ok", ("" if text == "ok" else text)
        time.sleep(0.5)
    return False, f"{timeout // 60}분 넘게 끝나지 않았습니다. 백신(알약 등)이 막고 있을 수 있습니다."
