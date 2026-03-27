import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cohort Retention", layout="wide")


# =====================================================
# LOAD DATA
# =====================================================
@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_parquet("data/crm_cohort.parquet")

    if df is None or df.empty:
        return pd.DataFrame()

    if "Ngày" in df.columns:
        df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
        df = df.dropna(subset=["Ngày"])

    for c in ["LoaiCT", "Brand", "Region", "Điểm_mua_hàng"]:
        if c in df.columns:
            try:
                df[c] = df[c].astype("category")
            except Exception:
                pass

    if "Số_điện_thoại" in df.columns:
        df["Số_điện_thoại"] = (
            df["Số_điện_thoại"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )

    return df


# =====================================================
# SAFE MULTISELECT WITH "ALL"
# =====================================================
def safe_multiselect_all(
    key: str,
    label: str,
    options,
    all_label: str = "All",
    default_all: bool = True,
    normalize: bool = True,
):
    opts = pd.Series(list(options)).dropna().astype(str)
    if normalize:
        opts = opts.str.strip()
    opts = sorted(opts.unique().tolist())

    ui_opts = [all_label] + opts

    if key not in st.session_state:
        st.session_state[key] = [all_label] if default_all else (opts[:1] if opts else [all_label])

    cur = st.session_state.get(key, [])
    cur = [str(x).strip() for x in cur if str(x).strip() in ui_opts]
    if not cur:
        cur = [all_label] if default_all else (opts[:1] if opts else [all_label])
        st.session_state[key] = cur

    selected = st.multiselect(label, options=ui_opts, key=key)

    if (not selected) or (all_label in selected):
        return opts
    return [x for x in selected if x in opts]


# =====================================================
# FORMAT HELPERS
# =====================================================
def fmt_int(x):
    if pd.isna(x):
        return ""
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return ""


def fmt_pct(x, decimals=2):
    if pd.isna(x):
        return ""
    try:
        return f"{float(x):,.{decimals}f}%"
    except Exception:
        return ""


def show_df(df_show: pd.DataFrame, title: str | None = None):
    if title:
        st.subheader(title)
    st.dataframe(df_show, use_container_width=True, hide_index=True)


# =====================================================
# APPLY FILTERS
# =====================================================
def apply_filters(df: pd.DataFrame, start_date, end_date, loaiCT, brand, region, store) -> pd.DataFrame:
    mask = (df["Ngày"] >= pd.to_datetime(start_date)) & (df["Ngày"] <= pd.to_datetime(end_date))

    if "LoaiCT" in df.columns:
        mask &= df["LoaiCT"].isin(loaiCT if loaiCT else [])
    if "Brand" in df.columns:
        mask &= df["Brand"].isin(brand if brand else [])
    if "Region" in df.columns:
        mask &= df["Region"].isin(region if region else [])
    if "Điểm_mua_hàng" in df.columns:
        mask &= df["Điểm_mua_hàng"].isin(store if store else [])

    return df.loc[mask].copy()


# =====================================================
# PAGE
# =====================================================
st.title("🏅 Cohort Retention")

df = load_data()
st.sidebar.caption(f"RAM df ~ {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB" if not df.empty else "RAM df ~ 0.0 MB")

if df.empty:
    st.warning("⚠ Không có dữ liệu để phân tích. Kiểm tra lại file data/crm_cohort.parquet")
    st.stop()


# =====================================================
# SIDEBAR FILTER
# =====================================================
with st.sidebar:
    st.header("🎛️ Bộ lọc dữ liệu (Cohort)")

    start_date = st.date_input("Từ ngày", df["Ngày"].min().date())
    end_date = st.date_input("Đến ngày", df["Ngày"].max().date())

    loaiCT_filter = safe_multiselect_all(
        key="loaiCT_filter",
        label="Loại CT",
        options=df["LoaiCT"] if "LoaiCT" in df.columns else [],
        all_label="All",
        default_all=True,
    )

    brand_filter = safe_multiselect_all(
        key="brand_filter",
        label="Brand",
        options=df["Brand"] if "Brand" in df.columns else [],
        all_label="All",
        default_all=True,
    )

df_b = df[df["Brand"].isin(brand_filter)] if (brand_filter and "Brand" in df.columns) else df.iloc[0:0]

with st.sidebar:
    region_filter = safe_multiselect_all(
        key="region_filter",
        label="Region",
        options=df_b["Region"] if "Region" in df_b.columns else [],
        all_label="All",
        default_all=True,
    )

df_br = df_b[df_b["Region"].isin(region_filter)] if (region_filter and "Region" in df_b.columns) else df_b.iloc[0:0]

with st.sidebar:
    store_filter = safe_multiselect_all(
        key="store_filter",
        label="Cửa hàng",
        options=df_br["Điểm_mua_hàng"] if "Điểm_mua_hàng" in df_br.columns else [],
        all_label="All",
        default_all=True,
    )

    st.subheader("⚙️ Cohort Retention")
    MAX_MONTH = st.sidebar.slider("Giới hạn số tháng retention", 3, 12, 7)


df_f = apply_filters(
    df,
    start_date,
    end_date,
    loaiCT_filter,
    brand_filter,
    region_filter,
    store_filter,
)

if df_f.empty:
    st.warning("⚠ Không có dữ liệu sau khi áp bộ lọc.")
    st.stop()


# =====================================================
# COHORT RETENTION
# =====================================================
df_cohort = df_f.copy()

df_cohort["Order_Month"] = df_cohort["Ngày"].dt.to_period("M")
df_cohort["First_Month"] = df_cohort.groupby("Số_điện_thoại")["Order_Month"].transform("min")

df_cohort["Cohort_Index"] = (
    (df_cohort["Order_Month"].dt.year - df_cohort["First_Month"].dt.year) * 12
    + (df_cohort["Order_Month"].dt.month - df_cohort["First_Month"].dt.month)
)

df_cohort = df_cohort[df_cohort["Cohort_Index"] >= 0]

cohort_size = (
    df_cohort[df_cohort["Cohort_Index"] == 0]
    .groupby("First_Month")["Số_điện_thoại"]
    .nunique()
)

rows = []
for cohort, size in cohort_size.items():
    d = df_cohort[df_cohort["First_Month"] == cohort]
    row = {"First_Month": str(cohort), "Tổng KH": int(size)}

    for m in range(1, MAX_MONTH + 1):
        kh_quay_lai = d[
            (d["Cohort_Index"] >= 1) & (d["Cohort_Index"] <= m)
        ]["Số_điện_thoại"].nunique()
        row[f"Sau {m} tháng"] = round(kh_quay_lai / size * 100, 2) if size else 0

    rows.append(row)

retention = pd.DataFrame(rows)

if not retention.empty:
    total_kh = retention["Tổng KH"].sum()
    grand = {"First_Month": "Grand Total", "Tổng KH": int(total_kh)}

    for c in retention.columns:
        if c.startswith("Sau"):
            grand[c] = round(
                (retention[c] * retention["Tổng KH"]).sum() / total_kh, 2
            ) if total_kh else 0

    retention = pd.concat([retention, pd.DataFrame([grand])], ignore_index=True)


# =====================================================
# DISPLAY
# =====================================================
st.subheader("🏅 Cohort Retention – Cộng dồn (%)")

if retention.empty:
    st.info("Không có dữ liệu cohort.")
else:
    retention_show = retention.copy()

    if "Tổng KH" in retention_show.columns:
        retention_show["Tổng KH"] = retention_show["Tổng KH"].apply(fmt_int)

    for c in retention_show.columns:
        if c.startswith("Sau"):
            retention_show[c] = retention_show[c].apply(lambda v: fmt_pct(v, 2))

    show_df(retention_show, title=None)


# =====================================================
# RESET FILTERS
# =====================================================
with st.sidebar:
    if st.button("🔄 Reset filters"):
        for k in [
            "loaiCT_filter",
            "brand_filter",
            "region_filter",
            "store_filter",
        ]:
            st.session_state.pop(k, None)
        st.rerun()