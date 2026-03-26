import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cohort Retention", layout="wide")

# ================= LOAD =================
@st.cache_data
def load_data():
    df = pd.read_parquet("data/crm_cohort.parquet", columns=[
        "Số_điện_thoại", "Ngày", "Brand", "Region"
    ])

    df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    df = df.dropna(subset=["Ngày"])

    if "Số_điện_thoại" in df.columns:
        df["Số_điện_thoại"] = (
            df["Số_điện_thoại"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

    return df

df = load_data()

st.title("🏅 Cohort Retention")

# ================= SAFE FILTER =================
def safe_multiselect(label, options):
    opts = sorted(pd.Series(options).dropna().astype(str).unique())
    selected = st.sidebar.multiselect(label, opts, default=opts)
    return selected if selected else opts


# ================= SIDEBAR =================
st.sidebar.header("🎛️ Bộ lọc")

start_date = st.sidebar.date_input("Từ ngày", df["Ngày"].min().date())
end_date = st.sidebar.date_input("Đến ngày", df["Ngày"].max().date())

brand_filter = safe_multiselect("Brand", df["Brand"] if "Brand" in df.columns else [])
region_filter = safe_multiselect("Region", df["Region"] if "Region" in df.columns else [])

# ================= APPLY FILTER =================
df_f = df[
    (df["Ngày"] >= pd.to_datetime(start_date)) &
    (df["Ngày"] <= pd.to_datetime(end_date))
]

if "Brand" in df_f.columns:
    df_f = df_f[df_f["Brand"].isin(brand_filter)]

if "Region" in df_f.columns:
    df_f = df_f[df_f["Region"].isin(region_filter)]

if df_f.empty:
    st.warning("Không có dữ liệu sau filter")
    st.stop()

# ================= COHORT =================
df_f["Order_Month"] = df_f["Ngày"].dt.to_period("M")

# ⚡ tối ưu RAM: dùng merge thay transform
first = df_f.groupby("Số_điện_thoại")["Order_Month"].min().reset_index()
first.columns = ["Số_điện_thoại", "First_Month"]

df_f = df_f.merge(first, on="Số_điện_thoại")

df_f["Cohort_Index"] = (
    (df_f["Order_Month"].dt.year - df_f["First_Month"].dt.year) * 12
    + (df_f["Order_Month"].dt.month - df_f["First_Month"].dt.month)
)

df_f = df_f[df_f["Cohort_Index"] >= 0]

# ================= CALC =================
MAX_MONTH = st.sidebar.slider("Số tháng retention", 3, 12, 6)

cohort_size = df_f[df_f["Cohort_Index"] == 0] \
    .groupby("First_Month")["Số_điện_thoại"].nunique()

rows = []

for cohort, size in cohort_size.items():
    d = df_f[df_f["First_Month"] == cohort]

    row = {
        "Cohort": str(cohort),
        "Size": size
    }

    for m in range(1, MAX_MONTH + 1):
        count = d[d["Cohort_Index"] == m]["Số_điện_thoại"].nunique()
        row[f"M{m}"] = round(count / size * 100, 2) if size else 0

    rows.append(row)

result = pd.DataFrame(rows)

# ================= DISPLAY =================
st.subheader("📊 Cohort Retention (%)")

if result.empty:
    st.info("Không có dữ liệu")
else:
    df_show = result.copy()

    for c in df_show.columns:
        if c.startswith("M"):
            df_show[c] = df_show[c].astype(str) + "%"

    st.dataframe(df_show, use_container_width=True)