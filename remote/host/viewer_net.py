"""PC용 조작 프로그램의 네트워크 부분 (화면 없이도 동작 → 자동 테스트에 사용).

Session 은 별도 스레드에서 asyncio 로 PC 호스트에 붙어:
  - 인증서 지문을 확인한 뒤에만 접속 키를 보냄 (다르면 바로 끊음)
  - H.264 를 풀어 '가장 최근 화면' 하나만 보관 (밀리면 오래된 화면은 버림)
  - 클립보드/파일/연결 상태 같은 일은 events 큐로 알려 줌
"""
import asyncio
import io
import json
import os
import queue
import ssl
import threading
import time

from remote_proto import (DEFAULT_PORT, FILE_CHUNK, PKT_H264, PKT_JPEG, PKT_UPLOAD, derive_key, fingerprint,
                          short_fp)


def client_tls():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # 자체 서명 인증서 → 아래에서 지문으로 직접 확인
    return ctx


def url_for(address, port):
    a = address.strip()
    if ":" in a and not a.startswith("["):
        a = f"[{a}]"
    return f"wss://{a}:{int(port or DEFAULT_PORT)}/"


def peer_fingerprint_async(ws):
    return fingerprint(ws.transport.get_extra_info("ssl_object").getpeercert(binary_form=True))


class PairError(Exception):
    pass


def pair(address, port, password, confirm, timeout=10):
    """PC 등록. confirm(지문짧은형, PC이름) 이 True 를 돌려줘야 키를 보냅니다.
    성공하면 {"key": hex, "pin": 지문, "name": PC이름} 반환, 실패하면 PairError."""
    from websockets.sync.client import connect
    try:
        ws = connect(url_for(address, port), ssl=client_tls(), open_timeout=timeout, max_size=2 ** 22)
    except Exception as e:
        raise PairError(f"연결할 수 없습니다: {e}\n\nPC 프로그램이 켜져 있는지, 주소·포트가 맞는지 확인하세요.")
    with ws:
        pin = fingerprint(ws.socket.getpeercert(binary_form=True))
        hello = json.loads(ws.recv(timeout))
        if hello.get("t") != "hello" or "salt" not in hello:
            raise PairError("PC 프로그램이 예전 버전입니다. 최신 sisico_remote_host.exe 로 바꿔 주세요.")
        if not confirm(short_fp(pin), hello.get("name", "")):
            raise PairError("등록을 취소했습니다.")
        key = derive_key(password, hello["salt"], int(hello["iter"]))
        ws.send(json.dumps({"t": "auth", "k": key.hex()}))
        try:
            while True:
                r = json.loads(ws.recv(timeout))
                if r.get("t") == "ok":
                    return {"key": key.hex(), "pin": pin, "name": hello.get("name", "")}
                if r.get("t") == "err":
                    raise PairError("비밀번호가 틀렸습니다.")
        except PairError:
            raise
        except Exception:
            raise PairError("비밀번호가 틀렸거나 PC가 연결을 끊었습니다.")


class Session:
    def __init__(self, host, settings):
        self.host = host
        self.settings = settings
        self.events = queue.Queue()      # (종류, 값)
        self.lock = threading.Lock()
        self.frame = None                # (bytes RGB, w, h)
        self.frame_seq = 0
        self.target = (1280, 720)        # 화면 창에 그릴 크기 (메인 스레드가 정함)
        self.stream_info = None
        self.monitors = []
        self.mon = 0
        self.decoded = 0
        self.bytes_in = 0
        self.loop = None
        self.ws = None
        self.closed = False
        self.decoder = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    # ---------------------------------------------------------------- 메인 스레드에서 쓰는 것
    def start(self):
        self._thread.start()

    def send(self, msg):
        if self.loop and self.ws and not self.closed:
            data = json.dumps(msg, ensure_ascii=False)
            asyncio.run_coroutine_threadsafe(self._send(data), self.loop)

    def send_file(self, path):
        if self.loop and self.ws:
            asyncio.run_coroutine_threadsafe(self._upload(path), self.loop)

    def start_message(self, t="start"):
        s = self.settings
        self.send({"t": t, "codec": "h264", "mon": self.mon, "fps": s.get("fps", 60),
                   "maxw": s.get("maxw", 0), "kbps": s.get("kbps", 12000), "q": 80})

    def close(self):
        self.closed = True
        if self.loop and self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

    def take_frame(self, last_seq):
        with self.lock:
            if self.frame_seq == last_seq or self.frame is None:
                return None, last_seq
            return self.frame, self.frame_seq

    # ---------------------------------------------------------------- 네트워크 스레드
    async def _send(self, data):
        try:
            await self.ws.send(data)
        except Exception:
            pass

    def _run(self):
        self.loop = asyncio.new_event_loop()
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            self.events.put(("closed", f"연결 오류: {e}"))
        finally:
            self.loop.close()

    async def _main(self):
        from websockets.asyncio.client import connect
        h = self.host
        try:
            ws = await asyncio.wait_for(connect(url_for(h["address"], h["port"]), ssl=client_tls(),
                                                max_size=2 ** 22, compression=None, ping_interval=10,
                                                ping_timeout=20), 10)
        except Exception as e:
            self.events.put(("closed", f"연결할 수 없습니다: {e}"))
            return
        try:
            fp = peer_fingerprint_async(ws)
            if fp != h["pin"]:
                self.events.put(("closed", "보안 경고: 이 주소의 PC 인증서가 등록할 때와 다릅니다.\n"
                                           "다른 기기가 내 PC인 척하고 있을 수 있어 연결하지 않았습니다.\n"
                                           f"(받은 지문 {short_fp(fp)})\n"
                                           "PC 프로그램을 새로 설치했다면 목록에서 '수정'으로 다시 등록하세요."))
                await ws.close()
                return
            hello = json.loads(await ws.recv())
            await ws.send(json.dumps({"t": "auth", "k": h["key"]}))
            ok = json.loads(await ws.recv())
            if ok.get("t") != "ok":
                self.events.put(("closed", "비밀번호가 바뀌었습니다. 목록에서 '수정'으로 다시 등록하세요."))
                return
            self.ws = ws
            self.monitors = ok.get("monitors", [])
            self.events.put(("authed", ok.get("name") or hello.get("name", "")))
            self.start_message()
            await ws.send(json.dumps({"t": "clip_watch"}))
            async for m in ws:
                if isinstance(m, bytes):
                    self.bytes_in += len(m)
                    await self._on_binary(m)
                else:
                    self._on_text(json.loads(m))
            self.events.put(("closed", "PC가 연결을 끊었습니다."))
        except Exception as e:
            if not self.closed:
                self.events.put(("closed", f"연결이 끊겼습니다: {type(e).__name__}"))
        finally:
            self.ws = None
            try:
                await ws.close()
            except Exception:
                pass

    def _on_text(self, m):
        t = m.get("t")
        if t == "stream":
            self.stream_info = m
            self._new_decoder()
            self.events.put(("stream", m))
        elif t == "clip":
            self.events.put(("clip", m.get("s", "")))
        elif t == "notice":
            self.events.put(("notice", m.get("msg", "")))
        elif t in ("fput_ok", "fput_err"):
            self.events.put((t, m.get("path") or m.get("msg", "")))

    def _new_decoder(self):
        import av
        ctx = av.CodecContext.create("h264", "r")
        try:
            ctx.thread_type = "SLICE"   # 프레임 단위 스레드는 지연이 생기므로 사용 안 함
        except Exception:
            pass
        try:
            ctx.options = {"flags": "low_delay"}
        except Exception:
            pass
        self.decoder = ctx

    async def _on_binary(self, m):
        kind = m[0]
        if kind == PKT_H264 and self.decoder is not None:
            frames = await self.loop.run_in_executor(None, self._decode_h264, m[2:])
        elif kind == PKT_JPEG:
            frames = await self.loop.run_in_executor(None, self._decode_jpeg, m[2:])
        else:
            return
        if frames:
            with self.lock:
                self.frame = frames
                self.frame_seq += 1

    def _decode_h264(self, data):
        import av
        out = None
        try:
            for f in self.decoder.decode(av.Packet(data)):
                tw, th = self.target
                out = (f.reformat(width=tw, height=th, format="rgb24").to_ndarray().tobytes(), tw, th)
                self.decoded += 1
        except Exception:
            self.send({"t": "kf"})   # 깨진 프레임 → 새 키프레임 요청
        return out

    def _decode_jpeg(self, data):
        from PIL import Image
        tw, th = self.target
        img = Image.open(io.BytesIO(data)).convert("RGB").resize((tw, th))
        self.decoded += 1
        return img.tobytes(), tw, th

    async def _upload(self, path):
        name = os.path.basename(path)
        try:
            size = os.path.getsize(path)
            await self.ws.send(json.dumps({"t": "fput", "name": name, "size": size}, ensure_ascii=False))
            sent, last = 0, 0.0
            with open(path, "rb") as f:
                while True:
                    chunk = await self.loop.run_in_executor(None, f.read, FILE_CHUNK)
                    if not chunk:
                        break
                    await self.ws.send(bytes([PKT_UPLOAD]) + chunk)
                    sent += len(chunk)
                    if time.monotonic() - last > 0.3:
                        last = time.monotonic()
                        self.events.put(("progress", (name, sent, size)))
            await self.ws.send(json.dumps({"t": "fput_end"}))
        except Exception as e:
            self.events.put(("fput_err", f"{name}: {e}"))


def selftest(address, password, port=DEFAULT_PORT):
    """화면 없이 등록 → 접속 → 화면 받기 → 파일 보내기까지 확인 (자동 테스트용). 성공하면 0."""
    info = pair(address, port, password, confirm=lambda fp, name: print("fingerprint", fp, name) or True)
    print("paired:", info["name"])
    try:
        pair(address, port, password + "x", confirm=lambda *a: True)
        print("FAIL: wrong password accepted")
        return 1
    except PairError as e:
        print("wrong password rejected:", e)
    host = {"address": address, "port": port, "key": info["key"], "pin": info["pin"]}
    s = Session(host, {"fps": 30, "maxw": 1280, "kbps": 4000})
    s.target = (640, 360)
    s.start()
    t0, seq, frames, sent_file, uploaded = time.time(), 0, 0, False, False
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest_upload.bin")
    while time.time() - t0 < 8:
        f, seq2 = s.take_frame(seq)
        if f:
            frames += 1
            seq = seq2
            assert len(f[0]) == 640 * 360 * 3
        if frames >= 10 and not sent_file:
            with open(tmp, "wb") as fh:
                fh.write(os.urandom(300_000))
            s.send_file(tmp)
            sent_file = True
        try:
            kind, val = s.events.get(timeout=0.02)
            if kind == "closed":
                print("closed:", val)
                return 1
            if kind == "fput_ok":
                uploaded = True
                os.remove(val)
        except queue.Empty:
            pass
        if uploaded and frames >= 20:
            break
    s.close()
    try:
        os.remove(tmp)
    except OSError:
        pass
    # 지문이 다르면 거부되는지
    bad = Session(dict(host, pin="00" * 32), {})
    bad.start()
    kind, val = bad.events.get(timeout=10)
    print(f"frames shown: {frames}, decoded: {s.decoded}, upload: {uploaded}, wrong pin -> {kind}")
    return 0 if frames >= 20 and uploaded and kind == "closed" and "보안 경고" in val else 1
