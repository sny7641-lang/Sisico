# Sisico 단어장

카드로 외우고, 퀴즈로 확인하는 영어 단어 공부 앱 (스마트폰용).

- **플래시카드**: 간격 반복(1·2·4·7·15일)으로 오늘 복습할 단어만 보여줍니다.
- **퀴즈**: 뜻 고르기(4지선다) / 철자 쓰기.
- **기본 단어장 (총 4,457개 + 일상 회화 153개)**: 모든 단어에 한국어 뜻·예문 포함.
  - 교육과정 초등 필수 801 / 중·고 필수 1,200 / 고등 심화 1,000 — 교육부 2022 개정 영어과 교육과정 [별표 3] 기본 어휘
  - 수능 기출 빈출 1,574 — 2014~2026학년도 수능 영어 13개년 문제지·듣기 대본에서 3개 연도 이상 나온 단어 (초등 단어 제외)
  - 토익 빈출 1,250 — TOEIC Service List 1.2
  - 일상 회화 153 — 직접 정리
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

## 단어 데이터와 출처

| 파일 | 내용 | 출처·라이선스 |
|---|---|---|
| `data/sources/edu_2022_basic_vocab.tsv` | 교육과정 기본 어휘 3,000 (초등/중고/그 외 구분) | 교육부 2022 개정 영어과 교육과정 [별표 3], 한국교육과정평가원 KICE Word Lister 자료 |
| `data/sources/csat_2014_2026_counts.json` | 단어별 수능 출제 연도 수·빈도 | 한국교육과정평가원 공개 기출문제에서 `tools/count_csat.py`로 집계 (시험 원문은 저장하지 않음) |
| `data/sources/TSL_1.2_*.csv` | TOEIC Service List | Browne, C. & Culligan, B. — CC BY-SA 4.0 |
| `data/sources/NGSL_*`, `NAWL_*` | 단어 변화형 → 기본형 매핑 | NGSL Project — CC BY-SA 4.0 |
| `data/sources/tatoeba_eng_kor.tsv` | 영어–한국어 예문 쌍 | Tatoeba (manythings.org 정리본) — CC BY 2.0 FR |
| `data/dict/*.tsv` | 한국어 뜻, Tatoeba에 없는 단어의 예문 | 직접 작성 |

`python3 tools/build_decks.py` 를 실행하면 위 자료로 `www/decks.js` 를 다시 만듭니다.
