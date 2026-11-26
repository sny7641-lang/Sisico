"""호스트가 켜진 상태에서 접속·인증·H.264 수신·입력 처리를 확인합니다.  python smoke_test.py <비밀번호> [주소]"""
import asyncio
import json
import os
import ssl
import sys
import time

import av
from websockets.asyncio.client import connect

from remote_proto import derive_key, fingerprint, short_fp


def tls():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   # 자체 서명 인증서 → 지문으로 확인
    return ctx


async def wrong_password(addr):
    async with connect(f"wss://{addr}:8765", ssl=tls()) as ws:
        h = json.loads(await ws.recv())
        await ws.send(json.dumps({"t": "auth", "k": derive_key("wrong-password", h["salt"], h["iter"]).hex()}))
        r = json.loads(await ws.recv())
        assert r["t"] == "err", r
        print("wrong password rejected")


async def main(pw, addr):
    await wrong_password(addr)
    async with connect(f"wss://{addr}:8765", max_size=2 ** 22, ssl=tls()) as ws:
        der = ws.transport.get_extra_info("ssl_object").getpeercert(binary_form=True)
        print("TLS", ws.transport.get_extra_info("ssl_object").version(), "fingerprint", short_fp(fingerprint(der)))
        hello = json.loads(await ws.recv())
        await ws.send(json.dumps({"t": "auth", "k": derive_key(pw, hello["salt"], hello["iter"]).hex()}))
        ok = json.loads(await ws.recv())
        assert ok["t"] == "ok", ok
        print("monitors:", ok["monitors"])
        await ws.send(json.dumps({"t": "start", "codec": "h264", "mon": 0, "fps": 30, "maxw": 1280, "kbps": 4000}))
        await ws.send(json.dumps({"t": "ping", "ts": 1}))
        dec = av.CodecContext.create("h264", "r")
        frames, t0, pong = 0, time.time(), False
        while time.time() - t0 < 4:
            m = await ws.recv()
            if isinstance(m, bytes):
                if m[0] == 1:
                    frames += len(dec.decode(av.Packet(m[2:])))
            elif json.loads(m)["t"] == "pong":
                pong = True
        print(f"decoded frames in 4s: {frames}, pong: {pong}")
        assert frames >= 20 and pong

        # 파일 전송: 올리기 → 같은 파일 내려받기
        async def text_msg(kinds):
            while True:
                m = await ws.recv()
                if isinstance(m, str) and json.loads(m)["t"] in kinds:
                    return json.loads(m)
        await ws.send(json.dumps({"t": "ls", "path": ""}))
        root = await text_msg({"ls"})
        print("PC folders:", [i["name"] for i in root["items"]])
        assert root["items"]
        data = os.urandom(700_000)
        await ws.send(json.dumps({"t": "fput", "name": "smoke 테스트.bin", "size": len(data)}))
        for i in range(0, len(data), 256 * 1024):
            await ws.send(bytes([0x10]) + data[i:i + 256 * 1024])
        await ws.send(json.dumps({"t": "fput_end"}))
        ok = await text_msg({"fput_ok", "fput_err"})
        assert ok["t"] == "fput_ok", ok
        await ws.send(json.dumps({"t": "fget", "path": ok["path"]}))
        await text_msg({"fget_start"})
        got = b""
        while True:
            m = await ws.recv()
            if isinstance(m, bytes) and m[0] == 3:
                got += m[2:]
            elif isinstance(m, str) and json.loads(m)["t"] in ("fget_end", "fget_err"):
                break
        os.remove(ok["path"])
        print("file round trip:", got == data)
        assert got == data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"))
