"""페이지 공통: 색상·데이터 로더."""
import streamlit as st
import pandas as pd
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TODAY_YEAR = pd.Timestamp.today().year


HEAT_COLORS = {
    "개별난방":        [74,  158, 255, 220],
    "지역난방":        [62,  207, 142, 220],
    "중앙난방(가스)":  [255, 107,  74, 220],
    "중앙난방(기름)":  [255, 180,  50, 220],
    "열병합(Co-gen)":  [236,  72, 153, 220],
    "CES(집단에너지)": [168,  85, 247, 220],
    "신서(집단에너지)":[20,  184, 166, 220],
    "기타":            [148, 163, 184, 220],
}
HEAT_HEX = {
    "개별난방":        "#4a9eff",
    "지역난방":        "#3ecf8e",
    "중앙난방(가스)":  "#ff6b4a",
    "중앙난방(기름)":  "#ffb432",
    "열병합(Co-gen)":  "#ec4899",
    "CES(집단에너지)": "#a855f7",
    "신서(집단에너지)":"#14b8a6",
    "기타":            "#94a3b8",
}
DEFAULT_COLOR = [148, 163, 184, 200]

def get_color(heat_type):
    if pd.isna(heat_type):
        return DEFAULT_COLOR
    return HEAT_COLORS.get(str(heat_type).strip(), DEFAULT_COLOR)

# 공급승인연도 구간 (색상·통계용)
# 1983-01-01 = 전산화 이전 공급분 일괄등록일 (실제 승인일 아님)
BULK_DATE  = pd.Timestamp("1983-01-01")
ERA_BINS   = [0, 2000, 2010, 2020, 9999]
ERA_LABELS = ["~2000", "2001~2010", "2011~2020", "2021~"]
ERA_ORDER  = ["1983 일괄등록"] + ERA_LABELS + ["미상"]
ERA_COLORS = {
    "1983 일괄등록": [100, 116, 139, 200],
    "~2000":     [234,  88,  12, 220],
    "2001~2010": [250, 204,  21, 220],
    "2011~2020": [ 34, 197,  94, 220],
    "2021~":     [ 59, 130, 246, 220],
    "미상":      [148, 163, 184, 160],
}
ERA_HEX = {k: "#%02x%02x%02x" % tuple(v[:3]) for k, v in ERA_COLORS.items()}

@st.cache_data
def load_data():
    # 전처리는 update_data.py 에서 끝남 — 여기선 읽기만
    df = pd.read_csv(DATA_DIR / "output" / "공동주택_지도.csv",
                     encoding="utf-8-sig", dtype={"아파트코드": str, "우편번호": str})
    df["공급승인일자"] = pd.to_datetime(df["공급승인일자"], errors="coerce")
    df["공급승인연도"] = df["공급승인일자"].dt.year.astype("Int64")
    df["승인연도구간"] = (pd.cut(df["공급승인연도"].astype(float), ERA_BINS, labels=ERA_LABELS)
                          .astype(str).replace("nan", "미상"))
    df.loc[df["공급승인일자"] == BULK_DATE, "승인연도구간"] = "1983 일괄등록"
    df["공급승인일자_표시"] = df["공급승인일자"].dt.strftime("%Y-%m-%d").fillna("-")
    # K-apt 사용승인일(실제 준공) — 주소 매칭, 공동주택 일부만 있음
    if "사용승인일" not in df.columns:
        df["사용승인일"] = None
    df["사용승인일"] = pd.to_datetime(df["사용승인일"], errors="coerce")
    df["준공연도"] = df["사용승인일"].dt.year.astype("Int64")
    df["경과연수"] = (TODAY_YEAR - df["준공연도"]).astype("Int64")
    df["사용승인일_표시"] = df["사용승인일"].dt.strftime("%Y-%m-%d").fillna("-")
    for c in ["K-apt단지명", "K-apt난방방식", "관리사무소전화", "K-apt매칭"]:
        if c not in df.columns:
            df[c] = None
    df["K-apt난방방식_표시"] = df["K-apt난방방식"].fillna("-")
    df["heat_color"] = df["난방구분"].apply(get_color)
    df["era_color"]  = df["승인연도구간"].map(ERA_COLORS)
    return df

@st.cache_data
def load_geojson():
    path = DATA_DIR / "ref" / "고시지역.geojson"
    with open(path, encoding='utf-8') as f:
        return json.load(f)
