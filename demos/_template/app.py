import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

# ==========================================
# 1. API 키 및 지역 설정
# ==========================================
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')

AREA_NO = {
    "성남시 분당구": "4113552000",
    "성남시 중원구": "4113551000",
    "성남시 수정구": "4113550000",
    "수원시 영통구": "4111763000",
    "수원시 장안구": "4111156500",
    "수원시 권선구": "4111552000",
}

LOCATIONS = {
    "수원시 영통구": (60, 121),
    "수원시 권선구": (60, 121),
    "수원시 장안구": (60, 121),
    "수원시 팔달구": (60, 121),
    "성남시 중원구": (127, 202),
    "성남시 분당구": (127, 202),
    "성남시 수정구": (127, 202),
}

# ==========================================
# 2. 데이터 수집 함수
# ==========================================
def get_uv_index(area_no, yyyymmddhh):
    url = (
        f"http://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4"
        f"?serviceKey={SERVICE_KEY}&areaNo={area_no}&time={yyyymmddhh}&dataType=JSON"
    )
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        uv_today = items[0].get("today")
        return uv_today
    except Exception:
        return None

def fetch_weather(base_date, nx, ny, base_time="1100", target_hours=["12","13"]):
    url = (
        f"http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={ENCODED_KEY}&numOfRows=100&pageNo=1&dataType=JSON"
        f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )
    TMPs, POPs = {}, {}
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        for h in target_hours:
            tmp = next((float(i["fcstValue"]) for i in items if i["category"] == "TMP" and i["fcstTime"].startswith(h)), None)
            pop = next((float(i["fcstValue"]) for
