import streamlit as st
import requests
import pandas as pd
import datetime

# 에어코리아/생활기상 미세먼지, 자외선 서비스키
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
AIR_API_URL = "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
UV_API_URL = "http://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4"

SIDO_LIST = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "세종"
]
# areaNo 매핑 (일부 샘플, 확장 가능)
AREA_NO = {
    "서울": "1100000000",
    "부산": "2600000000",
    "대구": "2700000000",
    "인천": "2800000000",
    "광주": "2900000000",
    "대전": "3000000000",
    "울산": "3100000000",
    "경기": "4100000000",
    "강원": "4200000000",
    "충북": "4300000000",
    "충남": "4400000000",
    "전북": "4500000000",
    "전남": "4600000000",
    "경북": "4700000000",
    "경남": "4800000000",
    "제주": "5000000000",
    "세종": "3611000000",
}

st.set_page_config(
    page_title="실시간 미세먼지 조회 대시보드",
    page_icon="☁️",
    layout="wide"
)
st.title("☁️ 실시간 미세먼지 조회 대시보드")

selected_sido = st.sidebar.selectbox("시/도를 선택하세요", SIDO_LIST)
today = datetime.date.today()
yyyymmdd = today.strftime("%Y%m%d")
uv_query_time = yyyymmdd + "12"  # 자외선은 정오값

def fetch_air_quality(sido_name):
    params = {
        "serviceKey": SERVICE_KEY,
        "returnType": "json",
        "sidoName": sido_name,
        "numOfRows": 1000,
        "pageNo": 1
    }
    try:
        response = requests.get(AIR_API_URL, params=params, timeout=10)
        response.raise_for_status()
        items = response.json()["response"]["body"]["items"]
        return items
    except Exception:
        return None

def get_uv_index(area_no, yyyymmddhh):
    url = (f"{UV_API_URL}?serviceKey={SERVICE_KEY}&areaNo={area_no}&time={yyyymmddhh}&dataType=JSON")
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        uv_today = items[0].get("today")
        return uv_today
    except Exception:
        return None

# --- 데이터 가져오기
air_data = fetch_air_quality(selected_sido)
area_no = AREA_NO.get(selected_sido)
uv_value = get_uv_index(area_no, uv_query_time) if area_no else None

# --- 예외처리/시각화
if air_data is None:
    st.error("실시간 미세먼지 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
elif len(air_data) == 0:
    st.warning("선택하신 지역의 실시간 대기정보가 없습니다.")
else:
    df = pd.DataFrame(air_data)
    for col in ['pm10Value', 'pm25Value']:
        df[col] = pd.to_numeric(df[col].replace(['-', ''], pd.NA), errors='coerce')
    mean_pm10 = df['pm10Value'].mean(skipna=True)
    mean_pm25 = df['pm25Value'].mean(skipna=True)

    # -- 지표 영역: 평균 및 자외선지수
    col1, col2, col3 = st.columns([1,1,1])
    col1.metric("평균 미세먼지(PM10)", f"{mean_pm10:.1f} ㎍/㎥" if not pd.isna(mean_pm10) else "-")
    col2.metric("평균 초미세먼지(PM2.5)", f"{mean_pm25:.1f} ㎍/㎥" if not pd.isna(mean_pm25) else "-")
    if uv_value is not None and uv_value != "-":
        uv_float = float(uv_value)
        uv_int = int(round(uv_float))
        if uv_int <= 2:
            level = "낮음 🌤️"
            guide = "야외활동에 큰 지장 없습니다."
        elif uv_int <= 5:
            level = "보통 😎"
            guide = "가벼운 자외선 차단 권장!"
        elif uv_int <= 7:
            level = "높음 🕶️"
            guide = "모자·선크림·양산 등 보호구 착용 필수"
        elif uv_int <= 10:
            level = "매우 높음 ☀️"
            guide = "한낮 야외활동 자제, 충분히 차단하세요!"
        else:
            level = "위험 🚨"
            guide = "실외활동 피하기, 반드시 보호구 착용"
        col3.metric("오늘 자외선지수(UV)", f"{uv_value} ({level})")
        with col3:
            st.caption(f"생활권고: {guide}")
    else:
        col3.metric("오늘 자외선지수(UV)", "정보없음")

    # -- 측정소별 상세 데이터
    st.subheader(f"📊 {selected_sido} 측정소별 실시간 미세먼지 정보")
    table_df = df[["stationName", "pm10Value", "pm25Value", "dataTime"]].rename(
        columns={
            "stationName": "측정소명",
            "pm10Value": "미세먼지(PM10)",
            "pm25Value": "초미세먼지(PM2.5)",
            "dataTime": "측정시각"
        }
    )
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # -- PM10 바 차트
    st.subheader(f"🟦 {selected_sido} 주요 측정소별 미세먼지(PM10) 비교")
    graph_df = table_df[["측정소명", "미세먼지(PM10)"]].dropna()
    if len(graph_df) > 0:
        graph_df = graph_df.set_index("측정소명").sort_values("미세먼지(PM10)", ascending=False)
        st.bar_chart(graph_df)
    else:
        st.info("PM10 그래프를 그릴 데이터가 부족합니다.")

st.caption("데이터 출처: 공공데이터포털 에어코리아/기상청 생활기상지수 OpenAPI. 1시간 단위 실시간 갱신.")
