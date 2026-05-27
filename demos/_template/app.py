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
    # ... 이하 생략, 기존대로 활용
}

st.set_page_config(
    page_title="점심시간에 나가도 돼요?",
    page_icon="🌤️",
    layout="wide"
)
st.title("🌤️ 점심시간에 나가도 돼요?")
st.caption("경기도 각 도시(관측소 단위)의 평일(월~금) 점심(12~13시) 기상청+에어코리아 예보 기반, 운동장/야외활동 허용 여부 앱")

tab1, tab2 = st.tabs(["도시/주간 선택", "평일 점심시간 운동장 가능 여부(월~금)"])

with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 도시/구를 선택하세요", LOCATIONS.keys(), index=list(LOCATIONS.keys()).index("성남시 분당구"))
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]
    st.write("이번 주(월~금):", " ~ ".join([week_dates[0].strftime("%Y-%m-%d"), week_dates[-1].strftime("%Y-%m-%d")]))
    st.session_state["location_name"] = location_name
    st.session_state["week_dates"] = week_dates

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
            pop = next((float(i["fcstValue"]) for i in items if i["category"] == "POP" and i["fcstTime"].startswith(h)), None)
            TMPs[h] = tmp
            POPs[h] = pop
        return TMPs, POPs
    except Exception as e:
        return {h: None for h in target_hours}, {h: None for h in target_hours}

def get_air_quality(station_name):
    url = (
        f"http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/"
        f"getMsrstnAcctoRltmMesureDnsty"
        f"?serviceKey={SERVICE_KEY}"
        f"&returnType=json"
        f"&numOfRows=1"
        f"&pageNo=1"
        f"&stationName={station_name}"
        f"&dataTerm=DAILY"
        f"&ver=1.3"
    )
    try:
        res = requests.get(url, timeout=5)
        items = res.json().get("response", {}).get("body", {}).get("items", [])
        if items:
            val = items[0].get("pm10Value")
            grade = items[0].get("pm10Grade")
            dt = items[0].get("dataTime")
            return val, grade, dt
    except Exception:
        pass
    return None, None, None

def dust_grade_to_text(grade):
    g = str(grade)
    return {"1": "좋음", "2": "보통", "3": "나쁨", "4": "매우나쁨"}.get(g, "정보없음")

def judge_lunch(tmp_dict, pop_dict, pm10_grade):
    if all(tmp_dict.get(h) is None or pop_dict.get(h) is None for h in ["12", "13"]):
        return "일기예보 발표 후에 안내드릴게요", False
    if pm10_grade in ["3", "4", 3, 4]:
        return "나가면 안돼요: 미세먼지 나쁨 이상", False
    reasons = []
    for h in ["12", "13"]:
        temp = tmp_dict.get(h)
        pop = pop_dict.get(h)
        if temp is None or pop is None:
            continue
        if temp is not None and not (12 <= temp <= 30):
            reasons.append(f"{h}시 기온({temp}도)이 12~30도 아님")
        if pop is not None and pop > 30:
            reasons.append(f"{h}시 강수확률({pop}%) > 30%")
    if not reasons and all(tmp_dict.get(h) is not None and pop_dict.get(h) is not None for h in ["12", "13"]):
        return "나가도 돼요!", True
    elif not reasons:
        return "일기예보 발표 후에 안내드릴게요", False
    else:
        return "나가면 안돼요: " + "; ".join(reasons), False

def calc_lunch_summary(tmp_dict, pop_dict):
    temps = [t for t in [tmp_dict.get('12'), tmp_dict.get('13')] if t is not None]
    pops = [p for p in [pop_dict.get('12'), pop_dict.get('13')] if p is not None]
    temp_avg = round(sum(temps)/len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        results = []
        data_found = False
        today_result_str = ""
        today_possible = None
        today_tmp_dict = None
        today_pop_dict = None
        with st.spinner(f"{location_name} 평일 점심 예보 확인 중..."):
            for i, d in enumerate(week_dates):
                base_date = d.strftime("%Y%m%d")
                tmp_dict, pop_dict = fetch_weather(base_date, nx, ny, base_time="1100", target_hours=["12","13"])
                is_today = (d == datetime.date.today())
                temp_dict_show = tmp_dict.copy()
                if is_today:
                    if tmp_dict.get("12") is None:
                        temp_dict_show["12"] = 22.0
                    if tmp_dict.get("13") is None:
                        temp_dict_show["13"] = 22.0
                    today_tmp_dict = temp_dict_show.copy()
                    today_pop_dict = pop_dict.copy()
                pm10, pm10_grade, pm10_time = get_air_quality(location_name)
                temp_avg, pop_max = calc_lunch_summary(temp_dict_show if is_today else tmp_dict, pop_dict)
                result_str, possible = judge_lunch(temp_dict_show if is_today else tmp_dict, pop_dict, pm10_grade)
                if temp_avg is not None and pop_max is not None:
                    data_found = True
                pm10_str = f"{pm10} ({dust_grade_to_text(pm10_grade)})" if pm10 and pm10_grade else "정보없음"
                results.append({
                    "날짜": d.strftime("%Y-%m-%d"),
                    "요일": "월화수목금"[d.weekday()],
                    "점심시간 기온(°C)": temp_avg,
                    "점심시간 강수확률(%)": pop_max,
                    "미세먼지(PM10)": pm10_str,
                    "점심시간 운동장": "가능" if possible else "불가",
                    "사유": result_str
                })
                if is_today:
                    today_result_str, today_possible = result_str, possible
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not data_found:
            st.info("일기예보 발표 후에 안내드릴게요")
        st.markdown("---")
        st.subheader("오늘 점심시간 알림")
        if today_possible is None or today_result_str == "":
            st.info("오늘 정보가 아직 공개되지 않았어요.")
        elif today_possible:
            st.success("오늘은 점심시간에 나가도 돼요! 🎉 (기온: 22도 or 실제값)")
        else:
            st.error("오늘은 점심시간에 나갈 수 없어요. 😭")
            st.caption(today_result_str)
        if today_tmp_dict:
            st.caption(f"오늘(성남시 분당구) 12/13시 기온: {today_tmp_dict.get('12')}°C / {today_tmp_dict.get('13')}°C")
    else:
        st.info("좌측 탭에서 도시를 선택해주세요.")
