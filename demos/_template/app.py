import datetime
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st
from urllib.parse import quote

# -----------------------------
# 기본 설정
# -----------------------------

# NOTE: 실서비스에서는 Streamlit Secrets(st.secrets)로 옮기는 것을 권장합니다.
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe="")

# 경기도 31개 시/군 (시군 단위)
# - 기상청 동네예보(VilageFcst)용 격자(nx, ny)
# - 사용자가 "경기도 내 모든 도시"를 원하셨으므로, 시/군 전체를 제공합니다.
# - 격자값은 예시/기본값이며, 실제 학교/지역에 맞게 조정해도 됩니다.
#   (정확도를 높이려면 주소->격자 변환 API/로직을 붙이는 방식이 가장 좋습니다.)
GYEONGGI_CITIES = {
    "가평군": (69, 133),
    "고양시": (57, 128),
    "과천시": (60, 124),
    "광명시": (58, 125),
    "광주시": (65, 123),
    "구리시": (62, 127),
    "군포시": (59, 122),
    "김포시": (55, 128),
    "남양주시": (64, 128),
    "동두천시": (61, 134),
    "부천시": (56, 125),
    "성남시": (63, 124),
    "수원시": (60, 121),
    "시흥시": (57, 123),
    "안산시": (58, 121),
    "안성시": (65, 115),
    "안양시": (59, 123),
    "양주시": (61, 131),
    "양평군": (69, 125),
    "여주시": (71, 121),
    "연천군": (61, 138),
    "오산시": (62, 118),
    "용인시": (62, 120),
    "의왕시": (60, 122),
    "의정부시": (61, 130),
    "이천시": (68, 121),
    "파주시": (56, 131),
    "평택시": (62, 114),
    "포천시": (64, 134),
    "하남시": (64, 126),
    "화성시": (57, 119),
}

TARGET_HOURS = ["12", "13"]


@dataclass(frozen=True)
class PlacePlan:
    label: str
    badge_text: str
    plays: tuple[str, str, str]
    safety_rules: tuple[str, str]


PLACE_PLANS: dict[str, PlacePlan] = {
    "playground": PlacePlan(
        label="운동장",
        badge_text="오늘 점심시간 추천 장소: 운동장",
        plays=("⚽ 축구/발야구", "🛝 놀이터 이용", "🏃 술래잡기"),
        safety_rules=(
            "운동장이 더울 땐 모자를 쓰고 물을 꼭 마셔요!",
            "놀이기구에서 친구를 밀지 않도록 주의해요!",
        ),
    ),
    "piloti": PlacePlan(
        label="필로티",
        badge_text="오늘 점심시간 추천 장소: 필로티",
        plays=("🏐 피구", "🪢 단체 줄넘기", "🪙 제기차기/수건돌리기"),
        safety_rules=(
            "주변에 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!",
            "기둥에 부딪히지 않도록 조심해요!",
        ),
    ),
    "classroom": PlacePlan(
        label="교실",
        badge_text="오늘 점심시간 추천 장소: 교실",
        plays=("🎲 보드게임", "⚪ 공기놀이", "🔍 교실 보물찾기"),
        safety_rules=(
            "교실 안에서는 절대 뛰지 않아요!",
            "책상이나 의자 모서리에 부딪히지 않도록 조심해요!",
        ),
    ),
}


# -----------------------------
# 데이터 호출
# -----------------------------

@st.cache_data(ttl=60 * 10)
def fetch_weather(base_date: str, nx: int, ny: int, base_time: str = "1100", target_hours=TARGET_HOURS):
    """기상청 동네예보에서 12/13시 기온(TMP), 강수확률(POP)을 가져옵니다."""
    url = (
        "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={ENCODED_KEY}&numOfRows=300&pageNo=1&dataType=JSON"
        f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )

    TMPs, POPs = {}, {}
    try:
        res = requests.get(url, timeout=8)
        res.raise_for_status()
        items = res.json()["response"]["body"]["items"]["item"]

        for h in target_hours:
            tmp = next(
                (
                    float(i["fcstValue"])
                    for i in items
                    if i.get("category") == "TMP" and str(i.get("fcstTime", "")).startswith(h)
                ),
                None,
            )
            pop = next(
                (
                    float(i["fcstValue"])
                    for i in items
                    if i.get("category") == "POP" and str(i.get("fcstTime", "")).startswith(h)
                ),
                None,
            )
            TMPs[h] = tmp
            POPs[h] = pop

        return TMPs, POPs
    except Exception:
        return {h: None for h in target_hours}, {h: None for h in target_hours}


# -----------------------------
# 판정 로직
# -----------------------------

def _has_all_hours(tmp_dict: dict, pop_dict: dict, hours=TARGET_HOURS) -> bool:
    return all(tmp_dict.get(h) is not None and pop_dict.get(h) is not None for h in hours)


def calc_lunch_summary(tmp_dict: dict, pop_dict: dict):
    temps = [t for t in [tmp_dict.get("12"), tmp_dict.get("13")] if t is not None]
    pops = [p for p in [pop_dict.get("12"), pop_dict.get("13")] if p is not None]

    temp_avg = round(sum(temps) / len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None

    return temp_avg, pop_max


def judge_lunch(tmp_dict: dict, pop_dict: dict):
    """점심시간(12/13시) 예보로 장소를 판정합니다.

    Returns:
        (result_text, place_code, reason_text)
        place_code: 'playground' | 'piloti' | 'classroom'
    """

    if not _has_all_hours(tmp_dict, pop_dict):
        return (
            "일기예보 발표 후에 안내드릴게요",
            "classroom",
            "아직 12~13시 기온/강수확률 예보가 충분히 나오지 않았어요.",
        )

    temps = [tmp_dict["12"], tmp_dict["13"]]
    pops = [pop_dict["12"], pop_dict["13"]]

    temp_ok = all(12 <= t <= 30 for t in temps)

    # 기온이 부적절하면 (춥거나/덥거나) 비와 무관하게 무조건 교실
    if not temp_ok:
        return (
            "교실 활동을 추천해요",
            "classroom",
            "기온이 12°C 미만이거나 30°C 초과라서 안전을 위해 실내(교실) 활동이 좋아요.",
        )

    rain_ok = all(p <= 30 for p in pops)

    if rain_ok:
        return (
            "운동장 활동을 추천해요",
            "playground",
            "기온이 적당하고(12~30°C), 비 올 확률이 낮아요(강수확률 30% 이하).",
        )

    # 기온은 적절하지만 비가 오면 필로티
    return (
        "비를 피해서 필로티 활동을 추천해요",
        "piloti",
        "기온은 아주 좋지만, 강수확률이 30%를 넘어서 비를 피할 수 있는 곳이 좋아요.",
    )


# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="점심시간 야외활동 추천", page_icon="🌤️", layout="wide")

st.title("🌤️ 점심시간 야외활동 추천")
st.caption("경기도 시/군 기준, 평일 점심(12~13시) 기온/강수확률 예보로 운동장·필로티·교실을 추천합니다.")

st.markdown(
    """
<style>
  .place-card {
    padding: 1rem;
    border-radius: 12px;
    background: rgba(255,255,255,0.6);
    border: 1px solid rgba(0,0,0,0.06);
    min-height: 68px;
  }
  .place-title {
    font-weight: 700;
    font-size: 1.05rem;
    margin-bottom: .3rem;
  }
  .place-sub {
    color: rgba(0,0,0,0.65);
    font-size: .95rem;
  }
  .big-safety {
    font-size: 1.05rem;
    font-weight: 700;
    line-height: 1.5;
  }
</style>
""",
    unsafe_allow_html=True,
)


tab1, tab2 = st.tabs(["도시/주간 선택", "평일 점심시간 추천(월~금)"])

with tab1:
    today = datetime.date.today()

    # 경기도 시/군
    city = st.selectbox("경기도 시/군을 선택하세요", sorted(GYEONGGI_CITIES.keys()))

    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]

    st.write(
        "이번 주(월~금):",
        " ~ ".join([week_dates[0].strftime("%Y-%m-%d"), week_dates[-1].strftime("%Y-%m-%d")]),
    )

    st.session_state["city"] = city
    st.session_state["week_dates"] = week_dates


def _render_today_banner(place_code: str, headline: str, reason: str):
    plan = PLACE_PLANS[place_code]

    if place_code == "playground":
        st.success(f"{plan.badge_text}")
    elif place_code == "piloti":
        st.warning(f"{plan.badge_text}")
    else:
        st.error(f"{plan.badge_text}")

    st.caption(f"판정: {headline}")
    st.caption(f"근거: {reason}")

    st.markdown("#### 추천 놀이 3가지")
    c1, c2, c3 = st.columns(3)
    for col, play in zip((c1, c2, c3), plan.plays):
        with col:
            st.markdown(
                f"""
<div class="place-card">
  <div class="place-title">{play}</div>
  <div class="place-sub">친구들과 안전하게 즐겨요</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("#### 안전 수칙")
    st.info(
        "\n\n".join([f"• {rule}" for rule in plan.safety_rules]),
        icon="🛡️",
    )


with tab2:
    if "city" not in st.session_state or "week_dates" not in st.session_state:
        st.info("먼저 '도시/주간 선택' 탭에서 지역을 선택해주세요.")
        st.stop()

    city = st.session_state["city"]
    week_dates = st.session_state["week_dates"]
    nx, ny = GYEONGGI_CITIES[city]

    results = []
    data_found = False

    today_place_code = None
    today_headline = ""
    today_reason = ""
    today_tmp_dict = None
    today_pop_dict = None

    with st.spinner(f"{city} 평일 점심 예보 확인 중..."):
        for d in week_dates:
            base_date = d.strftime("%Y%m%d")

            tmp_dict, pop_dict = fetch_weather(base_date, nx, ny, base_time="1100", target_hours=TARGET_HOURS)

            is_today = d == datetime.date.today()
            if is_today:
                today_tmp_dict = tmp_dict.copy()
                today_pop_dict = pop_dict.copy()

            temp_avg, pop_max = calc_lunch_summary(tmp_dict, pop_dict)
            headline, place_code, reason = judge_lunch(tmp_dict, pop_dict)

            if temp_avg is not None and pop_max is not None:
                data_found = True

            results.append(
                {
                    "날짜": d.strftime("%Y-%m-%d"),
                    "요일": "월화수목금"[d.weekday()],
                    "점심시간 기온(°C)": temp_avg,
                    "점심시간 강수확률(%)": pop_max,
                    "추천 장소": PLACE_PLANS[place_code].label,
                    "상태코드": place_code,
                    "판정": headline,
                    "설명": reason,
                }
            )

            if is_today:
                today_place_code = place_code
                today_headline = headline
                today_reason = reason

    df = pd.DataFrame(results)

    # 주간 표
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not data_found:
        st.info("일기예보 발표 후에 안내드릴게요")

    st.markdown("---")
    st.subheader("오늘 점심시간 알림")

    if today_place_code is None:
        st.info("오늘 정보가 아직 공개되지 않았어요.")
        st.stop()

    _render_today_banner(today_place_code, today_headline, today_reason)

    # (교사용) 오늘 12/13시 원자료 간단 표시
    if today_tmp_dict and today_pop_dict:
        st.caption(
            f"오늘({city}) 12/13시 기온: {today_tmp_dict.get('12')}°C / {today_tmp_dict.get('13')}°C · "
            f"강수확률: {today_pop_dict.get('12')}% / {today_pop_dict.get('13')}%"
        )
