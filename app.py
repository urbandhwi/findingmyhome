import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(
    page_title="연립다세대/오피스텔 임대료 시각화",
    layout="wide"
)

st.title("🏢 연립다세대·오피스텔 조건별 연도별 임대료 시각화")

# 2. 상대 경로를 이용한 데이터 로드 (parquet 파일 읽기)
@st.cache_data
def load_data():
    # Parquet 파일 및 공간 데이터 읽기
    df = pd.read_parquet("seoul_rent.parquet")
    geojson_dong = gpd.read_file("seoul_dong.geojson")
    geojson_grid = gpd.read_file("seoul_grid.geojson")
    
    return df, geojson_dong, geojson_grid

try:
    df_raw, geojson_dong, geojson_grid = load_data()
except Exception as e:
    st.error(f"데이터 파일 로드 중 오류가 발생했습니다: {e}")
    st.stop()

# 3. 사이드바 - 조건 선택 필터
st.sidebar.header("🔍 검색 조건 설정")

house_type = st.sidebar.radio("주택 유형", ["연립다세대", "오피스텔"])
spatial_unit = st.sidebar.radio("시각화 단위", ["행정동별", "격자별"])
selected_year = st.sidebar.selectbox("연도", [2023, 2024, 2025])

deposit_options = {
    "1000만원 미만": (0, 1000, 500),
    "1000~3000만원 미만": (1000, 3000, 1000),
    "3000~5000만원 미만": (3000, 5000, 3000),
    "5000만원~1억원": (5000, 10000, 5000)
}
selected_deposit_label = st.sidebar.selectbox("보증금 구간", list(deposit_options.keys()))
dep_min, dep_max, base_deposit = deposit_options[selected_deposit_label]

area_options = {
    "15 미만": (0, 15),
    "15~25": (15, 25),
    "25 이상": (25, 9999)
}
selected_area_label = st.sidebar.selectbox("면적대 (㎡)", list(area_options.keys()))
area_min, area_max = area_options[selected_area_label]

selected_age = st.sidebar.selectbox("건물 연식", ["전체", "신축 (2020년 이후)", "구축 (2000년 이전)"])
selected_floor = st.sidebar.selectbox("층수", ["전체", "저층 (1층 이하)"])

submit_button = st.sidebar.button("시각화 실행", type="primary")

# 4. 데이터 필터링 및 환산 로직
if submit_button:
    df = df_raw.copy()

    if "house_type" in df.columns:
        df = df[df["house_type"] == house_type]

    if "year" in df.columns:
        df = df[df["year"] == selected_year]

    if "deposit" in df.columns:
        df = df[(df["deposit"] >= dep_min) & (df["deposit"] < dep_max)]

    if "area" in df.columns:
        df = df[(df["area"] >= area_min) & (df["area"] < area_max)]

    if "build_year" in df.columns:
        if selected_age == "신축 (2020년 이후)":
            df = df[df["build_year"] >= 2020]
        elif selected_age == "구축 (2000년 이전)":
            df = df[df["build_year"] < 2000]

    if "floor" in df.columns:
        if selected_floor == "저층 (1층 이하)":
            df = df[df["floor"] <= 1]

    # 환산 임대료 계산
    if not df.empty and "deposit" in df.columns and "rent" in df.columns:
        df["adjusted_rent"] = df["rent"] - (df["deposit"] - base_deposit) * 0.005

        group_col = "dong_id" if spatial_unit == "행정동별" else "grid_id"
        target_geojson = geojson_dong if spatial_unit == "행정동별" else geojson_grid
        feature_id = "ADM_CD" if spatial_unit == "행정동별" else "GRID_ID"

        aggregated_df = df.groupby(group_col)["adjusted_rent"].mean().reset_index()

        # 5. 지도 시각화
        st.subheader(f"📊 {selected_year}년 {house_type} {spatial_unit} 평균 환산 임대료")
        
        fig = px.choropleth_mapbox(
            aggregated_df,
            geojson=target_geojson,
            locations=group_col,
            featureidkey=f"properties.{feature_id}",
            color="adjusted_rent",
            color_continuous_scale="Viridis",
            range_color=(aggregated_df["adjusted_rent"].min(), aggregated_df["adjusted_rent"].max()),
            mapbox_style="carto-positron",
            zoom=10,
            center={"lat": 37.5665, "lon": 126.9780},
            opacity=0.6,
            labels={"adjusted_rent": "환산 임대료 (만원)"}
        )
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=600)
        st.plotly_chart(fig, use_container_width=True)

        st.write(f"총 거래 건수: **{len(df):,}** 건")
        st.dataframe(aggregated_df)
    else:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
else:
    st.info("왼쪽 사이드바에서 필터 조건을 선택한 후 '시각화 실행' 버튼을 눌러주세요.")
