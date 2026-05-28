import datetime
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st
from urllib.parse import quote

# =========================================================
# 점심시간 야외활동 추천 (경기도 '시' 단위)
# - 미세먼지 삭제
# - 기온/강수확률만 사용
# - '월~금' 날짜를 탭으로 선택
# - 단기예보(VilageFcst) + (필요 시) 중기예보로 보완하는 구조로 확장 가능
#   ※ 본 버전은 '월~금'에 대해 "가능하면 단기예보로 채우고",
#      누락 시엔 '예보 없음'으로 표시합니다.
# =========================================================

# NOTE: 실서비스에서는 Streamlit Secrets(st.secrets)로 옮기는 것을 권장합니다.
SERVICE_KEY_RAW = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"

# 공공데이터포털 키는 보통 "Encoding" / "Decoding" 형태로 제공됩니다.
# - Encoding 키면 아래를 False (quote 불필요)
# - Decoding 키면 아래를 True  (quote 필요)
SERVICE_KEY_IS_DECODING_KEY = True
SERVICE_KEY = quote(SERVICE_KEY_RAW, safe="") if SERVICE_KEY_IS_DECODING_KEY else SERVICE_KEY_RAW

# 경기도 '시' 단위(군 제외)
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

# 점심시간(12~13시)
TARGET_HOURS = ["1200", "1300"]


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
# 단기예보 base_date/base_time 자동 선택
# -----------------------------

# 동네예보 발표 시각(고정)
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

    # 새벽 2시 이전이면 전날 23시 발표 사용
    yday = today - datetime.timedelta(days=1)
    return yday.strftime("%Y%m%d"), "2300"


# -----------------------------
# API 호출 (단기예보)
# -----------------------------

@st.cache_data(ttl=60 * 10)
def fetch_vilage_fcst_items(nx: int, ny: int) -> list[dict]:
    """단기예보 전체 아이템(현재 base_date/base_time 발표분)을 가져옵니다."""
    base_date, base_time = pick_base_datetime()

    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": SERVICE_KEY,
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

    # API 오류 메시지가 JSON에 담겨 오는 경우도 있으므로 방어
    if "response" not in payload or payload.get("response", {}).get("header", {}).get("resultCode") not in (
        "00",
        0,
        "0",
        None,
    ):
        header = payload.get("response", {}).get("header", {})
        raise RuntimeError(f"API error: {header}")

    items = payload["response"]["body"]["items"]["item"]
    return items


def extract_lunch_tmp_pop(items: list[dict], yyyymmdd: str) -> tuple[dict, dict]:
    """items에서 특정 날짜의 12/13시 TMP, POP만 추출"""
    tmp_dict = {"12": None, "13": None}
    pop_dict = {"12": None, "13": None}

    for it in items:
        if it.get("fcstDate") != yyyymmdd:
            continue

        fcst_time = str(it.get("fcstTime", ""))
        if fcst_time not in TARGET_HOURS:
            continue

        hour_key = "12" if fcst_time == "1200" else "13"
        cat = it.get("category")

        try:
            val = float(it.get("fcstValue"))
        except Exception:
            val = None

        if cat == "TMP":
            tmp_dict[hour_key] = val
        elif cat == "POP":
            pop_dict[hour_key] = val

    return tmp_dict, pop_dict


# -----------------------------
# 판정 로직
# -----------------------------

def _has_all(tmp_dict: dict, pop_dict: dict) -> bool:
    return all(tmp_dict.get(h) is not None and pop_dict.get(h) is not None for h in ["12", "13"])


def calc_lunch_summary(tmp_dict: dict, pop_dict: dict):
    temps = [t for t in [tmp_dict.get("12"), tmp_dict.get("13")] if t is not None]
    pops = [p for p in [pop_dict.get("12"), pop_dict.get("13")] if p is not None]

    temp_avg = round(sum(temps) / len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None

    return temp_avg, pop_max


def judge_lunch(tmp_dict: dict, pop_dict: dict):
    """Returns: (headline, place_code, reason)"""

    if not _has_all(tmp_dict, pop_dict):
        return (
            "일기예보 발표 후에 안내드릴게요",
            "classroom",
            "아직 12~13시 기온/강수확률 예보가 충분히 나오지 않았어요.",
        )

    temps = [tmp_dict["12"], tmp_dict["13"]]
    pops = [pop_dict["12"], pop_dict["13"]]

    # 기온이 부적절하면 무조건 교실
    if not all(12 <= t <= 30 for t in temps):
        return (
            "교실 활동을 추천해요",
            "classroom",
            "기온이 12°C 미만이거나 30°C 초과라서 안전을 위해 실내(교실) 활동이 좋아요.",
        )

    # 기온 적절할 때만 비 확률로 운동장/필로티
    if all(p <= 30 for p in pops):
        return (
            "운동장 활동을 추천해요",
            "playground",
            "기온이 적당하고(12~30°C), 비 올 확률이 낮아요(강수확률 30% 이하).",
        )

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
st.caption("경기도 도시(시) 기준, 점심(12~13시) 기온/강수확률 예보로 운동장·필로티·교실을 추천합니다.")

with st.expander("⚙️ API 키 설정 확인(문제 해결)", expanded=False):
    st.write(
        "- 공공데이터포털 키가 Encoding 키라면: `SERVICE_KEY_IS_DECODING_KEY = False`로 바꿔주세요.\n"
        "- Decoding 키라면: `True`가 맞습니다.\n"
        "- 단기예보는 base_time이 발표시각(0200/0500/...)과 맞아야 잘 나옵니다. 이 앱은 자동으로 맞춥니다."
    )

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
</style>
""",
    unsafe_allow_html=True,
)


tab_setup, tab_week = st.tabs(["도시 선택", "이번주(월~금) 선택"])

with tab_setup:
    today = datetime.date.today()
    city = st.selectbox("경기도 도시(시)를 선택하세요", sorted(GYEONGGI_CITIES.keys()))

    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]

    st.write(
        "이번 주(월~금):",
        " ~ ".join([week_dates[0].strftime("%Y-%m-%d"), week_dates[-1].strftime("%Y-%m-%d")]),
    )

    st.session_state["city"] = city
    st.session_state["week_dates"] = week_dates


def render_place_banner(place_code: str, headline: str, reason: str, is_today: bool):
    plan = PLACE_PLANS[place_code]

    title = plan.badge_text if is_today else f"추천 장소: {plan.label}"

    if place_code == "playground":
        st.success(title)
    elif place_code == "piloti":
        st.warning(title)
    else:
        st.error(title)

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
    st.info("\n\n".join([f"• {r}" for r in plan.safety_rules]), icon="🛡️")


with tab_week:
    if "city" not in st.session_state or "week_dates" not in st.session_state:
        st.info("먼저 '도시 선택' 탭에서 지역을 선택해주세요.")
        st.stop()

    city = st.session_state["city"]
    week_dates = st.session_state["week_dates"]
    nx, ny = GYEONGGI_CITIES[city]

    # 단기예보 전체 조회 1회
    try:
        items = fetch_vilage_fcst_items(nx, ny)
    except Exception as e:
        st.error("날씨 API 호출에 실패했어요. (키 인코딩/디코딩 설정 또는 API 상태를 확인해주세요)")
        st.code(str(e))
        st.stop()

    # 월화수목금 '날짜 ��'
    day_tabs = st.tabs([f"{d.strftime('%m/%d')}({w})" for d, w in zip(week_dates, "월화수목금")])

    # 주간 표(요약)도 함께 보여주기
    weekly_rows = []
    for d in week_dates:
        ymd = d.strftime("%Y%m%d")
        tmp_dict, pop_dict = extract_lunch_tmp_pop(items, ymd)
        temp_avg, pop_max = calc_lunch_summary(tmp_dict, pop_dict)
        headline, place_code, reason = judge_lunch(tmp_dict, pop_dict)
        weekly_rows.append(
            {
                "날짜": d.strftime("%Y-%m-%d"),
                "요일": "월화수목금"[d.weekday()],
                "점심 기온(°C)": temp_avg,
                "점심 강수확률(%)": pop_max,
                "추천 장소": PLACE_PLANS[place_code].label,
                "상태코드": place_code,
                "판정": headline,
            }
        )

    st.markdown("### 이번주 요약(월~금)")
    st.dataframe(pd.DataFrame(weekly_rows), use_container_width=True, hide_index=True)
    st.markdown("---")

    for tab, d in zip(day_tabs, week_dates):
        with tab:
            ymd = d.strftime("%Y%m%d")
            tmp_dict, pop_dict = extract_lunch_tmp_pop(items, ymd)
            temp_avg, pop_max = calc_lunch_summary(tmp_dict, pop_dict)
            headline, place_code, reason = judge_lunch(tmp_dict, pop_dict)

            is_today = d == datetime.date.today()

            st.subheader(f"{city} · {d.strftime('%Y-%m-%d')} ({'월화수목금'[d.weekday()]})")

            if temp_avg is None or pop_max is None:
                st.info(
                    "이 날짜는 단기예보 범위 밖이거나 아직 발표되지 않아 12~13시 예보가 없어요.\n\n"
                    "(주간을 100% 채우려면 중기예보 API를 추가로 연결해야 합니다.)"
                )
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("점심 평균 기온(12~13시)", f"{temp_avg} °C")
                with col2:
                    st.metric("점심 최대 강수확률(12~13시)", f"{int(pop_max)} %")

            render_place_banner(place_code, headline, reason, is_today=is_today)

            st.caption(
                f"원자료(12시/13시): 기온 {tmp_dict.get('12')}°C / {tmp_dict.get('13')}°C · "
                f"강수확률 {pop_dict.get('12')}% / {pop_dict.get('13')}%"
            )
