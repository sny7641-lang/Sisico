"""호스트와 PC용 조작 프로그램이 같이 쓰는 상수와 함수."""
import hashlib

VERSION = 2
DEFAULT_PORT = 8765
DISCOVERY_PORT = 8766
DISCOVER_MAGIC = b"SISICO_REMOTE_DISCOVER"
PBKDF2_ITER = 200_000

PKT_H264, PKT_JPEG, PKT_FILE = 1, 2, 3   # PC → 조작 기기
PKT_UPLOAD = 0x10                        # 조작 기기 → PC 파일 조각
FLAG_KEY = 1
FILE_CHUNK = 256 * 1024


def derive_key(password: str, salt_hex: str, iterations: int = PBKDF2_ITER) -> bytes:
    """비밀번호 → 접속 키. PC마다 다른 salt 를 쓰므로 같은 비밀번호라도 PC마다 키가 다릅니다."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)


def verifier(key: bytes) -> str:
    """PC 설정 파일에는 키가 아니라 키의 해시만 저장 (파일을 훔쳐도 접속 불가)."""
    return hashlib.sha256(b"sisico-remote-verifier" + key).hexdigest()


def fingerprint(cert_der: bytes) -> str:
    return hashlib.sha256(cert_der).hexdigest()


def short_fp(fp_hex: str) -> str:
    """사람이 눈으로 비교할 지문: 앞 16자리를 4자리씩."""
    s = fp_hex[:16].upper()
    return "-".join(s[i:i + 4] for i in range(0, 16, 4))
