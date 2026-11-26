"""Sisico Remote 호스트 (윈도우 PC에서 실행).

휴대폰 앱이 WebSocket(기본 포트 8765)으로 접속하면 화면을 H.264(또는 JPEG)로 보내고,
앱에서 오는 마우스·키보드 입력을 PC에 그대로 넣습니다.

  sisico_remote_host.exe                 # 실행 (처음이면 비밀번호를 정합니다)
  sisico_remote_host.exe --set-password  # 비밀번호 바꾸기
  sisico_remote_host.exe --port 9000     # 포트 바꾸기

프로토콜 요약 (protocol.md 에 자세히):
  서버 → {"t":"hello","nonce":..}  클라 → {"t":"auth","mac":HMAC(sha256(pw), nonce)}
  서버 → {"t":"ok","monitors":[..]} 클라 → {"t":"start", codec/mon/fps/maxw/kbps/q}
  서버 → {"t":"stream",codec,w,h} 다음 바이너리 프레임 [종류 1바이트][플래그 1바이트][데이터]
"""
import argparse
import asyncio
import concurrent.futures
import getpass
import hashlib
import hmac
import json
import os
import secrets
import socket
import sys
import time
from fractions import Fraction

import numpy as np

import win_input as wi

VERSION = 1
DEFAULT_PORT = 8765
DISCOVERY_PORT = 8766
DISCOVER_MAGIC = b"SISICO_REMOTE_DISCOVER"

PKT_H264, PKT_JPEG, PKT_FILE = 1, 2, 3
PKT_UPLOAD = 0x10  # 휴대폰 → PC 파일 조각
FILE_CHUNK = 256 * 1024
FLAG_KEY = 1


# ---------------------------------------------------------------- 설정 파일
def config_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "SisicoRemote")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def password_key(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def ask_password(cfg):
    while True:
        a = getpass.getpass("접속 비밀번호를 정하세요 (6자 이상): ")
        if len(a) < 6:
            print("  6자 이상이어야 합니다.")
            continue
        if getpass.getpass("한 번 더 입력: ") != a:
            print("  두 번 입력한 비밀번호가 다릅니다.")
            continue
        cfg["key"] = password_key(a)
        save_config(cfg)
        print(f"  저장했습니다: {config_path()}")
        return


# ---------------------------------------------------------------- 화면 캡처
class TestPattern:
    """--test 모드: 실제 화면 대신 움직이는 무늬 (화면이 없는 곳에서 시험용)."""
    monitors = [{"left": 0, "top": 0, "width": 1280, "height": 720}]

    def __init__(self):
        self.t = 0

    def grab(self, mon):
        h, w = mon["height"], mon["width"]
        self.t += 1
        img = np.zeros((h, w, 4), np.uint8)
        x = np.arange(w, dtype=np.uint16)
        img[:, :, 0] = ((x + self.t * 8) % 256).astype(np.uint8)
        img[:, :, 1] = (np.arange(h, dtype=np.uint16)[:, None] % 256).astype(np.uint8)
        img[:, :, 2] = 128
        s = (self.t * 6) % (w - 100)
        img[300:400, s:s + 100, :3] = 255
        return img

    def close(self):
        pass


class ScreenCapture:
    def __init__(self):
        import mss
        self.sct = mss.mss()
        self.monitors = self.sct.monitors[1:] or self.sct.monitors

    def grab(self, mon):
        shot = self.sct.grab(mon)
        return np.frombuffer(shot.raw, np.uint8).reshape(shot.height, shot.width, 4)

    def close(self):
        self.sct.close()


def list_monitors(test):
    if test:
        return TestPattern.monitors
    cap = ScreenCapture()
    try:
        return [dict(left=m["left"], top=m["top"], width=m["width"], height=m["height"]) for m in cap.monitors]
    finally:
        cap.close()


# ---------------------------------------------------------------- 인코더
def fit_size(w, h, max_side):
    if max_side and max(w, h) > max_side:
        s = max_side / max(w, h)
        w, h = w * s, h * s
    return max(2, int(w) // 2 * 2), max(2, int(h) // 2 * 2)


class H264Encoder:
    codec = "h264"

    def __init__(self, w, h, fps, kbps):
        import av
        self.av = av
        self.w, self.h = w, h
        ctx = av.CodecContext.create("libx264", "w")
        ctx.width, ctx.height = w, h
        ctx.pix_fmt = "yuv420p"
        ctx.time_base = Fraction(1, 1000)
        ctx.framerate = Fraction(fps, 1)
        ctx.bit_rate = kbps * 1000
        ctx.gop_size = fps * 10
        ctx.max_b_frames = 0
        buf = max(kbps // max(fps, 1) * 3, 200)
        ctx.options = {
            "preset": "ultrafast", "tune": "zerolatency", "profile": "baseline",
            "x264-params": f"repeat-headers=1:bframes=0:rc-lookahead=0:sliced-threads=1:"
                           f"vbv-maxrate={kbps}:vbv-bufsize={buf}:keyint={fps * 10}:min-keyint={fps}",
        }
        self.ctx = ctx
        self.t0 = time.monotonic()
        self.last_pts = -1

    def encode(self, bgra, force_key):
        av = self.av
        frame = av.VideoFrame.from_ndarray(bgra, format="bgra")
        frame = frame.reformat(width=self.w, height=self.h, format="yuv420p")
        pts = int((time.monotonic() - self.t0) * 1000)
        if pts <= self.last_pts:
            pts = self.last_pts + 1
        self.last_pts = pts
        frame.pts = pts
        if force_key:
            frame.pict_type = av.video.frame.PictureType.I
        packets = self.ctx.encode(frame)
        data = b"".join(bytes(p) for p in packets)
        key = any(p.is_keyframe for p in packets)
        return data, key


class JpegEncoder:
    codec = "jpeg"

    def __init__(self, w, h, quality):
        from PIL import Image
        self.Image = Image
        self.w, self.h, self.q = w, h, quality

    def encode(self, bgra, force_key):
        import io
        h, w = bgra.shape[:2]
        img = self.Image.frombuffer("RGB", (w, h), bgra.tobytes(), "raw", "BGRX", 0, 1)
        if (w, h) != (self.w, self.h):
            img = img.resize((self.w, self.h), self.Image.BILINEAR)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=self.q)
        return out.getvalue(), True


# ---------------------------------------------------------------- 스트림 (연결 1개당 1개)
class Stream:
    def __init__(self, test):
        self.test = test
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)  # mss 는 만든 스레드에서만 써야 함
        self.cap = None
        self.enc = None
        self.cfg = None
        self.pending = None
        self.want_key = True
        self.prev = None
        self.last_sent = 0.0

    def configure(self, cfg):
        self.pending = cfg

    def monitor(self):
        mons = self.cap.monitors
        idx = int(self.cfg.get("mon", 0))
        return mons[idx if 0 <= idx < len(mons) else 0]

    def produce(self):
        """캡처 + 인코딩 (작업 스레드에서 실행). (안내 메시지 또는 None, 바이너리 또는 None) 반환."""
        info = None
        if self.cap is None:
            self.cap = TestPattern() if self.test else ScreenCapture()
        if self.pending is not None:
            self.cfg, self.pending = self.pending, None
            mon = self.monitor()
            w, h = fit_size(mon["width"], mon["height"], int(self.cfg.get("maxw", 1920)))
            codec = self.cfg.get("codec", "h264")
            if codec == "h264":
                try:
                    self.enc = H264Encoder(w, h, int(self.cfg.get("fps", 30)), int(self.cfg.get("kbps", 6000)))
                except Exception as e:  # libx264 를 못 쓰면 JPEG 로
                    print("H.264 인코더를 만들 수 없어 JPEG 로 보냅니다:", e)
                    codec = "jpeg"
            if codec == "jpeg":
                self.enc = JpegEncoder(w, h, int(self.cfg.get("q", 70)))
            self.want_key, self.prev = True, None
            info = {"t": "stream", "codec": self.enc.codec, "w": w, "h": h,
                    "mon": self.cfg.get("mon", 0), "mw": mon["width"], "mh": mon["height"]}
        if self.enc is None:
            return info, None
        frame = self.cap.grab(self.monitor())
        now = time.monotonic()
        same = self.prev is not None and self.prev.shape == frame.shape and np.array_equal(self.prev, frame)
        if same and not self.want_key and now - self.last_sent < 1.0:
            return info, None  # 화면이 그대로면 보내지 않음 (최소 1초에 한 번은 보냄)
        self.prev = frame.copy()
        force = self.want_key
        self.want_key = False
        data, key = self.enc.encode(frame, force)
        if not data:
            return info, None
        self.last_sent = now
        kind = PKT_H264 if self.enc.codec == "h264" else PKT_JPEG
        return info, bytes([kind, FLAG_KEY if key else 0]) + data

    def close(self):
        def _c():
            if self.cap:
                self.cap.close()
        try:
            self.pool.submit(_c).result(timeout=2)
        except Exception:
            pass
        self.pool.shutdown(wait=False)


# ---------------------------------------------------------------- 파일 전송
def receive_dir():
    d = os.path.join(os.path.expanduser("~"), "Downloads", "Sisico 원격")
    os.makedirs(d, exist_ok=True)
    return d


def safe_name(name):
    name = os.path.basename(str(name).replace("\\", "/")) or "file"
    name = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in name).strip(" .") or "file"
    return name[:200]


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    path, n = os.path.join(folder, name), 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base} ({n}){ext}")
        n += 1
    return path


def list_dir(path):
    """폴더 내용. path 가 비어 있으면 자주 쓰는 폴더와 드라이브 목록."""
    if not path:
        home = os.path.expanduser("~")
        items = []
        for label, sub in (("바탕 화면", "Desktop"), ("다운로드", "Downloads"), ("문서", "Documents"), ("사진", "Pictures")):
            p = os.path.join(home, sub)
            if os.path.isdir(p):
                items.append({"name": label, "path": p, "dir": True})
        if sys.platform == "win32":
            import string
            for letter in string.ascii_uppercase:
                p = f"{letter}:\\"
                if os.path.exists(p):
                    items.append({"name": f"{letter}: 드라이브", "path": p, "dir": True})
        else:
            items.append({"name": "/", "path": "/", "dir": True})
        return {"t": "ls", "path": "", "parent": None, "items": items}
    path = os.path.abspath(path)
    items = []
    with os.scandir(path) as it:
        for e in it:
            try:
                is_dir = e.is_dir()
                items.append({"name": e.name, "path": e.path, "dir": is_dir,
                              "size": 0 if is_dir else e.stat().st_size})
            except OSError:
                continue
            if len(items) >= 3000:
                break
    items.sort(key=lambda i: (not i["dir"], i["name"].lower()))
    parent = os.path.dirname(path.rstrip("\\/")) or None
    if parent == path or (sys.platform == "win32" and len(path) <= 3):
        parent = ""  # 드라이브 맨 위 → 처음 목록으로
    return {"t": "ls", "path": path, "parent": parent, "items": items}


# ---------------------------------------------------------------- 연결 처리
class Host:
    def __init__(self, key_hex, test=False):
        self.key = bytes.fromhex(key_hex)
        self.test = test
        self.fails = {}  # ip -> (횟수, 마지막 시각)
        self.active = 0

    def _blocked(self, ip):
        n, t = self.fails.get(ip, (0, 0))
        if time.time() - t > 300:
            self.fails.pop(ip, None)
            return False
        return n >= 5

    async def handler(self, ws):
        ip = ws.remote_address[0] if ws.remote_address else "?"
        if self._blocked(ip):
            await ws.close(4003, "too many attempts")
            return
        nonce = secrets.token_bytes(16)
        await ws.send(json.dumps({"t": "hello", "nonce": nonce.hex(), "name": socket.gethostname(), "ver": VERSION}))
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), 15))
            mac = bytes.fromhex(msg.get("mac", ""))
        except Exception:
            return
        expect = hmac.new(self.key, nonce, hashlib.sha256).digest()
        if msg.get("t") != "auth" or not hmac.compare_digest(mac, expect):
            n, _ = self.fails.get(ip, (0, 0))
            self.fails[ip] = (n + 1, time.time())
            await asyncio.sleep(1)
            await ws.send(json.dumps({"t": "err", "msg": "비밀번호가 틀렸습니다"}))
            await ws.close(4001, "auth failed")
            print(f"[{ip}] 비밀번호 틀림")
            return
        self.fails.pop(ip, None)
        mons = list_monitors(self.test)
        await ws.send(json.dumps({"t": "ok", "monitors": mons, "name": socket.gethostname()}))
        print(f"[{ip}] 연결됨")
        self.active += 1
        wi.keep_awake(True)
        conn = Connection(self, ws, mons)
        try:
            await conn.run()
        finally:
            self.active -= 1
            if self.active == 0:
                wi.keep_awake(False)
            print(f"[{ip}] 연결 끊김")


class Connection:
    def __init__(self, host, ws, mons):
        self.host, self.ws, self.mons = host, ws, mons
        self.stream = None
        self.stream_task = None
        self.cursor_task = None
        self.cfg = {}
        self.fps = 30
        self.down_buttons = set()
        self.down_keys = set()
        self.upload = None        # (파일 객체, 경로, 받은 바이트, 전체 크기)
        self.download_task = None

    async def run(self):
        try:
            async for raw in self.ws:
                if isinstance(raw, bytes):
                    await self.on_binary(raw)
                    continue
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                await self.on_message(msg)
        except Exception as e:
            if not type(e).__name__.startswith("ConnectionClosed"):
                print("연결 오류:", repr(e))
        finally:
            self.abort_upload()
            for t in (self.stream_task, self.cursor_task, self.download_task):
                if t:
                    t.cancel()
            if self.stream:
                self.stream.close()
            for b in list(self.down_buttons):  # 눌린 채로 끊기면 풀어줌
                wi.button(b, False)
            for vk in list(self.down_keys):
                wi.key(vk, False)

    def monitor(self):
        idx = int(self.cfg.get("mon", 0))
        return self.mons[idx if 0 <= idx < len(self.mons) else 0]

    async def on_message(self, m):
        t = m.get("t")
        if t in ("start", "cfg"):
            self.cfg.update({k: v for k, v in m.items() if k != "t"})
            self.fps = max(1, min(int(self.cfg.get("fps", 30)), 60))
            if self.stream is None:
                self.stream = Stream(self.host.test)
                self.stream_task = asyncio.create_task(self.stream_loop())
                self.cursor_task = asyncio.create_task(self.cursor_loop())
            self.stream.configure(dict(self.cfg))
        elif t == "kf":
            if self.stream:
                self.stream.want_key = True
        elif t == "ping":
            await self.ws.send(json.dumps({"t": "pong", "ts": m.get("ts")}))
        elif t == "mm":  # 절대 위치 (0~1, 현재 모니터 기준)
            mon = self.monitor()
            wi.move_abs(mon["left"] + float(m["x"]) * mon["width"], mon["top"] + float(m["y"]) * mon["height"])
        elif t == "mr":  # 상대 이동 (PC 픽셀)
            wi.move_rel(int(round(m.get("dx", 0))), int(round(m.get("dy", 0))))
        elif t == "mb":
            b, d = m.get("b", "left"), bool(m.get("d"))
            (self.down_buttons.add if d else self.down_buttons.discard)(b)
            wi.button(b, d)
        elif t == "click":
            b = m.get("b", "left")
            for _ in range(int(m.get("n", 1))):
                wi.button(b, True)
                wi.button(b, False)
        elif t == "wh":
            wi.wheel(int(m.get("dy", 0)), int(m.get("dx", 0)))
        elif t == "key":
            vk, d = int(m["vk"]), bool(m.get("d"))
            (self.down_keys.add if d else self.down_keys.discard)(vk)
            wi.key(vk, d)
        elif t == "combo":  # 여러 키를 차례로 누르고 거꾸로 뗌 (예: Ctrl+C)
            vks = [int(v) for v in m.get("vks", [])]
            for v in vks:
                wi.key(v, True)
            for v in reversed(vks):
                wi.key(v, False)
        elif t == "text":
            wi.text(str(m.get("s", "")))
        elif t == "clip_set":
            wi.clipboard_set(str(m.get("s", "")))
        elif t == "clip_get":
            await self.ws.send(json.dumps({"t": "clip", "s": wi.clipboard_get()}))
        # ---- 파일: PC 폴더 보기 / 받기 (PC → 휴대폰)
        elif t == "ls":
            try:
                res = await asyncio.get_running_loop().run_in_executor(None, list_dir, m.get("path") or "")
            except OSError as e:
                res = {"t": "ls", "path": m.get("path"), "error": f"열 수 없습니다: {e.strerror or e}"}
            await self.ws.send(json.dumps(res, ensure_ascii=False))
        elif t == "fget":
            if self.download_task and not self.download_task.done():
                self.download_task.cancel()
            self.download_task = asyncio.create_task(self.send_file(str(m.get("path", ""))))
        elif t == "fget_cancel":
            if self.download_task:
                self.download_task.cancel()
        # ---- 파일: 휴대폰 → PC
        elif t == "fput":
            self.abort_upload()
            path = unique_path(receive_dir(), safe_name(m.get("name", "file")))
            try:
                self.upload = [open(path, "wb"), path, 0, int(m.get("size", 0))]
            except OSError as e:
                await self.ws.send(json.dumps({"t": "fput_err", "msg": str(e)}))
        elif t == "fput_end":
            if self.upload:
                f, path, got, _ = self.upload
                f.close()
                self.upload = None
                print(f"파일 받음: {path} ({got:,} 바이트)")
                await self.ws.send(json.dumps({"t": "fput_ok", "path": path, "size": got}, ensure_ascii=False))
        elif t == "fput_cancel":
            self.abort_upload()

    async def on_binary(self, raw):
        if raw[:1] == bytes([PKT_UPLOAD]) and self.upload:
            f = self.upload[0]
            await asyncio.get_running_loop().run_in_executor(None, f.write, raw[1:])
            self.upload[2] += len(raw) - 1

    def abort_upload(self):
        if self.upload:
            f, path, _, _ = self.upload
            self.upload = None
            try:
                f.close()
                os.remove(path)
            except OSError:
                pass

    async def send_file(self, path):
        loop = asyncio.get_running_loop()
        try:
            f = open(path, "rb")
        except OSError as e:
            await self.ws.send(json.dumps({"t": "fget_err", "msg": f"열 수 없습니다: {e.strerror or e}"}, ensure_ascii=False))
            return
        try:
            size = os.fstat(f.fileno()).st_size
            await self.ws.send(json.dumps({"t": "fget_start", "name": os.path.basename(path), "size": size},
                                          ensure_ascii=False))
            while True:
                chunk = await loop.run_in_executor(None, f.read, FILE_CHUNK)
                if not chunk:
                    break
                await self.ws.send(bytes([PKT_FILE, 0]) + chunk)
            await self.ws.send(json.dumps({"t": "fget_end"}))
        except asyncio.CancelledError:
            try:
                await self.ws.send(json.dumps({"t": "fget_err", "msg": "취소했습니다"}, ensure_ascii=False))
            except Exception:
                pass
            raise
        finally:
            f.close()

    async def stream_loop(self):
        loop = asyncio.get_running_loop()
        while True:
            t0 = time.monotonic()
            try:
                info, data = await loop.run_in_executor(self.stream.pool, self.stream.produce)
            except Exception as e:
                print("캡처 오류:", repr(e))
                await asyncio.sleep(1)
                continue
            if info:
                await self.ws.send(json.dumps(info))
            if data:
                await self.ws.send(data)  # 네트워크가 느리면 여기서 기다리므로 자연스럽게 프레임 수가 줄어듦
            delay = 1 / self.fps - (time.monotonic() - t0)
            await asyncio.sleep(max(delay, 0.001))

    async def cursor_loop(self):
        last = None
        while True:
            await asyncio.sleep(1 / 60)
            mon = self.monitor()
            x, y = wi.cursor_pos()
            nx = (x - mon["left"]) / mon["width"]
            ny = (y - mon["top"]) / mon["height"]
            cur = (round(nx, 4), round(ny, 4))
            if cur != last:
                last = cur
                await self.ws.send(json.dumps({"t": "cur", "x": cur[0], "y": cur[1]}))


# ---------------------------------------------------------------- 같은 와이파이에서 찾기 (UDP)
class Discovery(asyncio.DatagramProtocol):
    def __init__(self, port):
        self.port = port

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if data.strip() == DISCOVER_MAGIC:
            reply = json.dumps({"name": socket.gethostname(), "port": self.port, "ver": VERSION})
            self.transport.sendto(reply.encode("utf-8"), addr)


def local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


async def main_async(args, key):
    from websockets.asyncio.server import serve
    host = Host(key, test=args.test)
    loop = asyncio.get_running_loop()
    try:
        await loop.create_datagram_endpoint(lambda: Discovery(args.port), local_addr=("0.0.0.0", DISCOVERY_PORT),
                                            allow_broadcast=True)
    except OSError as e:
        print("LAN 검색 기능을 켜지 못했습니다:", e)
    async with serve(host.handler, args.bind, args.port, max_size=2 ** 20, compression=None,
                     ping_interval=10, ping_timeout=20) as server:
        print(f"\nSisico Remote 호스트 실행 중  (포트 {args.port})")
        for ip in local_ips():
            print(f"  휴대폰 앱에 입력할 주소: {ip}")
        print("  끝내려면 이 창을 닫거나 Ctrl+C\n")
        await server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="Sisico Remote 호스트")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--set-password", action="store_true")
    ap.add_argument("--password", help="비밀번호를 명령줄로 지정 (자동 실행용)")
    ap.add_argument("--test", action="store_true", help="실제 화면 대신 시험 무늬를 보냄")
    args = ap.parse_args()

    wi.set_dpi_aware()
    cfg = load_config()
    if args.password:
        cfg["key"] = password_key(args.password)
        save_config(cfg)
    elif args.set_password or "key" not in cfg:
        ask_password(cfg)
    if args.port:
        cfg["port"] = args.port
        save_config(cfg)
    args.port = int(cfg.get("port", DEFAULT_PORT))
    try:
        asyncio.run(main_async(args, cfg["key"]))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("")  # 콘솔 색/유니코드 출력 활성화
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
