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

# 2. Github 데이터 로드 (캐싱 처리)
# TODO: GITHUB_BASE_URL을 실제 파일이 위치한 GitHub Raw URL 경로로 수정하세요.
GITHUB_BASE_URL = "https://raw.githubusercontent.com/urbandhwi/findingmyhome/main/"

@st.cache_data
def load_data():
    # 거래 데이터 로드
    df = pd.read_csv(GITHUB_BASE_URL + "rent_data.csv")
    
    # 공간 데이터(GeoJSON) 로드
    geojson_dong = gpd.read_file(GITHUB_BASE_URL + "seoul_dong.geojson")
    geojson_grid = gpd.read_file(GITHUB_BASE_URL + "seoul_grid.geojson")
    
    return df, geojson_dong, geojson_grid

try:
    df_raw, geojson_dong, geojson_grid = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# 3. 사이드바 - 조건 선택 필터
st.sidebar.header("🔍 검색 조건 설정")

# 주택 유형
house_type = st.sidebar.radio("주택 유형", ["연립다세대", "오피스텔"])

# 시각화 단위
spatial_unit = st.sidebar.radio("시각화 단위", ["행정동별", "격자별"])

# 연도 선택
selected_year = st.sidebar.selectbox("연도", [2023, 2024, 2025])

# 보증금 구간 및 환산 기준 임대료 선택
deposit_options = {
    "1000만원 미만": (0, 1000, 500),
    "1000~3000만원 미만": (1000, 3000, 1000),
    "3000~5000만원 미만": (3000, 5000, 3000),
    "5000만원~1억원": (5000, 10000, 5000)
}
selected_deposit_label = st.sidebar.selectbox("보증금 구간", list(deposit_options.keys()))
dep_min, dep_max, base_deposit = deposit_options[selected_deposit_label]

# 면적대 선택 (㎡)
area_options = {
    "15 미만": (0, 15),
    "15~25": (15, 25),
    "25 이상": (25, 9999)
}
selected_area_label = st.sidebar.selectbox("면적대 (㎡)", list(area_options.keys()))
area_min, area_max = area_options[selected_area_label]

# 건물 연식 선택
age_options = ["전체", "신축 (2020년 이후)", "구축 (2000년 이전)"]
selected_age = st.sidebar.selectbox("건물 연식", age_options)

# 층수 선택
floor_options = ["전체", "저층 (1층 이하)"]
selected_floor = st.sidebar.selectbox("층수", floor_options)

submit_button = st.sidebar.button("시각화 실행", type="primary")

# 4. 데이터 필터링 및 환산 로직
if submit_button:
    df = df_raw.copy()

    # 주택 유형
    if "house_type" in df.columns:
        df = df[df["house_type"] == house_type]

    # 연도
    if "year" in df.columns:
        df = df[df["year"] == selected_year]

    # 보증금 구간
    if "deposit" in df.columns:
        df = df[(df["deposit"] >= dep_min) & (df["deposit"] < dep_max)]

    # 면적대
    if "area" in df.columns:
        df = df[(df["area"] >= area_min) & (df["area"] < area_max)]

    # 건물 연식 (건축년도 기준)
    if "build_year" in df.columns:
        if selected_age == "신축 (2020년 이후)":
            df = df[df["build_year"] >= 2020]
        elif selected_age == "구축 (2000년 이전)":
            df = df[df["build_year"] < 2000]

    # 층수
    if "floor" in df.columns:
        if selected_floor == "저층 (1층 이하)":
            df = df[df["floor"] <= 1]

    # 보증금 환산 임대료 계산
    # 공식: 실제임대료 + (보증금 - 기준보증금) * (-0.005)
    # (보증금 1만원 상승 시 임대료 50원 감소 = 0.005만원 감소)
    if not df.empty and "deposit" in df.columns and "rent" in df.columns:
        df["adjusted_rent"] = df["rent"] - (df["deposit"] - base_deposit) * 0.005

        # 공간 단위별 평균 임대료 집계
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

        # 요약 데이터 표시
        st.write(f"총 거래 건수: **{len(df):,}** 건")
        st.dataframe(aggregated_df)
    else:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
else:
    st.info("왼쪽 사이드바에서 필터 조건을 선택한 후 '시각화 실행' 버튼을 눌러주세요.")
