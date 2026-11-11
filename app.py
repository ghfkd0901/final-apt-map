import streamlit as st
import pandas as pd
import pydeck as pdk
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(
    page_title="대성에너지 아파트 지도",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    df["heat_color"] = df["난방구분"].apply(get_color)
    df["era_color"]  = df["승인연도구간"].map(ERA_COLORS)
    return df

@st.cache_data
def load_geojson():
    path = DATA_DIR / "ref" / "고시지역.geojson"
    with open(path, encoding='utf-8') as f:
        return json.load(f)

df_all  = load_data()
geojson = load_geojson()

st.title("🏢 대성에너지 공동주택 지도")
st.caption(f"총 {len(df_all):,}개 아파트 · WebGL 고성능 렌더링")
st.divider()

with st.sidebar:
    st.header("🔍 검색")
    search_apt  = st.text_input("아파트명", placeholder="예: 래미안, 힐스테이트...")
    search_addr = st.text_input("도로명주소", placeholder="예: 달서구 와룡로...")

    st.header("🎛️ 필터")

    sido_opts = sorted(df_all['시도명'].dropna().unique().tolist())
    sel_sido  = st.multiselect("시도", sido_opts)

    sgg_base = df_all[df_all['시도명'].isin(sel_sido)] if sel_sido else df_all
    sgg_opts = sorted(sgg_base['시군구명'].dropna().unique().tolist())
    sel_sgg  = st.multiselect("시군구", sgg_opts)

    adm_base = df_all[df_all['시군구명'].isin(sel_sgg)] if sel_sgg else sgg_base
    adm_opts = sorted(adm_base['읍면동명'].dropna().unique().tolist()) if '읍면동명' in df_all.columns else []
    sel_adm  = st.multiselect("읍면동", adm_opts)

    heat_opts = sorted(df_all['난방구분'].dropna().unique().tolist())
    sel_heat  = st.multiselect("난방방식", heat_opts)

    yong_opts = sorted(df_all['용도'].dropna().unique().tolist())
    sel_yong  = st.multiselect("용도", yong_opts)

    # ── 업종 (자체업종분류 → 자체업종명 캐스케이드) ─────────
    if '자체업종분류' in df_all.columns:
        upjong_cls_opts = sorted(df_all['자체업종분류'].dropna().unique().tolist())
        sel_upjong_cls  = st.multiselect("자체업종분류", upjong_cls_opts)
    else:
        sel_upjong_cls = []

    if '자체업종명' in df_all.columns:
        upj_base    = df_all[df_all['자체업종분류'].isin(sel_upjong_cls)] if sel_upjong_cls else df_all
        upjong_opts = sorted(upj_base['자체업종명'].dropna().unique().tolist())
        sel_upjong  = st.multiselect("자체업종명", upjong_opts)
    else:
        sel_upjong = []

    svc_opts = sorted(df_all['고객센터'].dropna().unique().tolist())
    sel_svc  = st.multiselect("고객센터", svc_opts)

    st.subheader("📌 고시지역")
    sel_gosi_yn = st.multiselect("고시여부", ["예", "아니오"])
    gosi_nm_opts = sorted(df_all['고시지역명'].dropna().unique().tolist())
    sel_gosi_nm  = st.multiselect("고시지역명", gosi_nm_opts)

    st.subheader("📅 공급승인연도")
    yr = df_all.loc[df_all["승인연도구간"] != "1983 일괄등록", "공급승인연도"].dropna()
    if len(yr):
        sel_year = st.slider("연도 범위", int(yr.min()), int(yr.max()),
                             (int(yr.min()), int(yr.max())))
        include_no_date = st.checkbox("1983 일괄등록·미상 단지 포함", value=True,
                                      help="1983-01-01은 전산화 이전 공급분의 일괄등록일로, 실제 승인일이 아닙니다.")
    else:
        sel_year, include_no_date = None, True
        st.caption("데이터에 공급승인일자가 없습니다.")

    st.subheader("🏠 세대수")
    hoga_min = int(df_all['세대수'].min())
    hoga_max = int(df_all['세대수'].max())

    col_min, col_max = st.columns(2)
    with col_min:
        input_min = st.number_input("최솟값", min_value=hoga_min, max_value=hoga_max,
                                     value=hoga_min, step=1)
    with col_max:
        input_max = st.number_input("최댓값", min_value=hoga_min, max_value=hoga_max,
                                     value=hoga_max, step=1)

    if input_min > input_max:
        st.warning("최솟값이 최댓값보다 클 수 없습니다.")
        input_min, input_max = input_max, input_min

    sel_hoga = (input_min, input_max)

    st.header("🗺️ 지도 옵션")
    marker_radius   = st.slider("마커 크기", 30, 200, 80)
    show_geojson    = st.toggle("고시지역 표시", value=True)
    geojson_opacity = st.slider("고시지역 투명도", 0.0, 1.0, 0.25, step=0.05,
                                disabled=not show_geojson)
    map_style = st.selectbox("배경지도", ["다크", "라이트", "일반"], index=2)
    STYLE_MAP = {
        "다크":  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        "라이트": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        "일반":  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    }

    color_by = st.radio("마커 색상 기준", ["난방방식", "공급승인연도"], horizontal=True)
    legend = HEAT_HEX if color_by == "난방방식" else ERA_HEX

    st.header("🎨 범례")
    for label, color in legend.items():
        st.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
            f'background:{color};margin-right:8px;vertical-align:middle;"></span>{label}',
            unsafe_allow_html=True
        )

# ── 필터링 ───────────────────────────────────────────────────────
df = df_all.copy()
if search_apt:       df = df[df['아파트명'].str.contains(search_apt, na=False, case=False, regex=False)]
if search_addr:      df = df[df['도로명주소'].str.contains(search_addr, na=False, case=False, regex=False)]
if sel_sido:         df = df[df['시도명'].isin(sel_sido)]
if sel_sgg:          df = df[df['시군구명'].isin(sel_sgg)]
if sel_adm:          df = df[df['읍면동명'].isin(sel_adm)]
if sel_heat:         df = df[df['난방구분'].isin(sel_heat)]
if sel_yong:         df = df[df['용도'].isin(sel_yong)]
if sel_upjong_cls:   df = df[df['자체업종분류'].isin(sel_upjong_cls)]
if sel_upjong:       df = df[df['자체업종명'].isin(sel_upjong)]
if sel_svc:          df = df[df['고객센터'].isin(sel_svc)]
if sel_gosi_yn:      df = df[df['고시여부'].isin(sel_gosi_yn)]
if sel_gosi_nm:      df = df[df['고시지역명'].isin(sel_gosi_nm)]
df = df[df['세대수'].between(sel_hoga[0], sel_hoga[1])]
if sel_year:
    no_date  = df['승인연도구간'].isin(["1983 일괄등록", "미상"])
    in_range = df['공급승인연도'].between(*sel_year).fillna(False).astype(bool) & ~no_date
    df = df[in_range | (no_date & include_no_date)]
df = df.reset_index(drop=True)
df['color'] = df['heat_color'] if color_by == "난방방식" else df['era_color']

# ── 메트릭 카드 (난방방식별 아파트수 + 세대수) ──────────────────
heat_summary = (
    df.groupby('난방구분', dropna=False)['세대수']
      .agg(아파트수='count', 세대수합계='sum')
      .reset_index()
      .sort_values('세대수합계', ascending=False)
)
heat_summary['난방구분'] = heat_summary['난방구분'].fillna('기타')

total_cols = st.columns(2)
total_cols[0].metric("🏢 전체 아파트", f"{len(df):,}개")
total_cols[1].metric("👥 전체 세대수", f"{df['세대수'].sum():,}세대")

st.markdown("")  # 간격

if len(heat_summary) > 0:
    heat_cols = st.columns(len(heat_summary))
    for i, (_, row) in enumerate(heat_summary.iterrows()):
        label   = str(row['난방구분'])
        dot_hex = HEAT_HEX.get(label, "#94a3b8")
        heat_cols[i].markdown(
            f'<div style="text-align:center;">'
            f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
            f'background:{dot_hex};margin-right:4px;vertical-align:middle;"></span>'
            f'<b style="font-size:13px;">{label}</b></div>'
            f'<div style="text-align:center;font-size:20px;font-weight:700;">{row["아파트수"]:,}개</div>'
            f'<div style="text-align:center;color:#888;font-size:12px;">{row["세대수합계"]:,}세대</div>',
            unsafe_allow_html=True
        )

st.divider()

if len(df) == 0:
    st.warning("조건에 맞는 아파트가 없습니다.")
    st.stop()

# ── 레이어 구성 ──────────────────────────────────────────────────
layers = []

if show_geojson:
    layers.append(pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        stroked=True,
        filled=True,
        get_fill_color=[255, 165, 0, int(geojson_opacity * 255)],
        get_line_color=[255, 140, 0, 220],
        line_width_min_pixels=1,
        get_line_width=30,
        pickable=False,
    ))

layers.append(pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position='[경도, 위도]',
    get_fill_color='color',
    get_radius=marker_radius,
    radius_min_pixels=3,
    radius_max_pixels=18,
    pickable=True,
    auto_highlight=True,
    highlight_color=[255, 255, 255, 80],
))

tooltip = {
    "html": "<b>{아파트명}</b><br>난방: {난방구분} · {세대수}세대<br>공급승인: {공급승인일자_표시}<br>업종: {자체업종분류} · {자체업종명}<br>고시: {고시여부} {고시지역명}<br>{도로명주소}",
    "style": {
        "backgroundColor": "#0f1923",
        "color": "#e8f4ff",
        "fontSize": "13px",
        "padding": "10px",
        "borderRadius": "6px",
        "border": "1px solid #2a3f55",
    },
}

st.pydeck_chart(
    pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=df['위도'].mean(),
            longitude=df['경도'].mean(),
            zoom=11, pitch=0,
        ),
        tooltip=tooltip,
        map_style=STYLE_MAP[map_style],
    ),
    width="stretch",
    height=520,
)

st.divider()

# ── 목록 & 상세 ──────────────────────────────────────────────────
st.subheader(f"📋 목록 ({len(df):,}건)")
st.caption("행을 클릭하면 아래에 상세정보가 표시됩니다.")

DISPLAY_COLS = ['아파트명', '아파트코드', '난방구분', '자체업종분류', '자체업종명', '고시여부', '고시지역명',
                '세대수', '공급승인일자_표시', '용도', '고객센터', '시군구명', '읍면동명', '도로명주소']
display_cols = [c for c in DISPLAY_COLS if c in df.columns]

event = st.dataframe(
    df[display_cols],
    width="stretch",
    hide_index=True,
    height=350,
    column_config={"공급승인일자_표시": "공급승인일자"},
    on_select="rerun",
    selection_mode="single-row",
)

selected_rows = event.selection.get("rows", []) if event and event.selection else []

if selected_rows:
    row = df.iloc[selected_rows[0]]
    st.divider()
    st.subheader(f"🏢 {row.get('아파트명', '-')}")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.metric("아파트코드", row.get('아파트코드', '-'))
        st.metric("세대수", f"{row.get('세대수', '-')}세대")
        st.metric("공급승인일자", row.get('공급승인일자_표시', '-'))
    with d2:
        st.metric("난방구분", row.get('난방구분', '-'))
        st.metric("용도", row.get('용도', '-'))
        st.metric("자체업종명", row.get('자체업종명', '-') or '-')
    with d3:
        st.metric("고시여부", row.get('고시여부', '-'))
        st.metric("고시지역명", row.get('고시지역명', '-') or '-')
        st.metric("자체업종분류", row.get('자체업종분류', '-') or '-')
    st.markdown(f"**📍 주소** : {row.get('도로명주소', '-')}")
    st.markdown(f"**🌐 위치** : 위도 `{row.get('위도', '-')}` · 경도 `{row.get('경도', '-')}`")
    st.markdown(f"**🗺️ 행정구역** : {row.get('시도명', '')} {row.get('시군구명', '')} {row.get('읍면동명', '')}")
    st.markdown(f"**🏢 고객센터** : {row.get('고객센터', '-')}")

st.divider()

# ── 통계 탭 ─────────────────────────────────────────────────────
st.subheader("📊 통계")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["난방방식별", "시군구별", "고시지역별", "업종별", "공급승인연도별"])

with tab1:
    g1 = df.groupby('난방구분')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g1 = g1.sort_values('세대수합계', ascending=False)
    g1['아파트수'] = g1['아파트수'].map('{:,}'.format)
    g1['세대수합계'] = g1['세대수합계'].map('{:,}'.format)
    g1.columns = ['난방방식', '아파트수', '세대수 합계']
    st.dataframe(g1, width="stretch", hide_index=True)

with tab2:
    g2 = df.groupby('시군구명')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g2 = g2.sort_values('세대수합계', ascending=False)
    g2['아파트수'] = g2['아파트수'].map('{:,}'.format)
    g2['세대수합계'] = g2['세대수합계'].map('{:,}'.format)
    g2.columns = ['시군구', '아파트수', '세대수 합계']
    st.dataframe(g2, width="stretch", hide_index=True)

with tab3:
    g3 = df.groupby('고시여부')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g3_nm = df[df['고시여부']=='예'].groupby('고시지역명')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g3.columns = ['구분', '아파트수', '세대수 합계']
    g3_nm.columns = ['구분', '아파트수', '세대수 합계']
    combined = pd.concat([g3, g3_nm], ignore_index=True)
    combined['아파트수'] = combined['아파트수'].map('{:,}'.format)
    combined['세대수 합계'] = combined['세대수 합계'].map('{:,}'.format)
    st.dataframe(combined, width="stretch", hide_index=True)

with tab4:
    if '자체업종분류' in df.columns:
        g4 = df.groupby('자체업종분류')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
        g4 = g4.sort_values('세대수합계', ascending=False)
        g4['아파트수'] = g4['아파트수'].map('{:,}'.format)
        g4['세대수합계'] = g4['세대수합계'].map('{:,}'.format)
        g4.columns = ['자체업종분류', '아파트수', '세대수 합계']
        st.dataframe(g4, width="stretch", hide_index=True)
    else:
        st.info("자체업종분류 컬럼이 데이터에 없습니다.")

with tab5:
    g5 = (df.groupby('승인연도구간')['세대수'].agg(아파트수='count', 세대수합계='sum')
            .reindex(ERA_ORDER).dropna().astype(int).reset_index())
    g5.columns = ['공급승인연도', '아파트수', '세대수 합계']
    st.dataframe(g5, width="stretch", hide_index=True)
    st.bar_chart(df[~df['승인연도구간'].isin(['1983 일괄등록', '미상'])].groupby('공급승인연도')['세대수'].sum(),
                 y_label="세대수")
