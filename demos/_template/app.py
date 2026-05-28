import requests
import pandas as pd
import streamlit as st
import datetime
from urllib.parse import quote

# ==========================================
# 1. API 키 및 지역 설정 (경기도 주요 모든 시/군 추가)
# ==========================================
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe='')

# 경기도 주요 시/군 행정표준코드 및 기상청 격자 좌표(nx, ny)
AREA_NO = {
    "수원시": "4111000000", "성남시": "4113500000", "고양시": "4128000000",
    "용인시": "4146000000", "부천시": "4119000000", "안산시": "4127000000",
    "안양시": "4117000000", "남양주시": "4136000000", "화성시": "4159000000",
    "평택시": "4122000000", "의정부시": "4115000000", "시흥시": "4139000000",
    "파주시": "4148000000", "김포시": "4157000000", "광명시": "4121000000",
    "광주시": "4161000000", "군포시": "4141000000", "오산시": "4137000000",
    "이천시": "4150000000", "양주시": "4163000000", "안성시": "4155000000",
    "구리시": "4131000000", "포천시": "4165000000", "의왕시": "4143000000",
    "하남시": "4145000000", "여주시": "4167000000", "동두천시": "4125000000",
    "과천시": "4129000000", "가평군": "4182000000", "양평군": "4183000000",
    "연천군": "4180000000"
}

LOCATIONS = {
    "수원시": (60, 121), "성남시": (62, 123), "고양시": (57, 128),
    "용인시": (62, 120), "부천시": (56, 125), "안산시": (58, 121),
    "안양시": (59, 123), "남양주시": (64, 128), "화성시": (57, 119),
    "평택시": (61, 114), "의정부시": (61, 130), "시흥시": (57, 123),
    "파주시": (56, 131), "김포시": (55, 128), "광명시": (58, 125),
    "광주시": (65, 123), "군포시": (59, 122), "오산시": (62, 118),
    "이천시": (68, 119), "양주시": (61, 131), "안성시": (65, 115),
    "구리시": (62, 127), "포천시": (64, 134), "의왕시": (60, 122),
    "하남시": (64, 126), "여주시": (71, 121), "동두천시": (61, 134),
    "과천시": (60, 124), "가평군": (69, 133), "양평군": (69, 125),
    "연천군": (58, 138)
}

# ==========================================
# 2. 데이터 수집 함수 (미세먼지 제거됨)
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
    except Exception:
        return {h: None for h in target_hours}, {h: None for h in target_hours}

# ==========================================
# 3. 장소 추천 핵심 알고리즘
# ==========================================
def judge_lunch(tmp_dict, pop_dict):
    temps = [tmp_dict.get(h) for h in ["12", "13"] if tmp_dict.get(h) is not None]
    pops = [pop_dict.get(h) for h in ["12", "13"] if pop_dict.get(h) is not None]

    if not temps or not pops:
        return "정보없음", "unknown", "아직 기온과 강수확률 예보가 발표되지 않았어요."

    # 1순위 (최우선 안전 조건): 기온이 12도 미만이거나 30도 초과일 때 -> 무조건 교실
    if any(t < 12 or t > 30 for t in temps):
        return "교실", "classroom", "기온이 너무 춥거나 더워서 실내 활동이 안전해요."

    # 2순위: 기온은 적절(12~30도)하지만 비가 올 확률이 30%를 초과할 때 -> 필로티
    if any(p > 30 for p in pops):
        return "필로티", "piloti", "비 소식이 있어서 비를 피할 수 있는 곳이 좋아요."

    # 3순위: 기온도 12~30도로 적절하고 강수확률도 30% 이하일 때 -> 운동장
    return "운동장", "playground", "기온과 날씨 모두 야외 활동하기에 아주 완벽해요!"

def calc_lunch_summary(tmp_dict, pop_dict):
    temps = [t for t in [tmp_dict.get('12'), tmp_dict.get('13')] if t is not None]
    pops = [p for p in [pop_dict.get('12'), pop_dict.get('13')] if p is not None]
    temp_avg = round(sum(temps)/len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

# ==========================================
# 4. Streamlit UI 렌더링
# ==========================================
st.set_page_config(
    page_title="점심시간 어디서 놀까?",
    page_icon="🌤️",
    layout="wide"
)

st.title("🌤️ 점심시간 어디서 놀까?")
st.caption("기온과 강수확률 예보를 바탕으로 안전한 점심시간 놀이 장소와 놀이를 추천합니다.")

tab1, tab2 = st.tabs(["지역/주간 선택", "평일 점심시간 장소 추천"])

# --- 탭 1: 지역 선택 ---
with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 내 지역을 선택하세요", list(LOCATIONS.keys()))
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]
    
    st.write("이번 주 평일(월~금):", " ~ ".join([week_dates[0].strftime("%Y-%m-%d"), week_dates[-1].strftime("%Y-%m-%d")]))
    st.session_state["location_name"] = location_name
    st.session_state["week_dates"] = week_dates

# --- 탭 2: 추천 결과 및 오늘 알림 ---
with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        area_no = AREA_NO.get(location_name)
        
        results = []
        data_found = False
        
        # 오늘 날짜 데이터를 담을 변수들
        today_place = ""
        today_status_code = "unknown"
        today_reason = ""
        today_tmp_dict = None
        
        with st.spinner(f"{location_name} 평일 점심 예보 확인 중..."):
            for d in week_dates:
                base_date = d.strftime("%Y%m%d")
                tmp_dict, pop_dict = fetch_weather(base_date, nx, ny, base_time="1100", target_hours=["12","13"])
                is_today = (d == datetime.date.today())
                
                temp_dict_show = tmp_dict.copy()
                
                # 오늘 데이터 보정 (11시 이전 조회 시 임시값)
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
                    "점심 기온(°C)": temp_avg,
                    "비 올 확률(%)": pop_max,
                    "자외선(UV)": uv_index if uv_index else "정보없음",
                    "추천 장소": place,
                    "판정 이유": reason_str
                })
                
                if is_today:
                    today_place, today_status_code, today_reason = place, status_code, reason_str
                    
        # 주간 예보 표 (DataFrame)
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        if not data_found:
            st.info("기상청 일기예보 발표(11시경) 후에 상세 안내를 드릴 수 있습니다.")
            
        # ==========================================
        # ★ 오늘 점심시간 장소 알림 및 추천 놀이 UI ★
        # ==========================================
        st.markdown("---")
        st.subheader("📢 오늘 점심시간 놀이 안내")
        
        if today_status_code == "unknown":
            st.info("오늘 정보가 아직 공개되지 않았어요.")
            
        elif today_status_code == "playground":
            st.success("### 🏃 야외활동 최고! 오늘은 [ 운동장 ] 으로 나가요!")
            st.write(f"**이유:** {today_reason}")
            
            st.write("#### 💡 추천 놀이")
            c1, c2, c3 = st.columns(3)
            with c1: st.button("⚽ 축구 / 발야구", use_container_width=True)
            with c2: st.button("🛝 놀이터 이용", use_container_width=True)
            with c3: st.button("🏃 술래잡기", use_container_width=True)
                
            st.info("🚨 **안전 수칙**\n- 운동장이 더울 땐 모자를 쓰고 물을 꼭 마셔요!\n- 놀이기구에서 친구를 밀지 않도록 주의해요!")
            
        elif today_status_code == "piloti":
            st.warning("### ☂️ 비 소식이 있어요. 오늘은 [ 필로티 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            st.write("#### 💡 추천 놀이")
            c1, c2, c3 = st.columns(3)
            with c1: st.button("🏐 피구", use_container_width=True)
            with c2: st.button("🪢 단체 줄넘기", use_container_width=True)
            with c3: st.button("🪙 제기차기 / 수건돌리기", use_container_width=True)
                
            st.info("🚨 **안전 수칙**\n- 주변에 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!\n- 기둥에 부딪히지 않도록 조심해요!")
            
        elif today_status_code == "classroom":
            st.error("### 🌡️ 날씨가 궂어요. 안전을 위해 오늘은 [ 교실 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            st.write("#### 💡 추천 놀이")
            c1, c2, c3 = st.columns(3)
            with c1: st.button("🎲 보드게임", use_container_width=True)
            with c2: st.button("⚪ 공기놀이", use_container_width=True)
            with c3: st.button("🔍 교실 보물찾기", use_container_width=True)
                
            st.info("🚨 **안전 수칙**\n- 교실 안에서는 절대 뛰지 않아요!\n- 책상이나 의자 모서리에 부딪히지 않도록 조심해요!")
            
        if today_tmp_dict:
            st.caption(f"※ 오늘 예상 기온 (12시/13시) : {today_tmp_dict.get('12')}°C / {today_tmp_dict.get('13')}°C")
    else:
        st.info("좌측 탭에서 지역을 먼저 선택해주세요.")
