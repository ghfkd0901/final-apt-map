import streamlit as st

st.set_page_config(
    page_title="대성에너지 아파트 지도",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("views/map.py", title="공동주택 지도", icon="🏢", default=True),
    st.Page("views/sales.py", title="영업대상", icon="🎯"),
    st.Page("views/about.py", title="데이터 안내", icon="📖"),
])
pg.run()
