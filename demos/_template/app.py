import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

# 🎫 공공데이터포털 API KEY (반드시 본인 발급키로 적용)
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')             # 기상청 API에서 사용

# 기상청 격자 좌표 (성남시 분당구청 부근)
GRID_NX, GRID_NY = 127, 202

st.set_page_config(
    page_title="야외수업 가능 날씨 앱 (공공데이터포털 API)",
    page_icon="📊",
    layout="wide",
)

st.title("📊 야외수업 가능 날씨 앱")
st.caption("공공데이터포털 기상청 실시간 데이터 기반 야외수업 판단")

def fetch_weather():
    # 기준 날짜/시간 설정 (예보는 0200, 0500, ... 등 3시간 간격만 제공)
    now = datetime.datetime.now()
    if now.hour < 5:
        base_time, base_date = "0200", (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
    elif now.hour < 8:
        base_time, base_date = "0500", now.strftime("%Y%m%d")
    elif now.hour < 11:
        base_time, base_date = "0800", now.strftime("%Y%m%d")
    elif now.hour < 14:
        base_time, base_date = "1100", now.strftime("%Y%m%d")
    elif now.hour < 17:
        base_time, base_date = "1400", now.strftime("%Y%m%d")
    elif now.hour < 20:
        base_time, base_date = "1700", now.strftime("%Y%m%d")
    elif now.hour < 23:
        base_time, base_date = "2000", now.strftime("%Y%m%d")
    else:
        base_time, base_date = "2300", now.strftime("%Y%m%d")

    url = (
        "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={ENCODED_KEY}&numOfRows=100&pageNo=1&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={GRID_NX}&ny={GRID_NY}"
    )
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        TMP = next(float(i["fcstValue"]) for i in items if i["category"] == "TMP")
        POP = next(float(i["fcstValue"]) for i in items if i["category"] == "POP")
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

st.subheader("① 성남 실시간 데이터 수집 및 판별 결과")
with st.spinner("실시간 데이터 수집 중 (성남)..."):
    temp, rain_prob = fetch_weather()
    판별 = judge(temp, rain_prob)
    df = pd.DataFrame({
        "장소": ["성남"],
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
