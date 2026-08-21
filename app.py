import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import urllib.parse # URL 인코딩을 위해 추가
import numpy as np # np.nan을 사용하기 위해 추가

# --- 1. 페이지 설정 ---
st.set_page_config(
    page_title="연립다세대/오피스텔 임대료 시각화",
    layout="wide"
)

st.title("🏢 연립다세대·오피스텔 조건별 연도별 임대료 시각화")

# --- GitHub raw content URL 설정 ---
# {YOUR_USERNAME}, {YOUR_REPOSITORY}, {YOUR_BRANCH}는 실제 값으로 변경해야 합니다.
# ☢☢ 중요: 데이터 파일의 실제 GitHub 경로에 맞춰 'github_base_url'을 설정해야 합니다.
# 예시 1: 'app.py'와 데이터 파일들이 모두 리포지토리 루트에 있다면:
# github_base_url = 'https://raw.githubusercontent.com/{YOUR_USERNAME}/{YOUR_REPOSITORY}/{YOUR_BRANCH}/'
# 예시 2: 'app.py'는 리포지토리 루트에 있고, 데이터 파일들은 'data/' 하위 디렉토리에 있다면:
# github_base_url = 'https://raw.githubusercontent.com/{YOUR_USERNAME}/{YOUR_REPOSITORY}/{YOUR_BRANCH}/data/'
github_base_url = 'https://raw.githubusercontent.com/urbandhwi/findingmyhome/main/' # 이곳을 사용자님의 GitHub URL로 변경해주세요!

# --- 2. 데이터 로드 함수 정의 ---
@st.cache_data
def load_data(base_url):
    # GitHub에서 파일을 직접 로드합니다.
    try:
        # 최적화된 Parquet 파일 로드
        encoded_rental_filename = urllib.parse.quote('seoul_rent.parquet')
        rental_data_url = base_url + encoded_rental_filename
        df = pd.read_parquet(rental_data_url)
        st.success(f"전월세 거래 데이터 로드 완료: {rental_data_url}")

        # geometry 컬럼 복원 (parquet 저장 시 제거되었을 수 있으므로)
        if 'geometry' not in df.columns:
            df = gpd.GeoDataFrame(
                df,
                geometry=gpd.points_from_xy(df.longitude, df.latitude),
                crs="EPSG:4326"
            )

        # GeoJSON 파일 로드 (법정동)
        encoded_dong_filename = urllib.parse.quote('seoul_dong.geojson')
        dong_url = base_url + encoded_dong_filename
        geojson_dong = gpd.read_file(dong_url)
        geojson_dong = geojson_dong.to_crs(epsg=4326) # CRS 통일
        st.success(f"법정동 경계 데이터 로드 완료: {dong_url}")

        # GeoJSON 파일 로드 (500m 격자)
        encoded_grid_filename = urllib.parse.quote('seoul_500m_grid.geojson')
        grid_url = base_url + encoded_grid_filename
        geojson_grid = gpd.read_file(grid_url)
        geojson_grid = geojson_grid.to_crs(epsg=4326) # CRS 통일
        st.success(f"500m 격자 데이터 로드 완료: {grid_url}")

        # GeoJSON 파일 로드 (자치구) - NEW
        encoded_gu_filename = urllib.parse.quote('seoul_gu.geojson') # Assuming user named it seoul_gu.geojson
        gu_url = base_url + encoded_gu_filename
        geojson_gu = gpd.read_file(gu_url)
        geojson_gu = geojson_gu.to_crs(epsg=4326) # CRS 통일
        st.success(f"자치구 경계 데이터 로드 완료: {gu_url}")

        # `seoul_dong.geojson`에는 '법정동코드'가 문자열로 저장되어 있습니다. (Cell zjRgA_OzBjYC 참고)
        # plotly.express의 featureidkey가 `feature.properties.법정동코드`를 사용하려면
        # geojson_dong의 '법정동코드' 컬럼이 있어야 합니다.
        if '법정동코드' not in geojson_dong.columns:
            # `EMD_CD` 컬럼이 있다면 이를 이용해 '법정동코드' 생성
            if 'EMD_CD' in geojson_dong.columns:
                # `df_raw`의 '법정동코드'가 5자리 법정동코드이므로, `EMD_CD`의 마지막 3자리 + '00' 형태로 추출
                geojson_dong['법정동코드'] = geojson_dong['EMD_CD'].astype(str).str[-3:] + '00'
            else:
                st.warning("geojson_dong에 'EMD_CD' 또는 '법정동코드' 컬럼이 없어 법정동 시각화에 문제가 있을 수 있습니다.")

        # Ensure `자치구코드` in `geojson_dong` and `SIG_CD` in `geojson_gu` are string for merging
        if '자치구코드' not in geojson_dong.columns and 'EMD_CD' in geojson_dong.columns:
            geojson_dong['자치구코드'] = geojson_dong['EMD_CD'].astype(str).str[0:5]

        if '자치구코드' in geojson_dong.columns:
            geojson_dong['자치구코드'] = geojson_dong['자치구코드'].astype(str)
        if 'SIG_CD' in geojson_gu.columns:
            geojson_gu['SIG_CD'] = geojson_gu['SIG_CD'].astype(str)

        # 지도 시각화의 고유 ID로 사용할 unique_map_key 생성 (자치구코드 + 법정동코드)
        if '자치구코드' in geojson_dong.columns and '법정동코드' in geojson_dong.columns:
            geojson_dong['unique_map_key'] = geojson_dong['자치구코드'].astype(str) + '_' + geojson_dong['법정동코드'].astype(str)
        else:
            st.warning("geojson_dong에 '자치구코드' 또는 '법정동코드' 컬럼이 없어 unique_map_key를 생성할 수 없습니다.")


        return df, geojson_dong, geojson_grid, geojson_gu # Return geojson_gu
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.info("GitHub URL 또는 파일 경로를 확인하거나, 파일이 public repository에 있는지 확인 바랍니다.")
        return None, None, None, None # Add None for geojson_gu

try:
    df_raw, geojson_dong, geojson_grid, geojson_gu = load_data(github_base_url)
except Exception as e:
    st.error(f"데이터 파일 로드 중 오류가 발생했습니다: {e}")
    st.stop()

# --- 3. 사이드바 - 조건 선택 필터 ---
st.sidebar.header("🔍 검색 조건 설정")

house_type_selection = st.sidebar.radio("주택 유형", ["전체", "연립다세대", "오피스텔"]) # '전체' 옵션 추가
spatial_unit = st.sidebar.radio("시각화 단위", ["법정동별", "격자별"]) # '행정동별'을 '법정동별'로 명칭 변경
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

# --- 4. 데이터 필터링 및 환산 로직 ---
if submit_button:
    df = df_raw.copy()

    # 주택 유형 필터
    if house_type_selection != "전체":
        df = df[df["건물용도"] == house_type_selection]

    # 연도 필터 (컬럼명 '접수년도' 사용)
    if "접수년도" in df.columns:
        df = df[df["접수년도"] == selected_year]

    # 보증금 필터 (컬럼명 '보증금(만원)' 사용)
    if "보증금(만원)" in df.columns:
        df = df[(df["보증금(만원)"] >= dep_min) & (df["보증금(만원)"] < dep_max)]

    # 면적 필터 (컬럼명 '임대면적' 사용)
    if "임대면적" in df.columns:
        df = df[(df["임대면적"] >= area_min) & (df["임대면적"] < area_max)]

    # 건물 연식 필터 (컬럼명 '건축년도' 사용)
    if "건축년도" in df.columns:
        if selected_age == "신축 (2020년 이후)":
            df = df[df["건축년도"] >= 2020]
        elif selected_age == "구축 (2000년 이전)":
            df = df[df["건축년도"] < 2000]

    # 층수 필터 (컬럼명 '층' 사용)
    if "층" in df.columns:
        if selected_floor == "저층 (1층 이하)":
            df = df[df["층"] <= 1]

    # 환산 임대료 계산 (컬럼명 '보증금(만원)', '임대료(만원)' 사용)
    if not df.empty and "보증금(만원)" in df.columns and "임대료(만원)" in df.columns:
        df["adjusted_rent"] = df["임대료(만원)"] - (df["보증금(만원)"] - base_deposit) * 0.005

        # 법정동 또는 격자 기준으로 집계
        # '법정동별' 시각화 시에는 자치구코드와 법정동코드를 조합한 고유 키 사용
        if spatial_unit == "법정동별":
            df['unique_map_key'] = df['자치구코드'].astype(str) + '_' + df['법정동코드'].astype(str)
            group_col = "unique_map_key"
            # `target_geojson`도 `unique_map_key`를 포함해야 함
            # `geojson_dong`이 이미 `unique_map_key`를 가지고 있으므로 `target_geojson`은 그대로 `geojson_dong` 사용
        else:
            group_col = "grid_id"
        
        target_geojson = geojson_dong if spatial_unit == "법정동별" else geojson_grid

        # `group_col`이 `df`에 있는지 확인하고 타입 통일
        if group_col in df.columns:
            df[group_col] = df[group_col].astype(str)
            # `target_geojson`의 해당 ID 컬럼도 문자열로 통일
            if group_col in target_geojson.columns:
                target_geojson[group_col] = target_geojson[group_col].astype(str)

        # Aggregate statistics
        aggregated_df = df.groupby(group_col)["adjusted_rent"].agg(
            count_거래건수='count',
            avg_환산임대료='mean',
            min_환산임대료='min',
            max_환산임대료='max',
            median_환산임대료='median'
        ).reset_index()

        # Merge with GeoJSON for plotting
        if spatial_unit == "법정동별":
            plot_gdf = target_geojson.merge(
                aggregated_df,
                left_on='unique_map_key', # GeoJSON의 고유 키
                right_on='unique_map_key', # 집계된 데이터의 고유 키
                how='left'
            )
            plot_gdf['avg_환산임대료'] = plot_gdf['avg_환산임대료'].fillna(np.nan) # 데이터 없는 지역은 NaN

            # NEW: Merge with geojson_gu to get SIG_KOR_NM (자치구명)
            plot_gdf = plot_gdf.merge(
                geojson_gu[['SIG_CD', 'SIG_KOR_NM']],
                left_on='자치구코드', # geojson_dong's district code
                right_on='SIG_CD', # geojson_gu's district code
                how='left'
            )
            # Drop the redundant SIG_CD column from the merge
            plot_gdf.drop(columns=['SIG_CD'], inplace=True, errors='ignore')

            feature_id_key = "properties.unique_map_key" # Plotly가 GeoJSON에서 찾을 고유 키
            hover_name_col = "EMD_NM" # Display legal district name
            hover_data_cols = ['count_거래건수', 'min_환산임대료', 'max_환산임대료', 'median_환산임대료', 'SIG_KOR_NM'] # Added SIG_KOR_NM
        else: # 격자별
            plot_gdf = target_geojson.merge(
                aggregated_df,
                left_on='grid_id',
                right_on='grid_id',
                how='left'
            )
            plot_gdf['avg_환산임대료'] = plot_gdf['avg_환산임대료'].fillna(np.nan) # 데이터 없는 지역은 NaN
            feature_id_key = "properties.grid_id"
            hover_name_col = "grid_id" # Display grid_id for grid
            hover_data_cols = ['count_거래건수', 'min_환산임대료', 'max_환산임대료', 'median_환산임대료']


        # 5. 지도 시각화
        st.subheader(f"📊 {selected_year}년 {house_type_selection} {spatial_unit} 평균 환산 임대료")

        # Plotly Express Choropleth Map
        fig = px.choropleth_mapbox(
            plot_gdf.dropna(subset=['avg_환산임대료']), # Only plot areas with data
            geojson=target_geojson, # Use original geojson for boundaries
            locations=group_col, # Column in aggregated_df/plot_gdf for matching
            featureidkey=feature_id_key, # Key in geojson properties for matching
            color="avg_환산임대료",
            color_continuous_scale="Viridis",
            range_color=(plot_gdf["avg_환산임대료"].min(), plot_gdf["avg_환산임대료"].max()),
            mapbox_style="carto-positron",
            zoom=9,
            center={"lat": 37.5665, "lon": 126.9780},
            opacity=0.6,
            labels={
                "avg_환산임대료": "평균 환산 임대료 (만원)",
                "count_거래건수": "거래 건수",
                "min_환산임대료": "최소 환산 임대료 (만원)",
                "max_환산임대료": "최고 환산 임대료 (만원)",
                "median_환산임대료": "중앙 환산 임대료 (만원)",
                "SIG_KOR_NM": "자치구"
            },
            hover_name=hover_name_col, # Use EMD_NM or grid_id for hover label
            hover_data=hover_data_cols # Include other statistics in hover info
        )
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=600)
        st.plotly_chart(fig, use_container_width=True)

        st.write(f"총 거래 건수: **{len(df):,}** 건")

        # Display the aggregated data in a dataframe as requested by the user
        if spatial_unit == "법정동별":
            display_cols = ['SIG_KOR_NM', 'EMD_NM', 'count_거래건수', 'avg_환산임대료', 'min_환산임대료', 'max_환산임대료', 'median_환산임대료']
            st.dataframe(plot_gdf[display_cols].dropna(subset=['avg_환산임대료']).rename(columns={
                'SIG_KOR_NM': '자치구',
                'EMD_NM': '법정동',
                'count_거래건수': '거래건수',
                'avg_환산임대료': '평균 환산 임대료 (만원)',
                'min_환산임대료': '최소 환산 임대료 (만원)',
                'max_환산임대료': '최고 환산 임대료 (만원)',
                'median_환산임대료': '중앙 환산 임대료 (만원)'
            }))
        else: # 격자별
            st.dataframe(aggregated_df.rename(columns={
                'count_거래건수': '거래건수',
                'avg_환산임대료': '평균 환산 임대료 (만원)',
                'min_환산임대료': '최소 환산 임대료 (만원)',
                'max_환산임대료': '최고 환산 임대료 (만원)',
                'median_환산임대료': '중앙 환산 임대료 (만원)'
            }))

    else:
        st.warning("선택한 조건에 해당하는 데이터가 없거나, 필요한 컬럼이 누락되었습니다.")
else:
    st.info("왼쪽 사이드바에서 필터 조건을 선택한 후 '시각화 실행' 버튼을 눌러주세요.")
