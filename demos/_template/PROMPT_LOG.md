# PROMPT_LOG.md

GitHub Copilot Chat에 입력한 프롬프트를 시간 순서대로 기록합니다.

> **왜?** 좋은 프롬프트의 감각은 시행착오를 봐야 늡니다.
> 코드를 베끼는 게 아니라 프롬프트를 배우는 과정입니다.

---

## #1 — 프로젝트 초기 골격

> **Prompt**
> import io

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="야외수업 가능 날씨 앱",
    page_icon="📊",
    layout="wide",
)

st.title("📊 야외수업 가능 날씨 앱")
st.caption("강수확률, 기온, 미세먼지 3가지 조건으로 야외수업 가능 여부를 판별합니다.")

def read_csv_any(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.read()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8", errors="replace")

with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded = st.file_uploader("CSV 파일", type=["csv"])
    st.markdown(
        """
        **필수 컬럼**
        - `rain_prob` (강수확률 %)
        - `temp` (기온, °C)
        - `dust` (미세먼지 ㎍/㎥ 또는 '좋음', '보통', '나쁨')

        샘플 파일 예시:

        | rain_prob | temp | dust  |
        |-----------|------|-------|
        |    10     |  15  |  22   |
        |    28     |  16  | 보통  |
        |    35     |  22  | 나쁨  |
        |    30     |  17  |  82   |
        """
    )

if uploaded is None:
    st.info("👈 왼쪽 사이드바에서 CSV 파일을 업로드하세요.")
    st.stop()

df = read_csv_any(uploaded)

st.subheader("① 데이터 확인")
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("② 야외수업 가능 여부 판별 결과")

def dust_is_ok(val):
    """미세먼지 수치/등급을 받아 '보통 이하'면 True."""
    try:
        # 만약 val이 숫자(str 포함)라면 80 이하
        if isinstance(val, str):
            val_strip = val.strip()
            if val_strip.isdigit():
                return int(val_strip) <= 80
            # 한글 등급 텍스트
            if val_strip in ["좋음", "보통"]:
                return True
            if val_strip in ["나쁨", "매우나쁨"]:
                return False
        # 실제 숫자
        elif isinstance(val, (int, float)):
            return val <= 80
    except:
        pass
    return False

def judge(row):
    reasons = []
    if not (15 <= row['temp'] <= 32):
        reasons.append("기온이 15~32도가 아니")
    if not dust_is_ok(row['dust']):
        reasons.append("미세먼지가 보통(80)이하가 아니")
    if row['rain_prob'] > 30:
        reasons.append("강수확률이 30% 이하가 아니")
    if not reasons:
        return "오늘은 야외수업 할 수 있어요!"
    else:
        s = "·".join(reasons)
        return f"아쉽지만 오늘은 야외수업을 못해요. 그 이유는 **{s} 때문이에요.**"

df["야외수업 판단"] = df.apply(judge, axis=1)
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("③ 가능/불가능 요약")
possible_count = (df["야외수업 판단"] == "오늘은 야외수업 할 수 있어요!").sum()
st.metric("야외수업 가능 일수", f"{possible_count} 일")


**결과:** (어떤 코드가 나왔는지 / 잘 됐는지 / 문제가 있었는지)

---

## #2 — (다음 프롬프트)

> **Prompt**
> ___

**결과:** ___

---

## #3 — ___

## #4 — ___

## #5 — ___

## #6 — ___

## #7 — ___

## #8 — ___

## #9 — ___

## #10 — ___

---

## 🪜 회고

| 잘 된 프롬프트의 특징 | 사례 번호 |
|---|---|
| 도메인 맥락을 함께 줌 |  |
| 실패 모드 미리 명시 |  |
| 색상/숫자 등 구체적 |  |

**나쁜 프롬프트 1순위**: "X가 안 돼" 만 던지기 → Copilot도 추측만 한다.
