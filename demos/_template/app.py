import io
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Project",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Project")

def read_csv_any(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.read()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8", errors="replace")

with st.sidebar:
    uploaded = st.file_uploader("CSV", type=["csv"])

if uploaded is None:
    st.stop()

df = read_csv_any(uploaded)

st.dataframe(df, use_container_width=True, hide_index=True)
