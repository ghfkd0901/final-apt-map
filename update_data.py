"""데이터 갱신 — 원본 CSV를 data/raw/공동주택현황.csv 에 덮어쓴 뒤 실행:

    python update_data.py

원본 → 정제 → 좌표(캐시+신규 지오코딩) → 단지 단위 집계 → 고시지역 → data/output/공동주택_지도.csv
"""
from pipeline import config
from pipeline.clean import add_region, aggregate, load_raw
from pipeline.geocode import attach_coords
from pipeline.gosi import attach_gosi

COLS = ["아파트명", "아파트코드", "세대수", "난방구분", "용도", "자체업종분류", "자체업종명",
        "고객센터", "공급승인일자", "우편번호", "도로명주소", "시도명", "시군구명", "읍면동명",
        "위도", "경도", "고시여부", "고시지역명"]


def main():
    print("1) 원본 로드")
    df = load_raw()
    print(f"   {len(df):,}행")

    print("2) 좌표 연결")
    df = attach_coords(df)
    df = df.dropna(subset=["위도", "경도"])

    print("3) 단지 단위 집계 · 시군구 · 고시지역")
    df = aggregate(df)
    df = add_region(df)
    df = attach_gosi(df)

    df["공급승인일자"] = df["공급승인일자"].dt.strftime("%Y-%m-%d")
    out = df[[c for c in COLS if c in df.columns]].sort_values(["시군구명", "아파트명"])
    config.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(config.OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n✅ {config.OUTPUT_FILE.relative_to(config.ROOT)} — {len(out):,}개 단지")
    print(f"   공급승인일자 있음 {out['공급승인일자'].notna().sum():,}개 | "
          f"고시지역 내 {(out['고시여부'] == '예').sum():,}개")


if __name__ == "__main__":
    main()
