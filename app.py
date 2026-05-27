import streamlit as st
import pandas as pd
import pydeck as pdk
import json
from pathlib import Path

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

def get_hex(heat_type):
    if pd.isna(heat_type):
        return "#94a3b8"
    return HEAT_HEX.get(str(heat_type).strip(), "#94a3b8")

@st.cache_data
def load_data():
    path = Path(__file__).parent / "data" / "공동주택현황_최종.csv"
    for enc in ['utf-8-sig', 'cp949', 'euc-kr']:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except:
            continue

    # ── 불필요한 컬럼 제거 ──────────────────────────────────
    drop_cols = ['공동주택계약', '설치위치', 'Unnamed: 10']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    # ── 좌표 필터링 ─────────────────────────────────────────
    df = df.dropna(subset=['위도', '경도'])
    df = df[(df['위도'] > 33) & (df['위도'] < 39)]
    df = df[(df['경도'] > 124) & (df['경도'] < 132)]

    # ── 세대수 숫자 변환 ────────────────────────────────────
    df['세대수'] = pd.to_numeric(
        df['세대수'].astype(str).str.replace(',', '', regex=False),
        errors='coerce'
    ).fillna(0).astype(int)

    # ── 그룹화 (세대수 합산) ────────────────────────────────
    GROUP_KEYS = ['아파트명', '아파트코드', '도로명주소', '난방구분', '용도', '서비스센터']
    other_cols = [c for c in df.columns if c not in GROUP_KEYS and c != '세대수']
    agg_dict = {'세대수': 'sum', **{c: 'first' for c in other_cols}}

    df = (
        df.groupby(GROUP_KEYS, as_index=False, dropna=False)
          .agg(agg_dict)
    )

    # ── 마커 색상 ───────────────────────────────────────────
    df['color'] = df['난방구분'].apply(get_color)

    return df.reset_index(drop=True)

@st.cache_data
def load_geojson():
    path = Path(__file__).parent / "data" / "고시지역.geojson"
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
    adm_opts = sorted(adm_base['읍면동명'].dropna().unique().tolist())
    sel_adm  = st.multiselect("읍면동", adm_opts)

    heat_opts = sorted(df_all['난방구분'].dropna().unique().tolist())
    sel_heat  = st.multiselect("난방방식", heat_opts)

    yong_opts = sorted(df_all['용도'].dropna().unique().tolist())
    sel_yong  = st.multiselect("용도", yong_opts)

    svc_opts = sorted(df_all['서비스센터'].dropna().unique().tolist())
    sel_svc  = st.multiselect("서비스센터", svc_opts)

    st.subheader("📌 고시지역")
    sel_gosi_yn = st.multiselect("고시여부", ["예", "아니오"])
    gosi_nm_opts = sorted(df_all['고시지역명'].dropna().unique().tolist())
    sel_gosi_nm  = st.multiselect("고시지역명", gosi_nm_opts)

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
    map_style = st.selectbox("배경지도", ["다크", "라이트", "일반"])
    STYLE_MAP = {
        "다크":  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        "라이트": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        "일반":  "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    }

    st.header("🎨 난방방식 범례")
    for label, color in HEAT_HEX.items():
        st.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
            f'background:{color};margin-right:8px;vertical-align:middle;"></span>{label}',
            unsafe_allow_html=True
        )

# ── 필터링 ───────────────────────────────────────────────────────
df = df_all.copy()
if search_apt:   df = df[df['아파트명'].str.contains(search_apt, na=False, case=False, regex=False)]
if search_addr:  df = df[df['도로명주소'].str.contains(search_addr, na=False, case=False, regex=False)]
if sel_sido:     df = df[df['시도명'].isin(sel_sido)]
if sel_sgg:      df = df[df['시군구명'].isin(sel_sgg)]
if sel_adm:      df = df[df['읍면동명'].isin(sel_adm)]
if sel_heat:     df = df[df['난방구분'].isin(sel_heat)]
if sel_yong:     df = df[df['용도'].isin(sel_yong)]
if sel_svc:      df = df[df['서비스센터'].isin(sel_svc)]
if sel_gosi_yn:  df = df[df['고시여부'].isin(sel_gosi_yn)]
if sel_gosi_nm:  df = df[df['고시지역명'].isin(sel_gosi_nm)]
df = df[df['세대수'].between(sel_hoga[0], sel_hoga[1])]
df = df.reset_index(drop=True)

# ── 메트릭 카드 (난방방식별 아파트수 + 세대수) ──────────────────
heat_summary = (
    df.groupby('난방구분', dropna=False)['세대수']
      .agg(아파트수='count', 세대수합계='sum')
      .reset_index()
      .sort_values('세대수합계', ascending=False)
)
heat_summary['난방구분'] = heat_summary['난방구분'].fillna('기타')

# 전체 합계 카드 + 난방방식별 카드
total_cols = st.columns(2)
total_cols[0].metric("🏢 전체 아파트", f"{len(df):,}개")
total_cols[1].metric("👥 전체 세대수", f"{df['세대수'].sum():,}세대")

st.markdown("")  # 간격

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
    "html": "<b>{아파트명}</b><br>난방: {난방구분} · {세대수}세대<br>고시: {고시여부} {고시지역명}<br>{도로명주소}",
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
    use_container_width=True,
    height=520,
)

st.divider()

# ── 목록 & 상세 ──────────────────────────────────────────────────
st.subheader(f"📋 목록 ({len(df):,}건)")
st.caption("행을 클릭하면 아래에 상세정보가 표시됩니다.")

DISPLAY_COLS = ['아파트명', '아파트코드', '난방구분', '고시여부', '고시지역명',
                '세대수', '용도', '서비스센터', '시군구명', '읍면동명', '도로명주소']
display_cols = [c for c in DISPLAY_COLS if c in df.columns]

event = st.dataframe(
    df[display_cols],
    use_container_width=True,
    hide_index=True,
    height=350,
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
    with d2:
        st.metric("난방구분", row.get('난방구분', '-'))
        st.metric("용도", row.get('용도', '-'))
    with d3:
        st.metric("고시여부", row.get('고시여부', '-'))
        st.metric("고시지역명", row.get('고시지역명', '-') or '-')
    st.markdown(f"**📍 주소** : {row.get('도로명주소', '-')}")
    st.markdown(f"**🌐 위치** : 위도 `{row.get('위도', '-')}` · 경도 `{row.get('경도', '-')}`")
    st.markdown(f"**🗺️ 행정구역** : {row.get('시도명', '')} {row.get('시군구명', '')} {row.get('읍면동명', '')}")
    st.markdown(f"**🏢 서비스센터** : {row.get('서비스센터', '-')}")

st.divider()

# ── 통계 탭 ─────────────────────────────────────────────────────
st.subheader("📊 통계")
tab1, tab2, tab3 = st.tabs(["난방방식별", "시군구별", "고시지역별"])

with tab1:
    g1 = df.groupby('난방구분')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g1 = g1.sort_values('세대수합계', ascending=False)
    g1['아파트수'] = g1['아파트수'].map('{:,}'.format)
    g1['세대수합계'] = g1['세대수합계'].map('{:,}'.format)
    g1.columns = ['난방방식', '아파트수', '세대수 합계']
    st.dataframe(g1, use_container_width=True, hide_index=True)

with tab2:
    g2 = df.groupby('시군구명')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g2 = g2.sort_values('세대수합계', ascending=False)
    g2['아파트수'] = g2['아파트수'].map('{:,}'.format)
    g2['세대수합계'] = g2['세대수합계'].map('{:,}'.format)
    g2.columns = ['시군구', '아파트수', '세대수 합계']
    st.dataframe(g2, use_container_width=True, hide_index=True)

with tab3:
    g3 = df.groupby('고시여부')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g3_nm = df[df['고시여부']=='예'].groupby('고시지역명')['세대수'].agg(아파트수='count', 세대수합계='sum').reset_index()
    g3.columns = ['구분', '아파트수', '세대수 합계']
    g3_nm.columns = ['구분', '아파트수', '세대수 합계']
    combined = pd.concat([g3, g3_nm], ignore_index=True)
    combined['아파트수'] = combined['아파트수'].map('{:,}'.format)
    combined['세대수 합계'] = combined['세대수 합계'].map('{:,}'.format)
    st.dataframe(combined, use_container_width=True, hide_index=True)