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

    k32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    u32.OpenInputDesktop.restype = wintypes.HANDLE
    u32.GetThreadDesktop.restype = wintypes.HANDLE

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
        """이 스레드를 지금 입력을 받는 데스크톱(일반/잠금 화면/UAC)으로 옮김. 옮겼으면 True."""
        h = u32.OpenInputDesktop(0, False, GENERIC_ALL)
        if not h:
            return False
        name = _desk_name(h)
        if getattr(_tls, "name", None) == name:
            u32.CloseDesktop(h)
            return False
        if not u32.SetThreadDesktop(h):
            u32.CloseDesktop(h)
            return False
        old = getattr(_tls, "handle", None)
        _tls.handle, _tls.name = h, name
        if old:
            u32.CloseDesktop(old)
        return True

else:
    def active_session():
        return 1

    def follow_input_desktop():
        return False

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


def install(user_config_dir, extra_args=()):
    """관리자 권한으로 실행됨. 성공하면 True."""
    if not getattr(sys, "frozen", False):
        log("install: only the packaged exe can be installed")
        return False
    _run(["schtasks", "/End", "/TN", TASK_NAME])          # 업데이트: 돌던 것을 먼저 멈춤
    time.sleep(1.5)
    os.makedirs(install_dir(), exist_ok=True)
    md = machine_dir()
    os.makedirs(md, exist_ok=True)
    for _ in range(10):                                    # 방금 멈춘 exe 가 아직 잡혀 있을 수 있음
        try:
            shutil.copy2(sys.executable, installed_exe())
            break
        except OSError:
            time.sleep(1)
    else:
        return False
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
        return False
    os.remove(xml)
    with open(marker_path(), "w", encoding="utf-8") as f:
        json.dump({"installed": time.time()}, f)
    _run(["icacls", marker_path(), "/grant", "*S-1-5-32-545:R"])
    _run(["schtasks", "/Run", "/TN", TASK_NAME])
    return True


def uninstall():
    _run(["schtasks", "/End", "/TN", TASK_NAME])
    _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    try:
        os.remove(marker_path())
    except OSError:
        pass
    time.sleep(1)
    shutil.rmtree(install_dir(), ignore_errors=True)
    return True


def run_elevated(args, wait_for, timeout=60):
    """관리자 확인 창(UAC)을 띄워 이 exe 를 args 로 실행하고, wait_for() 가 True 가 될 때까지 기다림."""
    params = " ".join(f'"{a}"' for a in args)
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 0)
    if r <= 32:
        return False                    # 사용자가 '아니요'를 누름
    end = time.time() + timeout
    while time.time() < end:
        if wait_for():
            return True
        time.sleep(0.5)
    return False
