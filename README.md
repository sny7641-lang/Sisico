# Sisico 단어장

카드로 외우고, 퀴즈로 확인하는 영어 단어 공부 앱 (스마트폰용).

- **플래시카드**: 간격 반복(1·2·4·7·15일)으로 오늘 복습할 단어만 보여줍니다.
- **퀴즈**: 뜻 고르기(4지선다) / 철자 쓰기.
- **기본 단어장**: 기초 필수(206), 중학 필수(216), 일상 회화(153), 수능 필수(214), 토익 빈출(194) — 모든 단어에 예문 포함, 골라서 추가하고 공부 범위로 선택.
- **단어장**: 단어 추가·검색·삭제, `단어, 뜻` 형식으로 여러 줄 붙여넣기.
- 발음 듣기, 연속 학습일, 다크 모드. 데이터는 기기 안에 저장됩니다.

## 안드로이드 앱(APK) 설치

1. 이 저장소의 **Releases → "Sisico 단어장 (최신 빌드)"** 에서 `sisico-vocab.apk` 를 휴대폰으로 내려받습니다.
2. 파일을 열고, "출처를 알 수 없는 앱 설치"를 허용하면 설치됩니다.

`www/` 를 고쳐서 푸시하면 GitHub Actions(`.github/workflows/android.yml`)가 APK를 다시 빌드해 같은 릴리스에 올립니다.
같은 서명 키(`assets/debug.keystore`)로 빌드하므로 새 APK를 덮어 설치해도 단어가 유지됩니다.

## 직접 빌드

```bash
npm ci
npx cap add android
npm run android:icons
npx cap sync android
cd android && ./gradlew assembleDebug   # Android SDK 필요
```

## 아이폰

`www/` 폴더를 HTTPS로 호스팅(예: GitHub Pages)한 뒤 Safari에서 열고 **공유 → 홈 화면에 추가** 하면 앱처럼 쓸 수 있습니다 (PWA, 오프라인 지원).
