import requests
import pandas as pd
import streamlit as st
import datetime
import urllib.parse

# ==========================================
# 1. API 키 설정 및 디코딩
# ==========================================
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
DECODED_KEY = urllib.parse.unquote(SERVICE_KEY)

# 경기도 주요 시/군 행정표준코드 및 기상청 격자 좌표(nx, ny)
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
# 2. 데이터 수집 함수 (기온, 강수확률만 조회)
# ==========================================
def fetch_weather(base_date, nx, ny, base_time="1100", target_hours=["12","13"]):
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": DECODED_KEY,
        "numOfRows": "100",
        "pageNo": "1",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }
    TMPs, POPs = {}, {}
    try:
        res = requests.get(url, params=params, timeout=5)
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
# 3. 점심시간 장소 추천 우선순위 로직
# ==========================================
def judge_lunch(tmp_dict, pop_dict):
    temps = [tmp_dict.get(h) for h in ["12", "13"] if tmp_dict.get(h) is not None]
    pops = [pop_dict.get(h) for h in ["12", "13"] if pop_dict.get(h) is not None]

    if not temps or not pops:
        return "알 수 없음", "unknown", "아직 예보가 발표되지 않았어요."

    # 1순위 (교실): 너무 춥거나(<12도) 너무 더우면(>30도) 비가 오든 안 오든 무조건 실내
    for t in temps:
        if t < 12 or t > 30:
            return "교실", "classroom", f"기온({t}도)이 야외 활동하기에 적합하지 않아 실내가 안전해요."

    # 2순위 (필로티): 기온은 적절하나, 비 소식(강수확률 30% 초과)이 있는 경우
    for p in pops:
        if p > 30:
            return "필로티", "piloti", f"비가 올 확률({p}%)이 있어서 비를 피할 수 있는 곳이 좋아요."

    # 3순위 (운동장): 기온 적절(12~30도)하고 강수확률도 낮을 때 가장 추천
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
st.caption("기온과 강수확률을 바탕으로 안전한 점심시간 놀이 장소를 추천해 드립니다.")

tab1, tab2 = st.tabs(["📍 지역/주간 선택", "📅 평일 점심시간 장소 추천"])

# --- 탭 1: 지역 선택 ---
with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 내 지역을 선택하세요", list(LOCATIONS.keys()))
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]
    st.write(f"**이번 주 평일:** {week_dates[0].strftime('%Y-%m-%d')} ~ {week_dates[-1].strftime('%Y-%m-%d')}")
    st.session_state["location_name"] = location_name
    st.session_state["week_dates"] = week_dates

# --- 탭 2: 결과 확인 및 오늘 알림 ---
with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        
        results = []
        data_found = False
        
        # 오늘 날짜 상태 변수
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
                
                # 11시 이전 조회 시 오늘 데이터 보정
                if is_today:
                    if tmp_dict.get("12") is None: temp_dict_show["12"] = 22.0
                    if tmp_dict.get("13") is None: temp_dict_show["13"] = 22.0
                    today_tmp_dict = temp_dict_show.copy()

                temp_avg, pop_max = calc_lunch_summary(temp_dict_show if is_today else tmp_dict, pop_dict)
                place, status_code, reason_str = judge_lunch(temp_dict_show if is_today else tmp_dict, pop_dict)
                
                if temp_avg is not None and pop_max is not None:
                    data_found = True
                    
                results.append({
                    "날짜": d.strftime("%Y-%m-%d"),
                    "요일": "월화수목금"[d.weekday()],
                    "기온(°C)": temp_avg,
                    "강수확률(%)": pop_max,
                    "추천 장소": place,
                    "판정 이유": reason_str
                })
                
                if is_today:
                    today_place, today_status_code, today_reason = place, status_code, reason_str
                    
        # 주간 예보 표 렌더링
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not data_found:
            st.info("기상청 일기예보 발표(11시경) 후에 상세 안내를 드릴 수 있습니다.")
            
        st.markdown("---")
        
        # ==========================================
        # ★ 하단 알림 및 추천활동/안전수칙 탭 UI ★
        # ==========================================
        st.subheader("📢 오늘 점심시간 활동 안내")
        
        if today_status_code == "unknown":
            st.info("오늘 예보 정보가 아직 공개되지 않았어요.")
            
        elif today_status_code == "playground":
            st.success("## 🏃 야외활동 최고! 오늘은 [ 운동장 ] 으로 나가요!")
            st.write(f"**이유:** {today_reason}")
            
            # 장소에 맞는 추천 활동 & 안전 수칙 탭 생성
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                c1, c2, c3 = st.columns(3)
                with c1: st.button("⚽ 축구 / 발야구", use_container_width=True)
                with c2: st.button("🛝 놀이터 이용", use_container_width=True)
                with c3: st.button("🏃 술래잡기", use_container_width=True)
            with safe_tab:
                st.info("✔️ 운동장이 더울 땐 모자를 쓰고 물을 꼭 마셔요!\n\n✔️ 놀이기구에서 친구를 밀지 않도록 주의해요!")
            
        elif today_status_code == "piloti":
            st.warning("## ☂️ 비 소식이 있어요. 오늘은 [ 필로티 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                c1, c2, c3 = st.columns(3)
                with c1: st.button("🏐 피구", use_container_width=True)
                with c2: st.button("🪢 단체 줄넘기", use_container_width=True)
                with c3: st.button("🪙 제기차기 / 수건돌리기", use_container_width=True)
            with safe_tab:
                st.warning("✔️ 주변에 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!\n\n✔️ 기둥에 부딪히지 않도록 조심해요!")
            
        elif today_status_code == "classroom":
            st.error("## 🌡️ 안전을 위해 오늘은 [ 교실 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                c1, c2, c3 = st.columns(3)
                with c1: st.button("🎲 보드게임", use_container_width=True)
                with c2: st.button("⚪ 공기놀이", use_container_width=True)
                with c3: st.button("🔍 교실 보물찾기", use_container_width=True)
            with safe_tab:
                st.error("✔️ 교실 안에서는 절대 뛰지 않아요!\n\n✔️ 책상이나 의자 모서리에 부딪히지 않도록 조심해요!")
            
        if today_tmp_dict:
            st.caption(f"※ 오늘 예상 기온 (12시/13시): {today_tmp_dict.get('12')}°C / {today_tmp_dict.get('13')}°C")
    else:
        st.info("좌측 탭에서 지역을 먼저 선택해주세요.")
