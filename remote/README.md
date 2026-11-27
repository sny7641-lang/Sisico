# Sisico 원격

휴대폰이나 다른 PC로 윈도우 PC 화면을 보면서 마우스·키보드로 조작하는 **개인용** 원격 프로그램입니다.
회원가입이나 중계 서버 없이 기기끼리 직접 연결하고, 연결은 모두 암호화됩니다.

| 프로그램 | 역할 | 위치 |
|---|---|---|
| `sisico_remote_host.exe` | **조작당할 PC**에서 실행 (화면 보내기, 입력 받기) | `host/sisico_remote_host.py` |
| `sisico-remote.apk` | **휴대폰**으로 조작 | `android/` |
| `sisico_remote_viewer.exe` | **다른 PC**로 조작 | `host/sisico_remote_viewer.py` |

`remote/` 를 고쳐서 푸시하면 GitHub Actions(`.github/workflows/remote.yml`)가 세 파일을 빌드하고 자동 시험한 뒤
**Releases → "Sisico 원격 (최신 빌드)"** (`remote-latest` 태그)에 올립니다.

## 설치

**조작당할 PC**
1. `sisico_remote_host.exe` 를 받아 아무 폴더(예: `C:\SisicoRemote`)에 두고 실행합니다.
2. 처음 실행하면 **비밀번호 설정 창**이 뜹니다. 8자 이상으로 정하고, **Windows 시작 시 자동 실행**은 켜 둡니다.
3. 윈도우 방화벽 창이 뜨면 허용을 누릅니다 (Tailscale 로 밖에서 쓸 거면 **공용**도 체크).
4. 이후에는 창 없이 **작업 표시줄 오른쪽 아래 아이콘**으로만 실행됩니다 (`^` 를 눌러야 보일 수 있음).
   아이콘을 누르면 **주소**와 **지문**(`75AD-E8DB-6101-EB15` 같은 모양)이 나옵니다.
   - 오른쪽 클릭 메뉴: 연결 정보 보기 · 비밀번호 바꾸기 · 잠금 화면·로그인 전에도 접속 · Tailscale 로만 접속 허용 · Windows 시작 시 자동 실행 · 설정·로그 폴더 열기 · 종료
   - 누가 접속하거나 틀린 비밀번호로 시도하면 윈도우 알림이 뜹니다.
   - 관리자 권한으로 실행해야 관리자 권한 창(작업 관리자 등)도 조작됩니다.
   - 포트 변경 `--port 9000`, 아이콘 없이 콘솔로 실행 `--no-tray`

**휴대폰**: `sisico-remote.apk` 설치 → **와이파이에서 찾기** 또는 **+ PC 추가**

**다른 PC**: `sisico_remote_viewer.exe` 실행 → **와이파이에서 찾기** 또는 **추가**

PC를 등록하면 앱이 PC에 접속해 **지문**을 보여 줍니다. PC 창에 나온 지문과 같을 때만 **같아요**를 누르세요.
그다음 비밀번호가 맞는지 확인하고 저장합니다.

**밖(LTE·다른 와이파이)에서 접속하려면**: 양쪽 기기에 [Tailscale](https://tailscale.com)을 설치해 같은 계정으로
로그인하고, PC의 `100.x.x.x` 주소로 등록하세요. 공유기 포트포워딩은 권하지 않습니다.

## 휴대폰 조작법

**트랙패드 모드** (기본, 노트북 터치패드처럼)
- 한 손가락 이동: 커서 이동 (빠르게 움직이면 더 멀리)
- 탭: 왼쪽 클릭 · 두 번 탭: 더블클릭
- 두 번 탭 후 끌기, 또는 길게 누른 뒤 끌기: 드래그
- 두 손가락 탭: 오른쪽 클릭 · 두 손가락 끌기: 스크롤
- 두 손가락 벌리기/오므리기: 화면 확대·축소 (확대 중엔 커서를 화면이 따라감)

**터치 모드**: 누른 곳 클릭, 길게 누르면 오른쪽 클릭, 끌면 드래그. 두 손가락 동작은 같음.

**☰ 메뉴**: 키보드 · 모드 전환 · 단축키 · 모니터 번호(🖥 1, 🖥 2 …, 지금 보는 모니터는 색이 다름) · 화질 · 파일 · 클립보드 · 원래 크기 · 끊기
- 키보드: 입력란에 친 글자가 PC로 바로 들어갑니다 (한글은 글자가 완성되면 전송). Ctrl/Alt/Shift/Win 을 켠 뒤 다른 키를 누르면 조합키가 됩니다.
- 파일: **휴대폰 → PC** (PC의 `다운로드\Sisico 원격`), **PC 파일 받기** (PC 폴더를 둘러보고 휴대폰 `다운로드/Sisico 원격` 에 저장)
- 블루투스/USB 키보드를 휴대폰에 연결하면 키가 그대로 PC로 갑니다.

## PC에서 조작 (sisico_remote_viewer.exe)

목록에서 PC를 두 번 누르면 원격 화면 창이 열립니다. 여러 PC를 동시에 열 수 있습니다.
- 마우스·키보드가 그대로 상대 PC로 갑니다. **Alt+Tab, Win 키**도 전달됩니다 (키보드 잡기).
- 한글: **오른쪽 Alt = 한/영**, **오른쪽 Ctrl = 한자** (상대 PC의 한글 입력기가 처리). 목록 창에서 끌 수 있음.
- **복사한 글은 양쪽 PC가 자동으로 맞춰집니다.**
- **파일을 창에 끌어다 놓으면** 상대 PC의 `다운로드\Sisico 원격` 폴더로 보냅니다.
- 화질: 보통(1080p 30fps) / 좋음(원본 60fps, 기본) / 최고(원본 60fps 고비트레이트)

원격 화면 창 단축키 — **Ctrl + Alt + Shift** 를 누른 채로:

| 키 | 기능 |
|---|---|
| H | 도움말 |
| F | 전체 화면 켜기/끄기 |
| M | 다음 모니터 |
| G | 키보드 잡기 켜기/끄기 (끄면 Alt+Tab 이 내 PC에서 동작) |
| 1 / 2 / 3 | 화질 보통 / 좋음 / 최고 |
| Q | 연결 끊기 |

## 보안

- **암호화**: 모든 연결은 TLS(`wss://`, TLS 1.2 이상)입니다. 화면·입력·파일·클립보드 모두 암호화됩니다.
- **가짜 PC 차단**: PC는 처음 실행할 때 자기만의 인증서를 만들어 `%APPDATA%\SisicoRemote\` 에 둡니다.
  앱은 등록할 때 확인한 인증서 지문을 기억하고, 접속할 때마다 TLS 연결 단계에서 비교합니다. 다르면 비밀번호에서 나온 키를 보내기 전에 끊고 경고합니다.
- **비밀번호**: PC마다 다른 salt 로 PBKDF2-SHA256(20만 회)를 돌린 키로 로그인합니다. 비밀번호 자체는 어디에도 저장하지 않습니다.
  PC 설정 파일에는 그 키의 해시만 있어서, 설정 파일을 복사해 가도 접속할 수 없습니다.
- **틀린 비밀번호**: 5번 틀린 IP는 5분간 막힙니다.
- **Tailscale 로만 접속 허용** (트레이 메뉴): 켜면 Tailscale 주소(100.64.0.0/10)가 아닌 곳, 예를 들어 같은 와이파이에서 오는
  연결은 비밀번호를 묻기 전에 끊고(코드 4004), 와이파이 검색에도 답하지 않습니다. LTE 로만 쓸 때 권장.
- **앱 잠금** (휴대폰 앱 첫 화면, 기본 켜짐): PC에 접속할 때 휴대폰 잠금(지문·얼굴·PIN·패턴)으로 본인 확인.
  한 번 확인하면 5분간 다시 묻지 않고, 앱을 내렸다가 5분 넘어 돌아오면 다시 묻습니다. 끌 때도 본인 확인이 필요합니다.
- **조작 기기에 저장되는 것**: PC 주소, 지문, 접속 키. 휴대폰·조작 PC를 잃어버리면 PC 아이콘 메뉴의 **비밀번호 바꾸기**로 바꾸세요 (저장된 키가 모두 무효가 됨).
- PC 아이콘 메뉴에서 **종료**를 누르면 원격 접속이 완전히 꺼집니다.
- 남은 약점: 앱 서명 키(`assets/debug.keystore`)가 공개 저장소에 있어, 누군가 같은 서명으로 가짜 앱을 만들 수 있습니다. 이 저장소 릴리스 외의 APK는 설치하지 마세요.

이전 버전에서 바꾸는 경우: PC 프로그램이 비밀번호를 다시 정하라고 하고, 앱에서는 PC를 한 번 다시 등록해야 합니다.

## 하지 못하는 것

- 윈도우 잠금 화면·UAC 확인 창(보안 데스크톱)은 캡처/조작되지 않습니다. Ctrl+Alt+Del, Win+L 도 보낼 수 없습니다.
- 소리 전송은 없습니다. PC에서 조작할 때 PC → 내 PC 방향 파일 받기는 아직 없습니다 (휴대폰 앱에는 있음).

## 구조

```
[휴대폰 앱 / PC 조작 프로그램]  ── wss:// (TLS, 지문 고정) ──  [PC 호스트]
 MediaCodec / FFmpeg 로 H.264 디코딩      ← libx264 (ultrafast, zerolatency) ← mss 화면 캡처
 마우스·키 JSON 메시지                      → SendInput (마우스·키보드·유니코드)
 같은 와이파이 찾기: UDP 8766 브로드캐스트
```

- 화면이 그대로면 프레임을 보내지 않고, 네트워크가 느리면 전송이 끝날 때까지 다음 캡처를 미뤄 지연이 쌓이지 않게 합니다.
- 휴대폰 앱은 커서 위치를 따로 60Hz 로 받아 직접 그립니다 (영상보다 빠르게 반응).

### 접속 순서
1. TLS 연결 → 조작 기기가 인증서 지문을 확인 (다르면 끊음)
2. PC → `{"t":"hello","salt","iter","name","ver":2}`
3. 조작 기기 → `{"t":"auth","k": PBKDF2-SHA256(비밀번호, salt, iter) hex}` → PC는 `sha256("sisico-remote-verifier" + k)` 와 비교
4. PC → `{"t":"ok","monitors":[..]}` 또는 `err` 후 종료(4001)

### 메시지 (조작 기기 → PC, JSON 텍스트)
`start`/`cfg` {codec, mon, fps, maxw, kbps, q} · `kf`(키프레임 요청) · `ping`{ts} · `mm`{x,y: 0~1 절대 위치} · `mr`{dx,dy: 픽셀 상대 이동} ·
`mb`{b, d} · `click`{b} · `wh`{dy,dx} · `key`{vk, d} · `combo`{vks:[..]} · `text`{s} · `clip_set`{s} · `clip_get` · `clip_watch` ·
`ls`{path: 빈 값이면 처음 목록} · `fget`{path} · `fget_cancel` · `fput`{name,size} → 바이너리 `[0x10][조각]` 반복 → `fput_end` · `fput_cancel`

### 메시지 (PC → 조작 기기)
텍스트: `stream`{codec,w,h,mw,mh} · `cur`{x,y} · `pong`{ts} · `clip`{s} · `ls`{path,parent,items} · `fget_start`{name,size} · `fget_end` · `fget_err` · `fput_ok`{path} · `fput_err`
바이너리: `[종류 1=H.264, 2=JPEG, 3=파일 조각][플래그 bit0=키프레임][데이터]`

## 직접 실행 / 빌드

```bash
cd remote/host
pip install -r requirements.txt
python sisico_remote_host.py                    # --no-tray 콘솔 실행, --test 실제 화면 대신 시험 무늬
python smoke_test.py <비밀번호>                  # 다른 창에서: 암호화 접속·H.264·파일 전송 확인
python sisico_remote_viewer.py                  # PC용 조작 프로그램
python sisico_remote_viewer.py --selftest 127.0.0.1 <비밀번호>   # 화면 없이 등록·접속·파일 시험

cd ../android
./gradlew testDebugUnitTest assembleDebug       # Android SDK 필요
SISICO_TEST_HOST=127.0.0.1 ./gradlew testDebugUnitTest   # 켜 둔 호스트에 앱 연결 코드로 접속 시험
```

## 참고: StarDesk 1.6.1 APK 분석에서 가져온 아이디어

사용 중인 StarDesk 앱을 열어 본 결과(코드 복사 없이 구조만 참고):
- WebRTC(`org.webrtc`) 피어 연결 + DataChannel 위에 protobuf 메시지(`com.remote.proto.*`: `MultiTouchEvent`, `ClipboardTextChangeReq`, `CaptureSetting`, `FileTransfer*`, `CursorShapeNotify` 등)
- 영상 H.264/H.265, 안드로이드 `MediaCodec` + `SurfaceView` 하드웨어 디코딩, 기기별 디코더 예외 목록(`streamer-config.json`)
- 조작: 트랙패드형 제스처, 윈도우/맥 전체 키보드 배열, 가상 게임패드, 단축키, 다중 모니터, 클립보드, 파일 전송, 원격 터미널
- 계정·클라우드 중계 서버·광고/분석 SDK(Firebase, AppsFlyer, Sentry, 결제)

이 프로그램은 개인용이라 계정/중계 서버/광고를 빼고, WebRTC 대신 단순한 WebSocket(TLS) + H.264 로 같은 핵심 흐름을 구현했습니다.
NAT 너머 연결은 직접 중계 서버를 두는 대신 Tailscale 에 맡깁니다.
