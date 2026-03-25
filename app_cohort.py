import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cohort Retention", layout="wide")

# ================= LOAD NHẸ =================
@st.cache_data
def load_data():
    df = pd.read_parquet("data/crm_cohort.parquet", columns=[
        "Số_điện_thoại", "Ngày"
    ])

    df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    df = df.dropna(subset=["Ngày"])

    return df

df = load_data()

st.title("🏅 Cohort Retention")

# ================= PREP =================
df["Order_Month"] = df["Ngày"].dt.to_period("M")

# ⚡ tối ưu: dùng merge thay transform
first = df.groupby("Số_điện_thoại")["Order_Month"].min().reset_index()
first.columns = ["Số_điện_thoại", "First_Month"]

df = df.merge(first, on="Số_điện_thoại")

df["Cohort_Index"] = (
    (df["Order_Month"].dt.year - df["First_Month"].dt.year) * 12
    + (df["Order_Month"].dt.month - df["First_Month"].dt.month)
)

df = df[df["Cohort_Index"] >= 0]

# ================= CALC =================
MAX_MONTH = st.sidebar.slider("Max month", 3, 12, 6)

cohort_size = df[df["Cohort_Index"] == 0].groupby("First_Month")["Số_điện_thoại"].nunique()

rows = []
for cohort, size in cohort_size.items():
    d = df[df["First_Month"] == cohort]

    row = {"Cohort": str(cohort), "Size": size}

    for m in range(1, MAX_MONTH + 1):
        count = d[d["Cohort_Index"] == m]["Số_điện_thoại"].nunique()
        row[f"M{m}"] = round(count / size * 100, 2)

    rows.append(row)

result = pd.DataFrame(rows)

st.dataframe(result, use_container_width=True)
