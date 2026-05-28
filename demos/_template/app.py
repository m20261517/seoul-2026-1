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
    # 필요 지역 계속 추가
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
# 2. 데이터 수집 함수 (단기예보, 자외선)
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
            pop = next((float(i["fcstValue"]) for i in items if i["category"] == "POP" and i["fcstTime"].startswith(h)), None)
            TMPs[h] = tmp
            POPs[h] = pop
        return TMPs, POPs
    except Exception as e:
        return {h: None for h in target_hours}, {h: None for h in target_hours}

# ==========================================
# 3. 점심시간 장소 판정 로직 (핵심)
# ==========================================
def judge_lunch(tmp_dict, pop_dict):
    # 12시, 13시 중 유효한 데이터만 추출
    temps = [tmp_dict.get(h) for h in ["12", "13"] if tmp_dict.get(h) is not None]
    pops = [pop_dict.get(h) for h in ["12", "13"] if pop_dict.get(h) is not None]

    # 예보 데이터가 아예 없는 경우
    if not temps or not pops:
        return "알 수 없음", "unknown", "아직 기온과 강수확률 예보가 없습니다."

    # 1순위: 교실 (기온이 12도 미만이거나 30도를 초과하면 비가 오든 안 오든 무조건 실내)
    for t in temps:
        if t < 12 or t > 30:
            return "교실", "classroom", f"기온({t}도)이 너무 춥거나 더워서 실내 활동이 안전해요."

    # 2순위: 필로티 (기온은 12~30도 사이로 적절한데, 비가 올 확률이 30%를 초과하는 경우)
    for p in pops:
        if p > 30:
            return "필로티", "piloti", f"비가 올 확률({p}%)이 있어서 비를 피할 수 있는 곳이 좋아요."

    # 3순위: 운동장 (온도 적절 12~30도, 비 올 확률 30% 이하)
    return "운동장", "playground", "기온과 날씨 모두 야외 활동하기에 아주 완벽해요!"

def calc_lunch_summary(tmp_dict, pop_dict):
    temps = [t for t in [tmp_dict.get('12'), tmp_dict.get('13')] if t is not None]
    pops = [p for p in [pop_dict.get('12'), pop_dict.get('13')] if p is not None]
    temp_avg = round(sum(temps)/len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

# ==========================================
# 4. Streamlit UI 구성
# ==========================================
st.set_page_config(
    page_title="점심시간 어디서 놀까?",
    page_icon="🌤️",
    layout="wide"
)
st.title("🌤️ 점심시간 어디서 놀까?")
st.caption("경기도 각 도시의 평일 점심(12~13시) 기상 예보 기반 점심시간 활동 장소 추천 앱")

tab1, tab2 = st.tabs(["도시/주간 선택", "평일 점심시간 장소 추천(월~금)"])

with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 도시/구를 선택하세요", LOCATIONS.keys())
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
        
        results = []
        data_found = False
        
        # 오늘 날짜 상태 저장을 위한 변수
        today_place = ""
        today_status_code = "unknown"
        today_reason = ""
        today_tmp_dict = None
        
        with st.spinner(f"{location_name} 평일 점심 예보 확인 중..."):
            for i, d in enumerate(week_dates):
                base_date = d.strftime("%Y%m%d")
                tmp_dict, pop_dict = fetch_weather(base_date, nx, ny, base_time="1100", target_hours=["12","13"])
                is_today = (d == datetime.date.today())
                temp_dict_show = tmp_dict.copy()
                
                # 오전(11시 이전)에 조회할 경우 임시 값 처리
                if is_today:
                    if tmp_dict.get("12") is None: temp_dict_show["12"] = 22.0
                    if tmp_dict.get("13") is None: temp_dict_show["13"] = 22.0
                    today_tmp_dict = temp_dict_show.copy()

                temp_avg, pop_max = calc_lunch_summary(temp_dict_show if is_today else tmp_dict, pop_dict)
                place, status_code, reason_str = judge_lunch(temp_dict_show if is_today else tmp_dict, pop_dict)
                uv_index = get_uv_index(area_no, base_date + "12") if area_no else None
                
                if temp_avg is not None and pop_max is not None:
                    data_found = True
                    
                results.append({
                    "날짜": d.strftime("%Y-%m-%d"),
                    "요일": "월화수목금"[d.weekday()],
                    "기온(°C)": temp_avg,
                    "강수확률(%)": pop_max,
                    "자외선(UV)": uv_index if uv_index else "정보없음",
                    "추천 장소": place,
                    "이유": reason_str
                })
                
                if is_today:
                    today_place, today_status_code, today_reason = place, status_code, reason_str
                    
        # 1. 주간 데이터 표 렌더링
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not data_found:
            st.info("일기예보 발표 후에 안내드릴게요")
            
        st.markdown("---")
        
        # 2. 오늘 점심시간 하단 알림 UI 렌더링
        st.subheader("📢 오늘 점심시간 놀이 안내")
        
        if today_status_code == "unknown":
            st.info("오늘 정보가 아직 공개되지 않았어요.")
            
        elif today_status_code == "playground":
            st.success("## 🏃 오늘은 [ 운동장 ] 에서 신나게 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            st.write("### 💡 추천 놀이")
            c1, c2, c3 = st.columns(3)
            c1.markdown("#### ⚽ 축구 / 발야구")
            c2.markdown("#### 🛝 놀이터 이용")
            c3.markdown("#### 🏃 술래잡기")
            
            st.info("🚨 **안전 수칙**\n* 운동장이 더울 땐 모자를 쓰고 물을 꼭 마셔요!\n* 놀이기구에서 친구를 밀지 않도록 주의해요!")
            
        elif today_status_code == "piloti":
            st.warning("## ☂️ 오늘은 비를 피할 수 있는 [ 필로티 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            st.write("### 💡 추천 놀이")
            c1, c2, c3 = st.columns(3)
            c1.markdown("#### 🏐 피구")
            c2.markdown("#### 🪢 단체 줄넘기")
            c3.markdown("#### 🪙 제기차기 / 수건돌리기")
            
            st.info("🚨 **안전 수칙**\n* 주변에 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!\n* 기둥에 부딪히지 않도록 조심해요!")
            
        elif today_status_code == "classroom":
            st.error("## 🌡️ 오늘은 안전을 위해 [ 교실 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            st.write("### 💡 추천 놀이")
            c1, c2, c3 = st.columns(3)
            c1.markdown("#### 🎲 보드게임")
            c2.markdown("#### ⚪ 공기놀이")
            c3.markdown("#### 🔍 교실 보물찾기")
            
            st.info("🚨 **안전 수칙**\n* 교실 안에서는 절대 뛰지 않아요!\n* 책상이나 의자 모서리에 부딪히지 않도록 조심해요!")
            
        if today_tmp_dict:
            st.caption(f"※ 오늘 12시/13시 기온: {today_tmp_dict.get('12')}°C / {today_tmp_dict.get('13')}°C")
    else:
        st.info("좌측 탭에서 도시를 선택해주세요.")
