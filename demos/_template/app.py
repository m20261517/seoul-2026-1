import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

# 🎫 공공데이터포털 API KEY (반드시 본인 발급키로 적용)
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')             # 기상청 API에서 사용

# 여러 지역 격자 좌표 예시
LOCATIONS = {
    "성남시 분당구": (127, 202),
    "서울 종로구": (60, 127),
    "부산 중구": (98, 76),
}

st.set_page_config(
    page_title="야외수업 가능 날씨 앱 (공공데이터포털 API)",
    page_icon="📊",
    layout="wide",
)

st.title("📊 야외수업 가능 날씨 앱")
st.caption("공공데이터포털 기상청 실시간 데이터 기반 야외수업/점심시간 운동장 가능성 판단")

tab1, tab2, tab3 = st.tabs([
    "날짜/지역 지정",
    "결과 확인",
    "이번 주 가능 요일(점심시간 포함)"
])

with tab1:
    # 날짜 선택
    picked_date = st.date_input(
        "날짜를 선택하세요",
        value=datetime.date.today(),
        min_value=datetime.date.today() - datetime.timedelta(days=7),
        max_value=datetime.date.today() + datetime.timedelta(days=6)
    )

    # 지역 선택
    location_name = st.selectbox("지역을 선택하세요", options=list(LOCATIONS.keys()))
    GRID_NX, GRID_NY = LOCATIONS[location_name]

    # 선택값 저장(세션)
    st.session_state['picked_date'] = picked_date
    st.session_state['location_name'] = location_name
    st.session_state['GRID_NX'] = GRID_NX
    st.session_state['GRID_NY'] = GRID_NY

def fetch_weather(base_date, nx, ny, base_time="1100", target_hour="12"):
    """
    기상청 단기 예보에서 특정 날짜(base_date), 좌표(nx,ny), 발표시간(base_time)의
    특정 시각(target_hour, HH) 1시간의 TMP/POP(기온/강수확률)을 가져옴
    """
    url = (
        "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={ENCODED_KEY}&numOfRows=100&pageNo=1&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        TMP = next(float(i["fcstValue"]) for i in items if i["category"] == "TMP" and i["fcstTime"].startswith(target_hour))
        POP = next(float(i["fcstValue"]) for i in items if i["category"] == "POP" and i["fcstTime"].startswith(target_hour))
        return TMP, POP
    except Exception as e:
        return None, None

def judge(temp, rain_prob):
    reasons = []
    if temp is None or rain_prob is None:
        return "데이터 수집 실패(네트워크 또는 API 오류)"
    if not (15 <= temp <= 32):
        reasons.append("기온이 15~32도가 아님")
    if rain_prob is not None and rain_prob > 30:
        reasons.append("강수확률이 30% 이하가 아님")
    if not reasons:
        return "오늘은 야외수업 할 수 있어요!"
    else:
        return "아쉽지만 오늘은 야외수업을 못해요. 그 이유는 " + ", ".join(reasons) + " 때문이에요."

with tab2:
    picked_date = st.session_state.get('picked_date', datetime.date.today())
    location_name = st.session_state.get('location_name', "성남시 분당구")
    nx = st.session_state.get('GRID_NX', 127)
    ny = st.session_state.get('GRID_NY', 202)
    base_date = picked_date.strftime("%Y%m%d")

    st.subheader(f"① {location_name} {picked_date} 데이터 판별 결과")
    with st.spinner(f"실시간 데이터 수집 중..."):
        temp, rain_prob = fetch_weather(base_date, nx, ny, base_time="1100", target_hour="12")
        판별 = judge(temp, rain_prob)
        df = pd.DataFrame({
            "장소": [location_name],
            "기온(°C)": [temp],
            "강수확률(%)": [rain_prob],
            "야외수업 판단": [판별]
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.subheader("② 가능/불가능 요약")
        if 판별 == "오늘은 야외수업 할 수 있어요!":
            st.metric("야외수업 가능 일수", "1 일")
        elif 판별.startswith("아쉽지만"):
            st.metric("야외수업 가능 일수", "0 일")
        else:
            st.warning("판별 데이터를 정상적으로 불러올 수 없습니다.")

with tab3:
    st.subheader("이번 주(월~일) 야외수업 / 점심시간 운동장 가능 요일")
    # 기준: 선택된 지역, 이번 주 월요일~일요일
    nx = st.session_state.get('GRID_NX', 127)
    ny = st.session_state.get('GRID_NY', 202)
    location_name = st.session_state.get('location_name', "성남시 분당구")
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(7)]

    status_list = []
    for d in week_dates:
        base_date = d.strftime("%Y%m%d")
        # 12시 예보(점심): 11:00 발표를 기준으로 12시 값 사용
        temp, rain_prob = fetch_weather(base_date, nx, ny, base_time="1100", target_hour="12")
        can_class = "O" if (temp is not None and rain_prob is not None and 15 <= temp <= 32 and rain_prob <= 30) else "X"
        # 점심시간 운동장(야외활동) 가능 여부 (동일 기준)
        can_lunch = "가능" if can_class == "O" else "불가능"

        status_list.append({
            "날짜": d.strftime("%m/%d"),
            "요일": ["월","화","수","목","금","토","일"][d.weekday()],
            "기온(°C)": temp,
            "강수확률(%)": rain_prob,
            "야외수업": can_class,
            "점심시간 운동장": can_lunch
        })

    df_week = pd.DataFrame(status_list)
    st.dataframe(df_week, use_container_width=True, hide_index=True)
