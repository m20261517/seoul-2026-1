import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')

LOCATIONS = {
    "수원시": (60, 121),
    "성남시": (127, 202),
    "고양시": (56, 128),
    "용인시": (66, 120),
    "부천시": (56, 123),
    "안산시": (56, 119),
    "화성시": (59, 119),
    "남양주시": (73, 134),
    "평택시": (62, 114),
    "의정부시": (61, 130),
    "파주시": (54, 131),
    "광명시": (58, 125),
    "오산시": (62, 118),
    "군포시": (58, 122),
    "이천시": (72, 122),
    "하남시": (70, 127),
    "안성시": (75, 115),
    "김포시": (55, 128),
    "시흥시": (56, 122),
    "광주시": (71, 125),
    "양주시": (63, 134),
    "여주시": (82, 126),
    "구리시": (69, 128),
    "과천시": (59, 126),
    "포천시": (69, 138),
    "의왕시": (60, 123),
    "가평군": (77, 137),
    "양평군": (78, 130)
}

st.set_page_config(
    page_title="점심시간에 나가도 돼요?",
    page_icon="🌤️",
    layout="wide"
)

st.title("🌤️ 점심시간에 나가도 돼요?")
st.caption("경기도 각 도시의 평일(월~금) 점심(12~13시) 기상청 예보 기반, 운동장/야외활동 허용 여부 앱")

tab1, tab2 = st.tabs(["도시/주간 선택", "평일 점심시간 운동장 가능 여부(월~금)"])

with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 도시를 선택하세요", LOCATIONS.keys())
    # 이번 주 월요일 계산
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]  # 월(0)~금(4)
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

def calc_lunch_summary(tmp_dict, pop_dict):
    temps = [t for t in [tmp_dict['12'], tmp_dict['13']] if t is not None]
    pops = [p for p in [pop_dict['12'], pop_dict['13']] if p is not None]
    temp_avg = round(sum(temps)/len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

def judge_lunch(tmp_dict, pop_dict):
    # 12, 13시 모두 데이터 없으면 안내만 표시
    if all(tmp_dict[h] is None or pop_dict[h] is None for h in ["12", "13"]):
        return "일기예보 발표 후에 안내드릴게요", False
    reasons = []
    for h in ["12", "13"]:
        temp = tmp_dict[h]
        pop = pop_dict[h]
        if temp is None or pop is None:
            continue  # 상세 '데이터 수집 실패' 표기 X
        if temp is not None and not (12 <= temp <= 30):
            reasons.append(f"{h}시 기온({temp}도)이 12~30도 아님")
        if pop is not None and pop > 30:
            reasons.append(f"{h}시 강수확률({pop}%) > 30%")
    # 조건 만족
    if not reasons and all(tmp_dict[h] is not None and pop_dict[h] is not None for h in ["12", "13"]):
        return "나가도 돼요!", True
    elif not reasons:
        return "일기예보 발표 후에 안내드릴게요", False
    else:
        return "나가면 안돼요: " + "; ".join(reasons), False

with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        results = []
        data_found = False
        with st.spinner(f"{location_name} 평일 점심 예보 확인 중..."):
            for d in week_dates:
                base_date = d.strftime("%Y%m%d")
                tmp_dict, pop_dict = fetch_weather(base_date, nx, ny, base_time="1100", target_hours=["12","13"])
                temp_avg, pop_max = calc_lunch_summary(tmp_dict, pop_dict)
                result_str, possible = judge_lunch(tmp_dict, pop_dict)
                # 안내 문구만 남았으면 data_found = True로 처리
                if temp_avg is not None and pop_max is not None:
                    data_found = True
                results.append({
                    "날짜": d.strftime("%Y-%m-%d"),
                    "요일": "월화수목금"[d.weekday()],
                    "점심시간 기온(°C)": temp_avg,
                    "점심시간 강수확률(%)": pop_max,
                    "점심시간 운동장": "가능" if possible else "불가",
                    "사유": result_str
                })
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
        enable_count = sum([x["점심시간 운동장"] == "가능" for x in results])
        st.metric("이번 주 평일 점심시간 운동장 가능 일수", f"{enable_count} 일")
        if not data_found:
            st.info("일기예보 발표 후에 안내드릴게요")
    else:
        st.info("좌측 탭에서 도시를 선택해주세요.")
