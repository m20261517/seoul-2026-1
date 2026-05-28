import requests
import pandas as pd
import streamlit as st
import datetime
import urllib.parse

# ==========================================
# 1. API 키 설정 및 안전한 디코딩 처리
# ==========================================
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
DECODED_KEY = urllib.parse.unquote(SERVICE_KEY)

# 경기도 주요 시/군 기상청 격자 좌표(nx, ny) 데이터셋
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
# 2. 기상청 API 최적화 및 실시간 시간 계산 로직
# ==========================================
def get_latest_base_datetime():
    """현재 시간을 기준으로 기상청에서 이미 발표된 가장 최신의 단기예보 기준일시를 계산합니다."""
    now = datetime.datetime.now()
    # 단기예보 발표 시간 (각 정시 10분 뒤부터 API 조회가 안정적으로 가능합니다)
    announcements = [2, 5, 8, 11, 14, 17, 20, 23]
    
    for target_hour in reversed(announcements):
        announcement_time = now.replace(hour=target_hour, minute=10, second=0, microsecond=0)
        if now >= announcement_time:
            return now.strftime("%Y%m%d"), f"{target_hour:02d}00"
            
    # 새벽 2시 10분 미만인 경우, 전날 밤 23시 예보를 사용합니다.
    yesterday = now - datetime.timedelta(days=1)
    return yesterday.strftime("%Y%m%d"), "2300"

def fetch_week_weather(nx, ny):
    """API 호출을 딱 1번만 수행하여 3일치 데이터를 통째로 긁어옵니다 (효율성 극대화)."""
    base_date, base_time = get_latest_base_datetime()
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": DECODED_KEY,
        "numOfRows": "1000",  # 3일치 분량을 넉넉하게 한 번에 가져옴
        "pageNo": "1",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }
    
    forecasts = {}
    try:
        res = requests.get(url, params=params, timeout=5)
        items = res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
        
        # 데이터를 {날짜: {시간: {카테고리: 값}}} 구조로 파싱
        for item in items:
            f_date = item["fcstDate"]
            f_time = item["fcstTime"]
            cat = item["category"]
            val = item["fcstValue"]
            
            if f_date not in forecasts:
                forecasts[f_date] = {}
            if f_time not in forecasts[f_date]:
                forecasts[f_date][f_time] = {}
                
            if cat in ["TMP", "POP"]:
                forecasts[f_date][f_time][cat] = float(val)
    except Exception:
        pass
        
    return forecasts

# ==========================================
# 3. 점심시간 장소 판정 알고리즘 (우선순위 반영)
# ==========================================
def judge_lunch(tmp_dict, pop_dict):
    """기온과 강수확률을 분석하여 교실 > 필로티 > 운동장 순서로 장소를 판정합니다."""
    t12, t13 = tmp_dict.get('12'), tmp_dict.get('13')
    p12, p13 = pop_dict.get('12'), pop_dict.get('13')

    if None in [t12, t13, p12, p13]:
        return "알 수 없음", "unknown", "예보 데이터가 존재하지 않습니다."

    # [1순위 필터링: 교실] 기온이 12도 미만이거나 30도를 초과하면 안전을 위해 무조건 교실
    if t12 < 12 or t12 > 30 or t13 < 12 or t13 > 30:
        return "교실", "classroom", f"점심시간 예상 기온이 너무 춥거나 더워서 실내 활동이 안전해요."

    # [2순위 필터링: 필로티] 기온은 좋으나 비 소식(강수확률 30% 초과)이 하나라도 있는 경우
    if p12 > 30 or p13 > 30:
        return "필로티", "piloti", f"비 소식(강수확률 30% 초과)이 있어서 비를 피할 수 있는 곳이 좋아요."

    # [3순위 필터링: 운동장] 기온 적절(12~30도)하고 강수확률도 모두 30% 이하인 완벽한 날씨
    return "운동장", "playground", "기온과 날씨 모두 야외 활동하기에 아주 완벽해요!"

# ==========================================
# 4. Streamlit 메인 UI 구성
# ==========================================
st.set_page_config(
    page_title="점심시간 어디서 놀까?",
    page_icon="🌤️",
    layout="wide"
)

st.title("🌤️ 점심시간 어디서 놀까?")
st.caption("미세먼지와 자외선 지수를 제외하고 오직 기온과 강수확률로만 정교하게 판단하는 초등 활동 추천 앱입니다.")

# 탭 나누기 (지역선택 / 주간추천)
tab1, tab2 = st.tabs(["📍 지역 선택", "📅 평일 점심시간 장소 추천"])

# --- 탭 1: 경기도 지역 선택 ---
with tab1:
    today = datetime.date.today()
    location_name = st.selectbox("경기도 내 지역을 선택하세요", list(LOCATIONS.keys()))
    
    # 이번 주 월요일부터 금요일까지의 날짜 자동 계산
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]
    
    st.info(f"📅 **이번 주 분석 범위 (월~금):** {week_dates[0].strftime('%Y-%m-%d')} ~ {week_dates[-1].strftime('%Y-%m-%d')}")
    st.session_state["location_name"] = location_name
    st.session_state["week_dates"] = week_dates

# --- 탭 2: 주간 예보 표 및 오늘 점심시간 활동 알림 ---
with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        
        results = []
        today_status_code = "unknown"
        today_place = ""
        today_reason = ""
        
        # 기상청 데이터 1회 통합 원격 호출
        with st.spinner(f"📡 기상청 서버에서 {location_name} 최신 날씨 정보를 가져오는 중..."):
            week_forecasts = fetch_week_weather(nx, ny)
            
        # 월~금 요일별 데이터 매핑 및 분석
        for d in week_dates:
            date_str = d.strftime("%Y%m%d")
            is_today = (d == datetime.date.today())
            
            temp_avg, pop_max, place, reason_str = "-", "-", "-", "지나간 날짜이거나 예보 범위를 벗어났습니다."
            status_code = "past"
            
            # 기상청 데이터에 해당 날짜가 존재하는 경우 파싱 (단기예보는 당일~모레까지만 제공됨)
            if date_str in week_forecasts:
                t12 = week_forecasts[date_str].get("1200", {}).get("TMP")
                t13 = week_forecasts[date_str].get("1300", {}).get("TMP")
                p12 = week_forecasts[date_str].get("1200", {}).get("POP")
                p13 = week_forecasts[date_str].get("1300", {}).get("POP")
                
                if None not in [t12, t13, p12, p13]:
                    temp_avg = round((t12 + t13) / 2, 1)
                    pop_max = int(max(p12, p13))
                    place, status_code, reason_str = judge_lunch({"12": t12, "13": t13}, {"12": p12, "13": p13})
            
            results.append({
                "날짜": d.strftime("%Y-%m-%d"),
                "요일": "월화수목금"[d.weekday()],
                "평균 기온(°C)": temp_avg,
                "최대 강수확률(%)": pop_max,
                "추천 장소": place,
                "판정 사유": reason_str
            })
            
            # 오늘 요일에 해당하는 데이터의 상태코드를 하단 배너용으로 저장
            if is_today:
                today_place, today_status_code, today_reason = place, status_code, reason_str
                    
        # 1. 주간 시간표 데이터프레임 시각화
        st.write(f"### 📊 {location_name} 주간 점심시간(12시~14시) 예보 요약")
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        # 2. 기획안 반영 핵심 하단 UI 구성 (오늘 점심시간 안내)
        st.subheader("📢 오늘 점심시간 활동 안내")
        
        if today_status_code in ["unknown", "past"]:
            st.info("💡 오늘은 주말이거나, 오늘 점심시간 예보 데이터가 아직 업데이트되지 않았습니다.")
            
        elif today_status_code == "playground":
            st.success("## ⚽ 야외활동 최고! 오늘은 [ 운동장 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            # 추천 활동 및 안전 수칙 탭 분리 구현
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                c1, c2, c3 = st.columns(3)
                with c1: st.button("⚽ 축구 / 발야구", use_container_width=True, key="p1")
                with c2: st.button("🛝 놀이터 이용", use_container_width=True, key="p2")
                with c3: st.button("🏃 술래잡기", use_container_width=True, key="p3")
            with safe_tab:
                st.info("🔸 운동장이 더울 땐 모자를 쓰고 물을 꼭 마셔요!\n\n🔸 놀이기구에서 친구를 밀지 않도록 주의해요!")
            
        elif today_status_code == "piloti":
            st.warning("## ☂️ 비 소식이 있어요. 오늘은 [ 필로티 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                c1, c2, c3 = st.columns(3)
                with c1: st.button("🏐 피구", use_container_width=True, key="pi1")
                with c2: st.button("🪢 단체 줄넘기", use_container_width=True, key="pi2")
                with c3: st.button("🪙 제기차기 / 수건돌리기", use_container_width=True, key="pi3")
            with safe_tab:
                st.warning("🔸 주변에 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!\n\n🔸 기둥에 부딪히지 않도록 조심해요!")
            
        elif today_status_code == "classroom":
            st.error("## 🌡️ 안전을 위해 오늘은 [ 교실 ] 에서 놀아요!")
            st.write(f"**이유:** {today_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                c1, c2, c3 = st.columns(3)
                with c1: st.button("🎲 보드게임", use_container_width=True, key="cl1")
                with c2: st.button("⚪ 공기놀이", use_container_width=True, key="cl2")
                with c3: st.button("🔍 교실 보물찾기", use_container_width=True, key="cl3")
            with safe_tab:
                st.error("🔸 교실 안에서는 절대 뛰지 않아요!\n\n🔸 책상이나 의자 모서리에 부딪히지 않도록 조심해요!")
                
    else:
        st.info("좌측 📍 지역 선택 탭에서 지역을 먼저 지정해주세요.")
