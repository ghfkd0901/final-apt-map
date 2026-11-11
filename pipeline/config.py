"""경로·컬럼 설정 — 경로를 바꿀 일이 있으면 이 파일만 고치면 됩니다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 입력
RAW_FILE     = DATA / "raw" / "공동주택현황.csv"       # 고객지원시스템에서 받은 원본 (덮어쓰기)
GOSI_GEOJSON = DATA / "ref" / "고시지역.geojson"

# 캐시 (지오코딩 결과 누적 — 지우면 전체 재지오코딩)
COORD_CACHE = DATA / "cache" / "좌표캐시.csv"

# 출력
OUTPUT_FILE   = DATA / "output" / "공동주택_지도.csv"     # 앱이 읽는 파일
GEOCODE_FAILS = DATA / "output" / "지오코딩실패.csv"     # 확인용

# 단지 식별 키
KEY = ["아파트코드", "아파트명"]

# 원본에서 버리는 컬럼
DROP_COLS = ["공동주택계약", "설치위치"]

# 공급승인일자 컬럼 후보 (원본 컬럼명이 바뀌어도 대응)
APPROVAL_COL_CANDIDATES = ["공급승인일자", "공급승인일", "공급승인년월일"]

# 경상북도 시군구 (그 외는 대구광역시)
GYEONGBUK_SGG = {"경산시", "고령군", "칠곡군"}
