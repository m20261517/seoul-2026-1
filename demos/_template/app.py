import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')

# 경기도 코드 (중기예보용)
MID_LAND_ID = "11B00000"  # 경기도
REGION_LABEL = "경기도"

st.set_page_config(
    page_title="점심시간에 나가도 돼요? (중기예보)",
    page_icon="🌤️",
    layout="wide"
)

st.title("🌤️ 점심시간에 나가도 돼요?")
st.caption("경기도 한 주간(3~7일후) 중기예보 - 오전·오후 강수확률과 하늘상태")

def get_midland_base_date_and_time():
    now = datetime.datetime.now()
    # 기상청 중기 예보 base(06, 18시) 시간 맞추기
    if now.hour < 6:
        base = (now - datetime.timedelta(days=1)).strftime("%Y%m%d") + "1800"
    elif now.hour < 18:
        base = now.strftime("%Y%m%d") + "0600"
    else:
        base = now.strftime("%Y%m%d") + "1800"
    return base

def fetch_midland():
    tmFc = get_midland_base_date_and_time()
    url = (f"http://apis.data.go.kr/1360000/MidLandForecastInfoService/getMidLandFcst"
           f"?serviceKey={ENCODED_KEY}&dataType=JSON&regId={MID_LAND_ID}&tmFc={tmFc}")
    try:
        res = requests.get(url, timeout=5)
        item = res.json()["response"]["body"]["items"]["item"][0]
        today = datetime.date.today()
        days = []
        # 기상청 중기예보는 3~10일후까지 나오며, 월~금만 표시
        for i, col in enumerate(["3", "4", "5", "6", "7"]):  # 월~금
            date = today + datetime.timedelta(days=i+2)  # today+2: 3일후 == 월, ... 7일후 == 금
            days.append({
                "날짜": date.strftime("%Y-%m-%d"),
                "요일": "월화수목금"[i],
                "오전 강수확률(%)": item.get(f"rnSt{col}Am"),
                "오후 강수확률(%)": item.get(f"rnSt{col}Pm"),
                "오전 하늘": item.get(f"wf{col}Am"),
                "오후 하늘": item.get(f"wf{col}Pm"),
            })
        return pd.DataFrame(days)
    except Exception as e:
        st.error("중기예보 데이터를 가져오는 도중 오류가 발생했습니다.")
        return pd.DataFrame([])

tab1, tab2 = st.tabs(["예보 안내", "이번 주(월~금) 예보 표"])

with tab1:
    st.markdown(
        """
        - 이 서비스는 **기상청 중기예보(도 단위, 3~10일후)**를 사용합니다.
        - 오전(6~12시), 오후(12~18시) 강수확률과 하늘상태만 제공됩니다.
        - 개인/학교 주소 등 세부 지역별 1시간 단위 예보는 기상청 정책상 불가(최대 2~3일치만 단기)입니다.
        - 아래 표에서 \"오후\" 값이 점심 시간 야외활동 참고용입니다.
        """
    )

with tab2:
    df = fetch_midland()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.info("※ 오후(12~18시) 강수확률이 30% 이하고, 하늘이 '맑음' 등일 때 야외활동에 더 적합합니다.")
    else:
        st.warning("중기예보 데이터가 없습니다. 잠시 후 다시 시도해 주세요.")
