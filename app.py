import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import numpy as np
import os
import urllib.parse # URL 인코딩을 위해 추가

# --- 1. 데이터 로드 함수 정의 ---
@st.cache_data
def load_data(github_base_url):
    # GitHub에서 파일을 직접 로드합니다.
    # 'github_base_url'은 'https://raw.githubusercontent.com/{YOUR_USERNAME}/{YOUR_REPOSITORY}/{YOUR_BRANCH}/data/' 와 같은 형식이어야 합니다.

    try:
        # 최적화된 Parquet 파일 로드 (이전 단계에서 최적화된 파일명을 사용합니다)
        # 한글 파일명을 URL 인코딩
        encoded_rental_filename = urllib.parse.quote('서울시_전월세거래_통합.parquet')
        rental_data_url = 'https://raw.githubusercontent.com/urbandhwi/findingmyhome/main/dat + encoded_rental_filename
        df = pd.read_parquet(rental_data_url)
        st.success(f"전월세 거래 데이터 로드 완료: {rental_data_url}")

        # geometry 컬럼 복원 (parquet 저장 시 제거되었을 수 있으므로)
        if 'geometry' not in df.columns:
            df = gpd.GeoDataFrame(
                df,
                geometry=gpd.points_from_xy(df.longitude, df.latitude),
                crs="EPSG:4326"
            )

        # GeoJSON 파일 로드
        # 한글 파일명을 URL 인코딩
        encoded_grid_filename = urllib.parse.quote('seoul_500m_grid.geojson')
        grid_url = github_base_url + encoded_grid_filename
        grid_gdf = gpd.read_file(grid_url)
        grid_gdf = grid_gdf.to_crs(epsg=4326) # CRS 통일
        st.success(f"500m 격자 데이터 로드 완료: {grid_url}")

        # 한글 파일명을 URL 인코딩
        encoded_dong_filename = urllib.parse.quote('seoul_dong.geojson')
        dong_url = github_base_url + encoded_dong_filename
        dong_gdf = gpd.read_file(dong_url)
        dong_gdf = dong_gdf.to_crs(epsg=4326) # CRS 통일
        st.success(f"법정동 경계 데이터 로드 완료: {dong_url}")

        # 한글 파일명을 URL 인코딩
        encoded_subway_filename = urllib.parse.quote('서울_지하철_종합.geojson')
        subway_url = github_base_url + encoded_subway_filename
        subway_gdf = gpd.read_file(subway_url)
        subway_gdf = subway_gdf.to_crs(epsg=4326) # CRS 통일
        st.success(f"서울 지하철 데이터 로드 완료: {subway_url}")

        return df, grid_gdf, dong_gdf, subway_gdf
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.info("GitHub URL 또는 파일 경로를 확인하거나, 파일이 public repository에 있는지 확인 바랍니다.")
        return None, None, None, None

# --- 2. Streamlit 앱 설정 및 데이터 로드 ---
st.set_page_config(layout="wide")
st.title("🏠 서울시 전월세 가격 지도 분석 (Streamlit)")

# GitHub raw content URL의 기본 경로를 설정하세요。
# YOUR_USERNAME, YOUR_REPOSITORY, YOUR_BRANCH는 실제 값으로 변경해야 합니다.
github_base_url = 'https://raw.githubusercontent.com/{YOUR_USERNAME}/{YOUR_REPOSITORY}/{YOUR_BRANCH}/data/' # 예시: 'https://raw.githubusercontent.com/username/repo/main/data/'

rental_data, grid_gdf, dong_gdf, subway_gdf = load_data(github_base_url)

if rental_data is None:
    st.stop() # 데이터 로드 실패 시 앱 중단

# 환산월세 계산 함수 (고정된 전환율 사용)
def calculate_converted_rent(row):
    conversion_rate_per_10k_deposit = 0.005 # 1만원 보증금당 0.005만원 월세
    return row['임대료(만원)'] + (row['보증금(만원)'] * conversion_rate_per_10k_deposit)

# --- 3. 사이드바 필터 설정 ---
st.sidebar.header("필터 설정")

# 1. 전월세구분
rent_type = st.sidebar.radio("전월세 구분", ['전체', '전세', '월세'])

# 2. 보증금(만원) 범위
deposit_options = {
    '전체': (0, 9999999), # 매우 큰 값으로 설정하여 '전체' 의미
    '1천만원 미만': (0, 1000),
    '1천만원 ~ 3천만원 미만': (1000, 3000),
    '3천만원 ~ 5천만원 미만': (3000, 5000),
    '5천만원 ~ 7천만원 미만': (5000, 7000),
    '7천만원 ~ 1억원 미만': (7000, 10000),
    '1억원 이상': (10000, 9999999) # 매우 큰 값
}
deposit_range_str = st.sidebar.selectbox("보증금(만원) 범위", list(deposit_options.keys()))
min_deposit, max_deposit = deposit_options[deposit_range_str]

# 3. 면적대 (제곱미터)
area_options = {
    '전체': (0, 9999999),
    '5㎡ ~ 15㎡ (3~4평)': (5, 15),
    '15㎡ ~ 20㎡ (5~6평)': (15, 20),
    '20㎡ ~ 30㎡ (7~9평)': (20, 30),
    '30㎡ ~ 40㎡ (10~12평)': (30, 40)
}
area_range_str = st.sidebar.selectbox("임대면적 (㎡)", list(area_options.keys()))
min_area, max_area = area_options[area_range_str]

# 4. 층수
floor_options = ['전체', '저층 제외 (2층 이상)', '1층 이하']
floor_selection = st.sidebar.radio("층수", floor_options)

# 5. 지도 시각화 기준 (동/격자)
visualization_unit = st.sidebar.radio("지도 시각화 단위", ['법정동', '500m 격자'])

# --- 4. 데이터 필터링 및 환산월세 계산 ---
filtered_df = rental_data.copy()

# 전월세구분 필터
if rent_type != '전체':
    filtered_df = filtered_df[filtered_df['전월세구분'] == rent_type]

# 보증금 필터
filtered_df = filtered_df[
    (filtered_df['보증금(만원)'] >= min_deposit) &
    (filtered_df['보증금(만원)'] < max_deposit)
]

# 면적 필터
filtered_df = filtered_df[
    (filtered_df['임대면적'] >= min_area) &
    (filtered_df['임대면적'] < max_area)
]

# 층수 필터
if floor_selection == '저층 제외 (2층 이상)':
    filtered_df = filtered_df[filtered_df['층'] >= 2]
elif floor_selection == '1층 이하':
    filtered_df = filtered_df[filtered_df['층'] <= 1]

# 환산월세 계산
if not filtered_df.empty:
    filtered_df['환산월세(만원)'] = filtered_df.apply(calculate_converted_rent, axis=1)
    st.sidebar.markdown(f"**선택된 조건의 평균 환산월세:** {filtered_df['환산월세(만원)'].mean():.2f} 만원")
else:
    st.sidebar.warning("선택된 조건에 해당하는 전월세 거래가 없습니다.")

# --- 5. 지도 시각화 (Folium) ---
seoul_center = [37.5665, 126.9780]
m = folium.Map(location=seoul_center, zoom_start=11, tiles='OpenStreetMap')

if not filtered_df.empty:
    # 시각화 단위에 따라 데이터 집계
    if visualization_unit == '법정동':
        # '법정동코드_법정동shp' 컬럼이 seoul_dong.geojson에 없으므로 '법정동코드' 사용
        # seoul_dong_gdf의 '법정동코드'를 string으로 변환하여 조인 키 통일
        dong_gdf['법정동코드'] = dong_gdf['법정동코드'].astype(str)

        # 전월세 데이터의 법정동코드를 string으로 변환
        filtered_df['법정동코드'] = filtered_df['법정동코드'].astype(str)

        agg_data = filtered_df.groupby('법정동코드')['환산월세(만원)'].agg(
            min_환산월세='min',
            max_환산월세='max',
            avg_환산월세='mean'
        ).reset_index()

        plot_gdf = dong_gdf.merge(
            agg_data,
            left_on='법정동코드',
            right_on='법정동코드',
            how='left'
        )
        plot_gdf['avg_환산월세'] = plot_gdf['avg_환산월세'].fillna(np.nan) # 데이터 없는 지역은 NaN

        folium.Choropleth(
            geo_data=plot_gdf,
            name=f'법정동별 평균 환산월세 ({rent_type})',
            data=plot_gdf.dropna(subset=['avg_환산월세']),
            columns=['법정동코드', 'avg_환산월세'],
            key_on='feature.properties.법정동코드',
            fill_color='YlGnBu',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name='평균 환산월세 (만원)',
            highlight=True,
            tooltip=folium.features.GeoJsonTooltip(
                fields=['EMD_NM', 'avg_환산월세', 'min_환산월세', 'max_환산월세'],
                aliases=['법정동명:', '평균 환산월세(만원):', '최저 환산월세(만원):', '최고 환산월세(만원):'],
                localize=True
            )
        ).add_to(m)
        st.info("법정동별 평균 환산월세 지도를 표시했습니다.")

    elif visualization_unit == '500m 격자':
        # grid_gdf의 'grid_id'를 string으로 변환하여 조인 키 통일
        grid_gdf['grid_id'] = grid_gdf['grid_id'].astype(str)

        # 전월세 데이터의 grid_id를 string으로 변환
        filtered_df['grid_id'] = filtered_df['grid_id'].astype(str)

        agg_data = filtered_df.groupby('grid_id')['환산월세(만원)'].agg(
            min_환산월세='min',
            max_환산월세='max',
            avg_환산월세='mean'
        ).reset_index()

        plot_gdf = grid_gdf.merge(
            agg_data,
            left_on='grid_id',
            right_on='grid_id',
            how='left'
        )
        plot_gdf['avg_환산월세'] = plot_gdf['avg_환산월세'].fillna(np.nan) # 데이터 없는 지역은 NaN

        folium.Choropleth(
            geo_data=plot_gdf,
            name=f'격자별 평균 환산월세 ({rent_type})',
            data=plot_gdf.dropna(subset=['avg_환산월세']),
            columns=['grid_id', 'avg_환산월세'],
            key_on='feature.properties.grid_id',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name='평균 환산월세 (만원)',
            highlight=True,
            tooltip=folium.features.GeoJsonTooltip(
                fields=['grid_id', 'avg_환산월세', 'min_환산월세', 'max_환산월세'],
                aliases=['격자 ID:', '평균 환산월세(만원):', '최저 환산월세(만원):', '최고 환산월세(만원):'],
                localize=True
            )
        ).add_to(m)
        st.info("500m 격자별 평균 환산월세 지도를 표시했습니다.")
else:
    st.warning("필터링된 데이터가 없어 전월세 시각화를 건너뜁니다.")

# --- 6. 지하철역 정보 오버레이 ---
if subway_gdf is not None and not subway_gdf.empty:
    subway_layer = folium.FeatureGroup(name='서울 지하철역 (호선별)').add_to(m)

    # 호선별 색상 매핑
    line_colors = {
        '1호선': 'blue', '2호선': 'green', '3호선': 'orange', '4호선': 'skyblue',
        '5호선': 'purple', '6호선': 'brown', '7호선': 'darkgreen', '8호선': 'pink',
        '9호선': 'darkorange', '수인분당선': 'yellow', '신분당선': 'red',
        '우이신설선': 'lightgreen', '경의중앙선': 'mediumblue', '공항철도': 'darkblue',
        '경춘선': 'forestgreen', '서해선': 'darkmagenta', '김고선': 'gold', '에버라인': 'darkkhaki',
        '의정부경전철': 'olive', '인천1호선': 'teal', '인천2호선': 'lightgray',
        '신림선': 'lightcoral', '동해선': 'cyan', '용인경전철': 'gray',
        'GTX-A': 'lightseagreen', 'GTX-B': 'mediumpurple', 'GTX-C': 'darkcyan'
    }

    for idx, row in subway_gdf.iterrows():
        hosun = row['hoseon'] if 'hoseon' in row else '기타'
        color = line_colors.get(hosun, 'gray') # 기본 색상은 회색
        tooltip_text = f"역명: {row['SWST_NM']}<br>호선: {hosun}"

        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            tooltip=tooltip_text
        ).add_to(subway_layer)
    st.success("서울 지하철역 정보를 지도에 추가했습니다.")
else:
    st.warning("지하철 데이터 로드에 실패하여 지하철역 정보를 표시하지 않습니다.")

folium.LayerControl().add_to(m)

# 지도 표시
st.write("### 전월세 거래 분포 지도")
st_folium(m, width=1200, height=700) # 너비를 1200으로 설정하여 지도 확장
