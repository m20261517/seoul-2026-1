import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')

LOCATIONS = {
    "수원시 영통구": (60, 121),
    "수원시 권선구": (60, 121),
    "수원시 장안구": (60, 121),
    "수원시 팔달구": (60, 121),
    "성남시 중원구": (127, 202),
    "성남시 분당구": (127, 202),
    "성남시 수정구": (127, 202),
}

AREA_NO = {
    "성남시 분당구": "4113552000",
    "성남시 중원구": "4113551000",
    "성남시 수정구": "4113550000",
    "수원시 영통구": "4111763000",
    "수원시 장안구": "4111156500",
    "수원시 권선구": "4111552000",
}

# 1. 측정소 명 매핑 (미세먼지)
STATION_NAMES = {
    "수원시 영통구": "영통동",
    "수원시 권선구": "고색동",
    "수원시 장안구": "정자동",
    "수원시 팔달구": "인계동",
    "성남시 중원구": "상대원동",
    "성남시 분당구": "수내동",
    "성남시 수정구": "단대동",
}

def get_safe_base_datetime():
    now = datetime.datetime.now()
    if now.hour < 5:
        base_date = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
        base_time = "2300"
    else:
        base_date = now.strftime("%Y%m%d")
        base_time = "0500"
    return base_date, base_time

# 2. 단기예보 날씨 fetch (5일분 미리 받아 날짜별 추출)
def fetch_weather_week(nx, ny):
    base_date, base_time = get_safe_base_datetime()
    url = (
        f"http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={ENCODED_KEY}&numOfRows=1000&pageNo=1&dataType=JSON"
        f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )
    weather_data = {}
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        for item in items:
            f_date = item["fcstDate"]
            f_time = item["fcstTime"][:2]
            cat = item["category"]
            if f_time in ["12", "13"] and cat in ["TMP", "POP"]:
                if (f_date, f_time) not in weather_data:
                    weather_data[(f_date, f_time)] = {}
                weather_data[(f_date, f_time)][cat] = float(item["fcstValue"])
        return weather_data
    except Exception:
        return {}

# 3. 미세먼지 (에어코리아) - stationName 매핑
def get_air_quality(station_name):
    url = (
        f"http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
        f"?serviceKey={SERVICE_KEY}&returnType=json"
        f"&numOfRows=1&pageNo=1"
        f"&stationName={station_name}"
        f"&dataTerm=DAILY&ver=1.3"
    )
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]
        val = items[0].get("pm10Value")
        grade = items[0].get("pm10Grade")
        dt = items[0].get("dataTime")
        return val, grade, dt
    except Exception:
        return None, None, None

def dust_grade_to_text(grade):
    g = str(grade)
    return {"1": "좋음", "2": "보통", "3": "나쁨", "4": "매우나쁨"}.get(g, "정보없음")

# 4. 자외선지수 (06시 기준으로만)
def get_uv_index(area_no):
    today_06 = datetime.datetime.now().strftime("%Y%m%d") + "06"
    url = (
        f"http://apis.data.go.kr/1360000/LivingWthrIdxServiceV4/getUVIdxV4"
        f"?serviceKey={SERVICE_KEY}&areaNo={area_no}&time={today_06}&dataType=JSON"
    )
    try:
        res = requests.get(url, timeout=5)
        items = res.json()["response"]["body"]["items"]["item"]
        return items[0].get("today")
    except Exception:
        return None

def judge_lunch(tmp_dict, pop_dict, pm10_grade):
    if all(tmp_dict.get(h) is None or pop_dict.get(h) is None for h in ["12", "13"]):
        return "일기예보 발표 후에 안내드릴게요", False, "아직 기온과 강수확률 예보가 없습니다."
    if pm10_grade in ["3", "4", 3, 4]:
        return "나가면 안돼요: 미세먼지 나쁨 이상", False, "미세먼지가 나쁨 또는 매우나쁨이에요. 실내활동 추천!"
    reasons = []
    for h in ["12", "13"]:
        temp = tmp_dict.get(h)
        pop = pop_dict.get(h)
        if temp is None or pop is None:
            continue
        if temp is not None and not (12 <= temp <= 30):
            reasons.append(f"{h}시 기온 {temp}°C (예상범위 아님)")
        if pop is not None and pop > 30:
            reasons.append(f"{h}시 강수확률 {pop}% (30% 초과)")
    if not reasons and all(tmp_dict.get(h) is not None and pop_dict.get(h) is not None for h in ["12", "13"]):
        return "나가도 돼요!", True, "오늘 점심 야외활동에 좋은 조건입니다!"
    elif not reasons:
        return "일기예보 발표 후에 안내드릴게요", False, "아직 예보가 확정되지 않았어요."
    else:
        return "나가면 안돼요: " + "; ".join(reasons), False, "; ".join(reasons) + " 때문에 불가"

def calc_lunch_summary(tmp_dict, pop_dict):
    temps = [t for t in [tmp_dict.get('12'), tmp_dict.get('13')] if t is not None]
    pops = [p for p in [pop_dict.get('12'), pop_dict.get('13')] if p is not None]
    temp_avg = round(sum(temps)/len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

# Streamlit UI
st.set_page_config(
    page_title="점심시간에 나가도 돼요?",
    page_icon="🌤️",
    layout="wide"
)
st.title("🌤️ 점심시간에 나가도 돼요?")
st.caption("경기도 각 도시(구)의 평일(월~금) 점심(12~13시) 운동장/야외활동 허용 앱 - 기상청/에어코리아/자외선 실예보 연동")

tab1, tab2 = st.tabs(["도시/주간 선택", "평일 점심시간 운동장 가능 여부(월~금)"])

with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 도시/구를 선택하세요", LOCATIONS.keys(), index=list(LOCATIONS.keys()).index("성남시 분당구"))
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]
    st.write("이번 주(월~금):", " ~ ".join([week_dates[0].strftime("%Y-%m-%d"), week_dates[-1].strftime("%Y-%m-%d")]))
    st.session_state["location_name"] = location_name
    st.session_state["week_dates"] = week_dates

with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        area_no = AREA_NO.get(location_name)
        station_name = STATION_NAMES.get(location_name, "수내동")
        # 날씨/미세먼지/자외선 데이터는 한 번만!
        weather_data = fetch_weather_week(nx, ny)
        pm10, pm10_grade, pm10_time = get_air_quality(station_name)
        uv_index_today = get_uv_index(area_no) if area_no else None

        results = []
        data_found = False
        today_result_str = ""
        today_possible = None
        today_reason = ""
        today_tmp_dict = None
        today_pop_dict = None

        for i, d in enumerate(week_dates):
            f_date = d.strftime("%Y%m%d")
            is_today = (d == datetime.date.today())
            # 날씨 데이터 날짜+시간별로 분할
            tmp_dict = {h: weather_data.get((f_date, h), {}).get("TMP") for h in ["12", "13"]}
            pop_dict = {h: weather_data.get((f_date, h), {}).get("POP") for h in ["12", "13"]}
            temp_avg, pop_max = calc_lunch_summary(tmp_dict, pop_dict)
            # 사유/운동장 판단
            if is_today:
                pm10_val = pm10
                pm10_grade_val = pm10_grade
                uv_val = uv_index_today
            else:
                pm10_val = "당일제공"
                pm10_grade_val = "당일제공"
                uv_val = "당일제공"

            result_str, possible, reason_str = judge_lunch(tmp_dict, pop_dict, pm10_grade if is_today else None)
            
            if temp_avg is not None and pop_max is not None:
                data_found = True

            pm10_str = f"{pm10_val} ({dust_grade_to_text(pm10_grade_val)})" if (pm10_val not in [None, '', "당일제공"]) else str(pm10_val)
            uv_str = uv_val if uv_val else "정보없음"
            results.append({
                "날짜": d.strftime("%Y-%m-%d"),
                "요일": "월화수목금"[d.weekday()],
                "점심시간 기온(°C)": temp_avg,
                "점심시간 강수확률(%)": pop_max,
                "미세먼지(PM10)": pm10_str,
                "자외선지수(UV)": uv_str,
                "점심시간 운동장": "가능" if possible else "불가",
                "사유": result_str,
                "설명": reason_str
            })

            if is_today:
                today_result_str, today_possible, today_reason = result_str, possible, reason_str
                today_tmp_dict = tmp_dict.copy()
                today_pop_dict = pop_dict.copy()

        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not data_found:
            st.info("일기예보 발표 후에 안내드릴게요")
        st.markdown("---")
        st.subheader("오늘 점심시간 알림")
        if today_possible is None or today_result_str == "":
            st.info("오늘 정보가 아직 공개되지 않았어요.")
        elif today_possible:
            st.success("오늘은 점심시간에 나가도 돼요! 🎉")
            st.caption(f"사유: {today_reason}")
        else:
            st.error("오늘은 점심시간에 나갈 수 없어요. 😭")
            st.caption(f"사유: {today_reason}")
        if today_tmp_dict:
            st.caption(f"오늘 12/13시 기온: {today_tmp_dict.get('12')}°C / {today_tmp_dict.get('13')}°C")
    else:
        st.info("좌측 탭에서 도시를 선택해주세요.")
