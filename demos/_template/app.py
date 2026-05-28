import datetime
from dataclasses import dataclass

import requests
import streamlit as st
from urllib.parse import quote

# =========================================================
# 초등 점심시간 야외활동 추천 (오늘만)
# - 기상청 단기예보(동네예보) API로 오늘 12~13시 기온(TMP) + 강수확률(POP)만 사용
# - 장소 우선순위: 운동장 > 필로티 > 교실
# - 오늘 알림 UI: 배너 + 추천놀이 3개 + 안전수칙
# =========================================================

# NOTE: 실서비스에서는 Streamlit Secrets(st.secrets)로 옮기는 것을 권장합니다.
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
ENCODED_KEY = quote(SERVICE_KEY, safe="")

# 경기도 '시' 단위(군 제외) 대표 격자(nx, ny)
GYEONGGI_CITIES = {
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
    "여주시": (71, 121),
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
    banner_text: str
    plays: tuple[str, str, str]
    safety_rules: tuple[str, str]


PLACE_PLANS: dict[str, PlacePlan] = {
    "playground": PlacePlan(
        label="운동장",
        banner_text="오늘 점심시간 추천 장소: 운동장",
        plays=("⚽ 축구/발야구", "🛝 놀이터 이용", "🏃 술래잡기"),
        safety_rules=(
            "운동장이 더울 땐 모자를 쓰고 물을 꼭 마셔요!",
            "놀이기구에서 친구를 밀지 않도록 주의해요!",
        ),
    ),
    "piloti": PlacePlan(
        label="필로티",
        banner_text="오늘 점심시간 추천 장소: 필로티",
        plays=("🏐 피구", "🪢 단체 줄넘기", "🪙 제기차기/수건돌리기"),
        safety_rules=(
            "주변에 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!",
            "기둥에 부딪히지 않도록 조심해요!",
        ),
    ),
    "classroom": PlacePlan(
        label="교실",
        banner_text="오늘 점심시간 추천 장소: 교실",
        plays=("🎲 보드게임", "⚪ 공기놀이", "🔍 교실 보물찾기"),
        safety_rules=(
            "교실 안에서는 절대 뛰지 않아요!",
            "책상이나 의자 모서리에 부딪히지 않도록 조심해요!",
        ),
    ),
}


# -----------------------------
# 단기예보 base_date/base_time 자동 선택
# -----------------------------
PUBLISH_TIMES = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]


def pick_base_datetime(now: datetime.datetime | None = None) -> tuple[str, str]:
    """현재시각 기준으로 가장 최근 발표시각의 base_date/base_time을 계산합니다."""
    if now is None:
        now = datetime.datetime.now()

    today = now.date()
    hhmm = now.strftime("%H%M")

    candidates = [t for t in PUBLISH_TIMES if t <= hhmm]
    if candidates:
        return today.strftime("%Y%m%d"), candidates[-1]

    # 새벽 2시 이전이면 전날 23시 발표
    yday = today - datetime.timedelta(days=1)
    return yday.strftime("%Y%m%d"), "2300"


@st.cache_data(ttl=60 * 10)
def fetch_today_lunch_forecast(nx: int, ny: int) -> tuple[dict, dict, str, str]:
    """오늘(12/13시) TMP/POP만 뽑아서 반환합니다.

    Returns:
      (tmp_dict, pop_dict, base_date, base_time)
    """
    base_date, base_time = pick_base_datetime()
    today = datetime.date.today().strftime("%Y%m%d")

    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": ENCODED_KEY,  # 이미 quote 처리된 key
        "numOfRows": "1000",
        "pageNo": "1",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": str(nx),
        "ny": str(ny),
    }

    res = requests.get(url, params=params, timeout=12)
    res.raise_for_status()
    payload = res.json()
    items = payload["response"]["body"]["items"]["item"]

    tmp_dict = {"12": None, "13": None}
    pop_dict = {"12": None, "13": None}

    for it in items:
        if it.get("fcstDate") != today:
            continue
        fcst_time = str(it.get("fcstTime", ""))  # "1200"
        if not any(fcst_time.startswith(h) for h in TARGET_HOURS):
            continue
        hour_key = "12" if fcst_time.startswith("12") else "13"

        cat = it.get("category")
        try:
            val = float(it.get("fcstValue"))
        except Exception:
            val = None

        if cat == "TMP":
            tmp_dict[hour_key] = val
        elif cat == "POP":
            pop_dict[hour_key] = val

    return tmp_dict, pop_dict, base_date, base_time


def _has_all_hours(tmp_dict: dict, pop_dict: dict) -> bool:
    return all(tmp_dict.get(h) is not None and pop_dict.get(h) is not None for h in ["12", "13"])


def judge_lunch(tmp_dict: dict, pop_dict: dict):
    """점심시간(12/13시) 예보로 장소를 판정합니다.

    Returns:
        (headline, place_code, reason)
        place_code: 'playground' | 'piloti' | 'classroom'
    """

    if not _has_all_hours(tmp_dict, pop_dict):
        return (
            "일기예보 발표 후에 안내드릴게요",
            "classroom",
            "아직 12~13시 기온/강수확률 예보가 없습니다.",
        )

    temps = [tmp_dict["12"], tmp_dict["13"]]
    pops = [pop_dict["12"], pop_dict["13"]]

    # 1) 기온이 부적절하면 무조건 교실 (최우선)
    if not all(12 <= t <= 30 for t in temps):
        return (
            "교실 활동을 추천해요",
            "classroom",
            "기온이 12°C 미만이거나 30°C 초과라서 안전을 위해 교실 활동이 좋아요.",
        )

    # 2) 기온이 적절할 때만 강수확률로 운동장/필로티
    if all(p <= 30 for p in pops):
        return (
            "운동장 활동을 추천해요",
            "playground",
            "기온이 적당하고(12~30°C), 비 올 확률이 낮아요(강수확률 30% 이하).",
        )

    return (
        "비를 피해서 필로티 활동을 추천해요",
        "piloti",
        "기온은 아주 좋지만 강수확률이 30%를 넘어서 비를 피할 수 있는 곳이 좋아요.",
    )


def render_today_section(place_code: str, headline: str, reason: str):
    plan = PLACE_PLANS[place_code]

    if place_code == "playground":
        st.success(plan.banner_text)
    elif place_code == "piloti":
        st.warning(plan.banner_text)
    else:
        st.error(plan.banner_text)

    st.caption(f"판정: {headline}")
    st.caption(f"근거: {reason}")

    st.markdown("#### 추천 놀이 3가지")
    c1, c2, c3 = st.columns(3)
    for col, play in zip((c1, c2, c3), plan.plays):
        with col:
            st.markdown(
                f"""
<div style="padding: 1rem; border-radius: 12px; border: 1px solid rgba(0,0,0,0.08); background: rgba(255,255,255,0.6); min-height: 70px;">
  <div style="font-weight: 700; font-size: 1.05rem;">{play}</div>
  <div style="color: rgba(0,0,0,0.65);">친구들과 안전하게 즐겨요</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("#### 안전 수칙")
    st.info("\n\n".join([f"• {r}" for r in plan.safety_rules]), icon="🛡️")


# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title="오늘 점심시간 어디서 놀까요?", page_icon="🌤️", layout="wide")

st.title("🌤️ 오늘 점심시간 어디서 놀까요?")
st.caption("경기도 도시(시) 기준, 오늘 12~13시 기온/강수확률 예보로 운동장·필로티·교실을 추천합니다.")

city = st.selectbox("경기도 도시(시)를 선택하세요", sorted(GYEONGGI_CITIES.keys()))
nx, ny = GYEONGGI_CITIES[city]

st.markdown("---")

try:
    tmp_dict, pop_dict, base_date, base_time = fetch_today_lunch_forecast(nx, ny)
except Exception as e:
    st.error("날씨 API 호출에 실패했어요. (서비스키/네트워크/API 상태 확인 필요)")
    st.code(str(e))
    st.stop()

headline, place_code, reason = judge_lunch(tmp_dict, pop_dict)

st.subheader(f"{city} · 오늘({datetime.date.today().strftime('%Y-%m-%d')}) 점심시간 예보")

col1, col2 = st.columns(2)
with col1:
    st.metric("12시 기온", "정보없음" if tmp_dict.get("12") is None else f"{tmp_dict.get('12')} °C")
    st.metric("13시 기온", "정보없음" if tmp_dict.get("13") is None else f"{tmp_dict.get('13')} °C")
with col2:
    st.metric("12시 강수확률", "정보없음" if pop_dict.get("12") is None else f"{int(pop_dict.get('12'))} %")
    st.metric("13시 강수확률", "정보없음" if pop_dict.get("13") is None else f"{int(pop_dict.get('13'))} %")

st.caption(f"(조회 기준 발표시각: base_date={base_date}, base_time={base_time})")

st.markdown("---")
st.subheader("오늘 점심시간 알림")
render_today_section(place_code, headline, reason)
