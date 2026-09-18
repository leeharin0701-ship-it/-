import pandas as pd
import numpy as np
import requests
import streamlit as st
import plotly.express as px

# 1. 스트림릿 페이지 기본 설정 (와이드 레이아웃 사용)
st.set_page_config(
    page_title="전국 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 대한민국 시군구별 고령화 지도 대시보드")
st.write("연도별·지역별 65세 이상 인구 비율(고령화율)을 지도 단계구분도와 표로 확인하는 앱입니다.")

# 2. 데이터 로드 함수 (캐시를 사용하여 앱 실행 속도 향상)
@st.cache_data
def load_data():
    # 전국 읍·면·동 연도별 인구 데이터 (CSV.gz)
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    # '코드' 열은 자릿수 손실 방지를 위해 확실하게 문자열(str)로 읽어옵니다.
    df_pop = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 전국 시군구 경계 GeoJSON 데이터
    geo_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geo_url)
    geojson_data = response.json()
    
    return df_pop, geojson_data

# 데이터 불러오기 실행
with st.spinner("데이터를 불러오는 중입니다... 잠시만 기다려주세요."):
    df_pop, sigungu_geo = load_data()

# 3. 사이드바 설정 (연도 선택 및 지역 필터링)
st.sidebar.header("⚙️ 지도 및 데이터 옵션")

# 연도 선택 슬라이더
available_years = sorted(df_pop['연도'].unique())
selected_year = st.sidebar.slider(
    "분석 연도 선택", 
    min_value=min(available_years), 
    max_value=max(available_years), 
    value=max(available_years) # 기본값은 가장 최신 연도
)

# 4. 선택한 연도의 데이터 전처리
df_filtered_year = df_pop[df_pop['연도'] == selected_year].copy()

# 행정동 코드(10자리)에서 앞 5자리를 추출하여 시군구 코드 생성
df_filtered_year['시군구코드'] = df_filtered_year['코드'].str.zfill(10).str.slice(0, 5)

# 나이별 열 이름 자동 인식 ('계_X세' 형식)
all_age_cols = []
valid_age_cols = []

for col in df_filtered_year.columns:
    if col.startswith('계_') and '세' in col:
        all_age_cols.append(col)
        num_str = col.replace('계_', '').replace('세', '').replace(' 이상', '')
        if num_str.isdigit() and int(num_str) >= 65:
            valid_age_cols.append(col)

# 전체 인구 및 65세 이상 인구 계산
df_filtered_year['전체인구'] = df_filtered_year[all_age_cols].sum(axis=1)
df_filtered_year['65세이상인구'] = df_filtered_year[valid_age_cols].sum(axis=1)

# 시군구별로 그룹화하여 합계 구하기
sigungu_pop = df_filtered_year.groupby('시군구코드').agg({
    '시도': 'first',
    '시군구': 'first',
    '전체인구': 'sum',
    '65세이상인구': 'sum'
}).reset_index()

# 고령화율(%) 계산
sigungu_pop['고령화율'] = (sigungu_pop['65세이상인구'] / sigungu_pop['전체인구']) * 100

# 5. 5단계 구간 나누기 (경계값: 19%, 23%, 28%, 38%)
bins = [-np.inf, 19, 23, 28, 38, np.inf]
labels = ['19% 미만', '19%~23%', '23%~28%', '28%~38%', '38% 이상']
sigungu_pop['고령화구간'] = pd.cut(sigungu_pop['고령화율'], bins=bins, labels=labels)

# 시도별 상세보기 필터 (사이드바)
sido_list = ['전국'] + sorted(sigungu_pop['시도'].dropna().unique().tolist())
selected_sido = st.sidebar.selectbox("시도별 상세보기 필터", sido_list)

if selected_sido != '전국':
    map_data = sigungu_pop[sigungu_pop['시도'] == selected_sido]
else:
    map_data = sigungu_pop

# 6. Plotly를 이용한 단계구분도(Choropleth) 시각화
fig = px.choropleth(
    map_data,
    geojson=sigungu_geo,
    locations='시군구코드',
    featureidkey="properties.코드", # GeoJSON의 시군구 코드 속성과 매칭
    color='고령화구간',
    color_discrete_map={
        '19% 미만': '#edf8fb',
        '19%~23%': '#b2e2e2',
        '23%~28%': '#66c2a4',
        '28%~38%': '#2ca25f',
        '38% 이상': '#006d2c'
    },
    category_orders={'고령화구간': labels},
    hover_name='시군구',
    hover_data={
        '시군구코드': False,
        '시도': True,
        '고령화율': ':.2f'
    },
    labels={'고령화구간': '고령화율 구간', '시도': '시도', '고령화율': '고령화율(%)'}
)

# 배경 지도 타일 없이 경계선만 깔끔하게 표시 (지역 선택에 따라 지도 자동 확대)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r":0, "t":0, "l":0, "b":0},
    legend_title_text=f'<b>{selected_year}년 고령화율</b>'
)

st.subheader(f"📍 {selected_year}년 시군구별 고령화 지도 ({selected_sido})")
st.plotly_chart(fig, use_container_width=True)

# 7. 데이터 다운로드 버튼 (사이드바)
st.sidebar.markdown("---")
csv_data = sigungu_pop.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(
    label=f"📥 {selected_year}년 데이터 CSV 다운로드",
    data=csv_data,
    file_name=f"aging_population_{selected_year}.csv",
    mime="text/csv",
)

st.markdown("---")

# 8. 지도 아래 고령화율 상위 10개 및 하위 10개 표 나란히 배치 (전국 기준)
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"🔴 {selected_year}년 고령화율 높은 시군구 Top 10")
    top_10 = sigungu_pop.nlargest(10, '고령화율')[['시도', '시군구', '고령화율']]
    top_10['고령화율'] = top_10['고령화율'].round(2).astype(str) + '%'
    top_10.reset_index(drop=True, inplace=True)
    top_10.index = top_10.index + 1
    st.dataframe(top_10, use_container_width=True)

with col2:
    st.subheader(f"🔵 {selected_year}년 고령화율 낮은 시군구 Top 10")
    bottom_10 = sigungu_pop.nsmallest(10, '고령화율')[['시도', '시군구', '고령화율']]
    bottom_10['고령화율'] = bottom_10['고령화율'].round(2).astype(str) + '%'
    bottom_10.reset_index(drop=True, inplace=True)
    bottom_10.index = bottom_10.index + 1
    st.dataframe(bottom_10, use_container_width=True)
