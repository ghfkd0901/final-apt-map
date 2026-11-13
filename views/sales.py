"""영업대상 — 개별난방이 아니고 지역난방 고시지역 밖인 오래된 단지."""
import io

import pandas as pd
import pydeck as pdk
import streamlit as st

from common import HEAT_COLORS, HEAT_HEX, load_data, load_geojson

GIS_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"


def heat_check(row):
    """당사 난방구분과 K-apt 난방방식이 어긋나면 표시 (예: 개별난방 전환 의심)."""
    k, a = row["K-apt난방방식"], row["난방구분"]
    if pd.isna(k):
        return ""
    same = (k == "중앙난방" and (a.startswith("중앙") or a.startswith("열병합"))) or \
           (k == "지역난방" and ("지역" in a or "집단" in a)) or \
           (k == "개별난방" and a == "개별난방")
    return "" if same else f"K-apt: {k}"


df_all = load_data()
# ── 선정 기준 (고정) ─────────────────────────────────────────
base = df_all[(df_all["난방구분"] != "개별난방") & (df_all["고시여부"] != "예")].copy()
base["난방확인"] = base.apply(heat_check, axis=1)

st.title("🎯 영업대상")
st.info(
    f"**선정 기준** — 전체 {len(df_all):,}개 단지 중 아래 두 조건을 모두 만족하는 **{len(base):,}개 단지 "
    f"({base['세대수'].sum():,}세대)**\n\n"
    "1. 난방구분이 **개별난방이 아님** — 대성에너지는 개별난방(세대별 가스보일러)만 공급하므로, "
    "지역난방·중앙난방·집단에너지·열병합 등 나머지는 모두 **개별난방 전환 영업 대상**\n"
    "2. **지역난방 고시지역 밖** — 고시지역 안은 지역난방 공급지역으로 지정되어 있어 제외\n\n"
    "이 안에서 왼쪽 필터로 좁혀 볼 수 있습니다. 목록은 준공(사용승인)이 오래된 순입니다."
)

with st.expander("선정 기준 내 난방구분별 현황", expanded=False):
    g = (base.groupby("난방구분")
             .agg(단지수=("아파트명", "size"), 세대수=("세대수", "sum"),
                  사용승인일확인=("사용승인일", "count"))
             .sort_values("세대수", ascending=False).reset_index())
    st.dataframe(g, hide_index=True, width="stretch")

# ── 필터 (기준 안에서 좁히기) ─────────────────────────────────
with st.sidebar:
    st.header("🎛️ 필터")
    st.caption("선정 기준(개별난방 아님 · 고시지역 밖) 안에서 좁히기")

    heat_opts = base["난방구분"].value_counts().index.tolist()
    sel_heat = st.multiselect("난방구분", heat_opts, default=heat_opts)

    yong_opts = base["용도"].value_counts().index.tolist()
    sel_yong = st.multiselect("용도", yong_opts, default=yong_opts)

    sgg_opts = sorted(base["시군구명"].dropna().unique())
    sel_sgg = st.multiselect("시군구", sgg_opts)

    svc_opts = sorted(base["고객센터"].dropna().unique())
    sel_svc = st.multiselect("고객센터", svc_opts)

    st.subheader("🏗️ 준공(사용승인) 연도")
    yr = base["준공연도"].dropna()
    sel_year = st.slider("연도 범위", int(yr.min()), int(yr.max()), (int(yr.min()), int(yr.max())))
    incl_unknown = st.checkbox("사용승인일 없는 단지 포함", value=True,
                               help="K-apt에 없는 단지(소규모·비주거 등)이거나 아직 조회 전인 단지")

    st.subheader("🏠 세대수")
    min_hh = st.number_input("최소 세대수", min_value=0, value=0, step=50)

    only_flag = st.checkbox("난방확인 대상만 (K-apt 난방방식과 다른 단지)", value=False)
    search = st.text_input("아파트명 검색")

df = base[base["난방구분"].isin(sel_heat) & base["용도"].isin(sel_yong)]
if sel_sgg:
    df = df[df["시군구명"].isin(sel_sgg)]
if sel_svc:
    df = df[df["고객센터"].isin(sel_svc)]
known = df["준공연도"].notna()
in_year = df["준공연도"].between(*sel_year).fillna(False).astype(bool)
df = df[in_year | (~known & incl_unknown)]
df = df[df["세대수"] >= min_hh]
if only_flag:
    df = df[df["난방확인"] != ""]
if search:
    df = df[df["아파트명"].str.contains(search, na=False, regex=False) |
            df["K-apt단지명"].fillna("").str.contains(search, regex=False)]
df = df.sort_values(["사용승인일", "공급승인일자", "세대수"], ascending=[True, True, False],
                    na_position="last").reset_index(drop=True)

# ── 요약 ─────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("단지", f"{len(df):,}개")
c2.metric("세대수", f"{df['세대수'].sum():,}세대")
c3.metric("사용승인일 확인", f"{df['사용승인일'].notna().sum():,}개")
avg = df["경과연수"].dropna()
c4.metric("평균 경과연수", f"{avg.mean():.0f}년" if len(avg) else "-")

n_flag = (df["난방확인"] != "").sum()
if n_flag:
    st.warning(f"당사 난방구분과 K-apt 난방방식이 다른 단지 {n_flag}곳 — '난방확인' 컬럼 참고 "
               "(예: 개별난방으로 전환했을 수 있음)")

if df.empty:
    st.info("조건에 맞는 단지가 없습니다.")
    st.stop()

# ── 지도 ─────────────────────────────────────────────────────
mdf = df.dropna(subset=["위도", "경도"]).copy()
mdf["color"] = mdf["난방구분"].map(HEAT_COLORS).apply(lambda c: c if isinstance(c, list) else [148, 163, 184, 220])
mdf["경과"] = mdf["경과연수"].astype(str).replace("<NA>", "-")
st.pydeck_chart(pdk.Deck(
    layers=[pdk.Layer("GeoJsonLayer", data=load_geojson(), stroked=True, filled=True,
                      get_fill_color=[255, 165, 0, 60], get_line_color=[255, 140, 0, 220],
                      line_width_min_pixels=1, pickable=False),
            pdk.Layer("ScatterplotLayer", data=mdf, get_position="[경도, 위도]", get_fill_color="color",
                      get_radius=120, radius_min_pixels=4, radius_max_pixels=20, pickable=True)],
    initial_view_state=pdk.ViewState(latitude=mdf["위도"].mean(), longitude=mdf["경도"].mean(), zoom=10.5),
    tooltip={"html": "<b>{아파트명}</b><br>{난방구분} · {세대수}세대<br>"
                     "준공 {사용승인일_표시} (경과 {경과}년)<br>{도로명주소}"},
    map_style=GIS_STYLE,
), height=420)
st.caption("  ".join(f"● {k}" for k in sel_heat if k in HEAT_HEX) + "  ·  주황 영역: 지역난방 고시지역(제외 대상)")

# ── 목록 ─────────────────────────────────────────────────────
COLS = {"아파트명": "아파트명", "K-apt단지명": "K-apt 단지명", "시군구명": "시군구", "도로명주소": "도로명주소",
        "난방구분": "난방구분", "K-apt난방방식": "K-apt 난방", "난방확인": "난방확인", "세대수": "세대수",
        "사용승인일": "사용승인일(준공)", "경과연수": "경과연수", "공급승인일자": "공급승인일자",
        "관리사무소전화": "관리사무소", "고객센터": "고객센터", "K-apt매칭": "매칭방법"}
out = df[list(COLS)].rename(columns=COLS)

st.subheader(f"📋 목록 ({len(out):,}건)")
st.dataframe(
    out, hide_index=True, width="stretch", height=480,
    column_config={
        "사용승인일(준공)": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "공급승인일자": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "세대수": st.column_config.NumberColumn(format="%d"),
    },
)

buf = io.BytesIO()
xl = out.copy()
for c in ("사용승인일(준공)", "공급승인일자"):
    xl[c] = xl[c].dt.date
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    xl.to_excel(w, index=False, sheet_name="영업대상")
    ws = w.sheets["영업대상"]
    for col, width in zip("ABCDEFGHIJKLMN", [24, 22, 8, 28, 14, 10, 14, 8, 13, 8, 13, 14, 22, 14]):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
st.download_button("⬇️ 엑셀 다운로드", buf.getvalue(), file_name="영업대상.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with st.expander("ℹ️ 데이터 기준"):
    st.markdown(
        "- **사용승인일**: 국토교통부 공동주택 기본정보(K-apt). 단지코드·이름이 달라 **도로명주소 → 지번** 순으로 매칭하고, "
        "세대수 또는 단지명이 비슷한 경우만 인정합니다.\n"
        "- K-apt는 의무관리대상(대략 150세대 이상·중앙난방 100세대 이상 등)만 있어 소규모 단지·비주거는 빈 값입니다.\n"
        "- **공급승인일자**: 고객지원시스템 원본. 1983-01-01은 전산화 이전 공급분 일괄등록일입니다.\n"
        "- **경과연수**: 올해 − 준공연도")
