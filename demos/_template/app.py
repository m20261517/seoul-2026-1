import io
import requests
import pandas as pd
import streamlit as st

# API Keys (노출 주의)
WEATHER_API_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
DUST_API_KEY    = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"

st.set_page_config(
    page_title="야외수업 가능 날씨 앱 (실시간 API 연동)",
    page_icon="📊",
    layout="wide",
)

st.title("📊 야외수업 가능 날씨 앱 (실시간 API)")
st.caption("실시간 기상/미세먼지 API 데이터를 사용하여 서울의 야외수업 가능여부를 바로 판별합니다.")

def fetch_weather_and_dust_seoul():
    # 서울 위도/경도
    lat, lon = 37.5665, 126.9780
    url_weather = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
    url_dust = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={DUST_API_KEY}"

    # 날씨
    try:
        res_w = requests.get(url_weather, timeout=3)
        dat_w = res_w.json()
        temp = dat_w["main"]["temp"]
        rain_prob = dat_w.get("rain", {}).get("1h", 0)
        if rain_prob is None:
            rain_prob = 0
    except Exception as e:
        temp, rain_prob = None, None

    # 미세먼지
    try:
        res_d = requests.get(url_dust, timeout=3)
        dat_d = res_d.json()
        if "list" in dat_d and len(dat_d["list"]) > 0:
            dust_value = dat_d["list"][0]["components"].get("pm10", None)
        else:
            dust_value = None
    except Exception as e:
        dust_value = None

    return temp, rain_prob, dust_value

def dust_is_ok(val):
    try:
        if val is None: return False
        if isinstance(val, (int, float)):
            return val <= 80
        if isinstance(val, str):
            v = val.strip()
            if v.isdigit():
                return int(v) <= 80
            if v in ["좋음", "보통"]:
                return True
        return False
    except:
        return False

def judge(temp, rain_prob, dust):
    reasons = []
    if temp is None or rain_prob is None or dust is None:
        return "데이터 수집 실패(네트워크/API 오류)"
    if not (15 <= temp <= 32):
        reasons.append("기온이 15~32도가 아니")
    if not dust_is_ok(dust):
        reasons.append("미세먼지가 보통(80)이하가 아니")
    if rain_prob is not None and rain_prob > 30:
        reasons.append("강수확률이 30% 이하가 아니")
    if not reasons:
        return "오늘은 야외수업 할 수 있어요!"
    else:
        s = "·".join(reasons)
        return f"아쉽지만 오늘은 야외수업을 못해요. 그 이유는 {s} 때문이에요."

st.subheader("① 서울 실시간 데이터 수집 및 판별 결과")

with st.spinner("실시간 데이터 수집 중 (서울)..."):
    temp, rain_prob, dust = fetch_weather_and_dust_seoul()
    판별 = judge(temp, rain_prob, dust)
    df = pd.DataFrame({
        "장소": ["서울"],
        "기온(°C)": [temp],
        "강수량(mm/h)": [rain_prob],
        "미세먼지(㎍/㎥)": [dust],
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
