# Sisico 원격 (안드로이드 → 윈도우)

휴대폰으로 집/회사 윈도우 PC 화면을 보고 마우스·키보드로 조작하는 **개인용** 원격 프로그램입니다.
회원가입·중계 서버 없이 PC와 휴대폰이 직접 연결됩니다.

| 위치 | 내용 |
|---|---|
| `host/` | 윈도우 PC에서 실행하는 호스트 (Python → `sisico_remote_host.exe`) |
| `android/` | 휴대폰 앱 (Kotlin, `sisico-remote.apk`) |

`remote/` 를 고쳐서 푸시하면 GitHub Actions(`.github/workflows/remote.yml`)가 APK와 exe를 빌드해
**Releases → "Sisico 원격 (최신 빌드)"** (`remote-latest` 태그)에 올립니다.

## 설치

**PC**
1. 릴리스에서 `sisico_remote_host.exe` 를 받아 아무 폴더에 둡니다.
2. 실행하면 접속 비밀번호(6자 이상)를 정하라고 합니다. 설정은 `%APPDATA%\SisicoRemote\config.json` 에 저장됩니다 (비밀번호 자체가 아니라 SHA-256 값).
3. 윈도우 방화벽 창이 뜨면 **개인 네트워크 허용**을 누릅니다.
4. 창에 나오는 `휴대폰 앱에 입력할 주소` 를 확인합니다.
   - 관리자 권한으로 실행해야 관리자 권한 창(작업 관리자 등)도 조작됩니다.
   - 윈도우 시작 시 자동 실행: `Win+R` → `shell:startup` → exe 바로 가기를 넣습니다.
   - 비밀번호 변경 `--set-password`, 포트 변경 `--port 9000`

**휴대폰**
1. 릴리스에서 `sisico-remote.apk` 를 받아 설치합니다.
2. 같은 와이파이면 **와이파이에서 찾기**, 아니면 **+ PC 추가**에 주소·비밀번호를 넣습니다.

**밖에서(LTE/다른 와이파이) 접속하려면**: PC와 휴대폰 모두에 [Tailscale](https://tailscale.com)을 설치해 같은 계정으로 로그인하고,
PC의 `100.x.x.x` 주소를 앱에 넣으세요. 공유기 포트포워딩으로 8765 포트를 인터넷에 여는 것은 권하지 않습니다 (아래 보안 참고).

## 조작법

**트랙패드 모드** (기본, 노트북 터치패드처럼)
- 한 손가락 이동: 커서 이동 (빠르게 움직이면 더 멀리)
- 탭: 왼쪽 클릭 · 두 번 탭: 더블클릭
- 두 번 탭 후 끌기, 또는 길게 누른 뒤 끌기: 드래그
- 두 손가락 탭: 오른쪽 클릭 · 두 손가락 끌기: 스크롤
- 두 손가락 벌리기/오므리기: 화면 확대·축소 (확대 중엔 커서를 화면이 따라감)

**터치 모드**: 누른 곳 클릭, 길게 누르면 오른쪽 클릭, 끌면 드래그. 두 손가락 동작은 같음.

**☰ 메뉴**: 키보드 · 모드 전환 · 단축키(Alt+Tab, Win+D, 작업 관리자, 복사/붙여넣기, 볼륨 등) · 모니터 선택 · 화질 · 파일 · 클립보드 주고받기 · 원래 크기 · 끊기
- 키보드: 입력란에 친 글자가 PC로 바로 들어갑니다 (한글은 글자가 완성되면 전송). Ctrl/Alt/Shift/Win 을 켠 뒤 다른 키를 누르면 조합키가 됩니다. 방향키, F1~F12, 한/영 키 포함.
- 파일:
  - **휴대폰 → PC**: 파일을 여러 개 골라 보내면 PC의 `다운로드\Sisico 원격` 폴더에 저장됩니다.
  - **PC 파일 받기**: 바탕 화면·다운로드·문서·드라이브부터 PC 폴더를 둘러보고, 파일을 누르면 휴대폰 `다운로드/Sisico 원격` 에 저장됩니다 (안드로이드 9 이하는 앱 전용 다운로드 폴더).
- 블루투스/USB 키보드를 휴대폰에 연결하면 키가 그대로 PC로 갑니다.
- 화질: H.264(기본, 데이터 적음) / JPEG(호환용), 해상도 720~원본, 15/30/60fps, 비트레이트 2~16Mbps, 트랙패드 속도

## 구조

```
[휴대폰 앱]  ── WebSocket (ws://PC:8765) ──  [PC 호스트]
 TextureView ← MediaCodec(H.264 하드웨어 디코딩)   ← libx264 (ultrafast, zerolatency) ← mss 화면 캡처
 터치 → 마우스/키 JSON 메시지                        → SendInput (마우스·키보드·유니코드 입력)
 같은 와이파이 찾기: UDP 8766 브로드캐스트
```

- 인증: 접속하면 PC가 무작위 nonce 를 보내고, 앱이 `HMAC-SHA256(sha256(비밀번호), nonce)` 로 답합니다. 비밀번호는 네트워크로 나가지 않습니다. 5번 틀린 IP는 5분간 막힙니다.
- 화면이 그대로면 프레임을 보내지 않고, 네트워크가 느리면 전송이 끝날 때까지 다음 캡처를 미뤄 지연이 쌓이지 않게 합니다.
- 마우스 커서는 영상에 그리지 않고 좌표만 따로 60Hz 로 보내 앱에서 그립니다 (영상보다 빠르게 반응).

### 메시지 (앱 → PC, JSON 텍스트)
`start`/`cfg` {codec, mon, fps, maxw, kbps, q} · `kf`(키프레임 요청) · `ping`{ts} · `mm`{x,y: 0~1 절대 위치} · `mr`{dx,dy: 픽셀 상대 이동} ·
`mb`{b, d} · `click`{b} · `wh`{dy,dx} · `key`{vk, d} · `combo`{vks:[..]} · `text`{s} · `clip_set`{s} · `clip_get` ·
`ls`{path: 빈 값이면 처음 목록} · `fget`{path} · `fget_cancel` · `fput`{name,size} → 바이너리 `[0x10][조각]` 반복 → `fput_end` · `fput_cancel`

### 메시지 (PC → 앱)
텍스트: `hello`{nonce} · `ok`{monitors} · `err` · `stream`{codec,w,h,mw,mh} · `cur`{x,y} · `pong`{ts} · `clip`{s} · `ls`{path,parent,items} · `fget_start`{name,size} · `fget_end` · `fget_err` · `fput_ok`{path} · `fput_err`
바이너리: `[종류 1=H.264, 2=JPEG, 3=파일 조각][플래그 bit0=키프레임][데이터]`

## 보안

- 연결 자체는 암호화되지 않습니다 (인증만 안전함). 화면과 입력 내용은 같은 네트워크에 있는 사람이 볼 수 있으므로,
  공용 와이파이나 인터넷 너머에서는 반드시 **Tailscale**(WireGuard 암호화) 같은 VPN 을 통해 접속하세요.
- 비밀번호는 길게 정하세요. 호스트 창을 닫으면 원격 접속이 완전히 꺼집니다.

## 하지 못하는 것

- 윈도우 잠금 화면·UAC 확인 창(보안 데스크톱)은 캡처/조작되지 않습니다 (서비스로 동작하는 상용 앱만 가능). Ctrl+Alt+Del, Win+L 도 보낼 수 없습니다.
- 소리 전송은 아직 없습니다. 파일 전송 중에는 화면이 잠깐 느려질 수 있습니다 (같은 연결을 나눠 씀).

## 직접 실행 / 빌드

```bash
# 호스트 (윈도우, Python 3.10+)
cd remote/host
pip install -r requirements.txt
python sisico_remote_host.py            # --test 를 붙이면 실제 화면 대신 시험 무늬
python smoke_test.py <비밀번호>          # 다른 창에서: 접속·H.264 수신·파일 전송 확인

# 앱 (Android SDK 필요)
cd remote/android
./gradlew testDebugUnitTest assembleDebug
```

## 참고: StarDesk 1.6.1 APK 분석에서 가져온 아이디어

사용 중인 StarDesk 앱을 열어 본 결과(코드 복사 없이 구조만 참고):
- WebRTC(`org.webrtc`) 피어 연결 + DataChannel 위에 protobuf 메시지(`com.remote.proto.*`: `MultiTouchEvent`, `ClipboardTextChangeReq`, `CaptureSetting`, `FileTransfer*`, `CursorShapeNotify` 등)
- 영상 H.264/H.265, 안드로이드 `MediaCodec` + `SurfaceView` 하드웨어 디코딩, 기기별 디코더 예외 목록(`streamer-config.json`)
- 조작: 트랙패드형 제스처(드래그·스크롤·확대 애니메이션), 윈도우/맥 전체 키보드 배열, 가상 게임패드, 단축키, 다중 모니터, 클립보드, 파일 전송, 원격 터미널
- 계정·클라우드 중계 서버·광고/분석 SDK(Firebase, AppsFlyer, Sentry, 결제)

이 프로그램은 개인용이라 계정/중계 서버/광고를 빼고, WebRTC 대신 단순한 WebSocket + H.264 로 같은 핵심 흐름
(하드웨어 디코딩, 트랙패드 제스처, 커서 따로 전송, 다중 모니터, 클립보드, 조합키)을 구현했습니다.
NAT 너머 연결은 직접 중계 서버를 두는 대신 Tailscale 에 맡깁니다.
