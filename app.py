import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ------------------------------
# PAGE CONFIG
# ------------------------------
st.set_page_config(page_title="Sales Dashboard - Manado", layout="wide")

# ------------------------------
# HARD-CODED LOGIN (demo)
# ------------------------------
import streamlit as st

def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🔐 Login to Sales Dashboard")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            # Check credentials from secrets
            if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = st.secrets["users"].get(username, "Viewer")
                st.session_state.company = st.secrets["company"].get(username, None)
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid username or password")
        return False
    return True

# ------------------------------
# LOAD DATA (cached, using Excel)
# ------------------------------
@st.cache_data
def load_orders():
    df = pd.read_excel("Order Data Sample.xlsx", sheet_name="Sheet1")
    # Convert date columns to datetime
    date_cols = ["io_ts", "re_ts", "ps_ts", "provi_ts", "fallout_ts", "completed_ts"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

# ------------------------------
# ROLE FILTERS (based on sf_company_name)
# ------------------------------
def apply_role_filters(df):
    role = st.session_state.role
    company = st.session_state.company
    if role in ["Agency Manager", "Agency Team Leader"] and company is not None:
        if "sf_company_name" in df.columns:
            df = df[df["sf_company_name"] == company]
    return df

# ------------------------------
# MAIN APP (after login)
# ------------------------------

import streamlit as st

@st.cache_data
def load_orders():
    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, sheet_name="Sheet1")
        # ... rest of processing
        return df
    else:
        st.warning("Please upload your order data file to continue")
        st.stop()


if not check_login():
    st.stop()

orders_raw = load_orders()
orders = apply_role_filters(orders_raw.copy())

# Global date filter – using io_ts
min_date = orders["io_ts"].min()
max_date = orders["io_ts"].max()
if pd.isna(min_date):
    st.error("No valid io_ts dates found in data")
    st.stop()

default_start = min_date.date()
default_end = max_date.date()

# Top bar
st.markdown("## 🏠 SALES DASHBOARD – BRANCH MANADO")
col_date, col_user = st.columns([3,1])
with col_date:
    date_range = st.date_input(
        "📅 Select Date Range",
        value=(default_start, default_end),
        min_value=min_date,
        max_value=max_date
    )
with col_user:
    st.write(f"👤 **{st.session_state.username}** | Role: {st.session_state.role}")
    if st.button("🚪 Logout"):
        for key in ["logged_in", "username", "role", "company"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Filter by date range (using io_ts)
if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (orders["io_ts"] >= pd.to_datetime(start_date)) & (orders["io_ts"] <= pd.to_datetime(end_date))
    filtered = orders[mask].copy()
else:
    filtered = orders.copy()
    start_date, end_date = default_start, default_end

# Sidebar menu
with st.sidebar:
    st.title("📋 MENU")
    menu = st.radio(
        "Go to",
        ["Home", "Branch Performance", "Agency Performance", "Alpro"],
        index=0
    )
    st.markdown("---")
    st.caption(f"Data period: {start_date} to {end_date}")

# ------------------------------
# HOME PAGE (AOA Summary)
# ------------------------------
if menu == "Home":
    st.header("📊 Area of Operations Analysis (AOA)")

    # -------- Core metrics ----------
    total_orders = len(filtered)
    complete_orders = filtered["ps_ts"].notna().sum() if "ps_ts" in filtered else 0
    fallout_orders = filtered["fallout_category"].notna().sum() if "fallout_category" in filtered else 0
    complete_pct = (complete_orders / total_orders * 100) if total_orders > 0 else 0
    fallout_pct = (fallout_orders / total_orders * 100) if total_orders > 0 else 0

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("📉 FALLOUT", f"{fallout_pct:.1f}%", delta=f"{fallout_orders} orders")
    with col_b:
        st.metric("✅ COMPLETE", f"{complete_pct:.1f}%", delta=f"{complete_orders} orders")

    # -------- IO/RE/PS Trend (line chart) – using io_ts as date ----------
    st.subheader("📈 IO / RE / PS TREND")
    daily = filtered.groupby(filtered["io_ts"].dt.date).agg(
        IO=("order_id", "count"),            # count of order_id
        RE=("re_ts", lambda x: x.notna().sum()),
        PS=("ps_ts", lambda x: x.notna().sum())
    ).reset_index()
    daily.rename(columns={"io_ts": "Date"}, inplace=True)
    if not daily.empty:
        fig_trend = px.line(daily, x="Date", y=["IO", "RE", "PS"],
                            title="Daily Orders Progress (IO = Input, RE = Past Registration, PS = Put in Service)",
                            labels={"value": "Count", "variable": "Stage"})
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No data in selected date range")

    # -------- Fallout Breakdown + Status Donut ----------
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("⚠️ TREND FALLOUT KENDALA")
        if "fallout_category" in filtered.columns and filtered["fallout_category"].notna().any():
            fallout_counts = filtered["fallout_category"].value_counts().reset_index()
            fallout_counts.columns = ["Kendala", "Jumlah"]
            fig_fallout = px.bar(fallout_counts, x="Kendala", y="Jumlah",
                                 color="Kendala", title="Fallout by Category (Current Period)")
            st.plotly_chart(fig_fallout, use_container_width=True)
        else:
            st.info("No fallout data in selected period")

    with col_right:
        st.subheader("📊 STATUS ORDER")
        if "process_state" in filtered.columns:
            status_counts = filtered["process_state"].value_counts()
            # Map to friendly names (optional)
            status_map = {
                "PROVISION_ISSUED": "Provision Issued",
                "TECH_ASSIGNED": "Tecn Assigned",
                "COMPLETED": "Complete"
            }
            renamed = {}
            for k, v in status_counts.items():
                renamed[status_map.get(k, k)] = v
            status_df = pd.DataFrame(list(renamed.items()), columns=["Status", "Count"])
            fig_donut = px.pie(status_df, values="Count", names="Status",
                               title="Order Status Distribution", hole=0.4)
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No process_state column found")

    # -------- Channel Breakdown (Sales Force vs Other Channels) ----------
    st.subheader("📢 Order Input by Channel")
    # Determine if order came from sales force (sf_name not null) or other channel
    filtered["source_type"] = filtered["sf_name"].apply(lambda x: "Sales Force" if pd.notna(x) else "Other Channel")
    # Also show breakdown by channel_name if needed
    channel_counts = filtered["source_type"].value_counts().reset_index()
    channel_counts.columns = ["Source", "Orders"]
    fig_channel = px.bar(channel_counts, x="Source", y="Orders", color="Source",
                         title="Orders by Sales Force vs Other Channels")
    st.plotly_chart(fig_channel, use_container_width=True)

    # Optional: show top channels (from channel_name column)
    if "channel_name" in filtered.columns:
        st.subheader("📢 Top Order Channels")
        top_channels = filtered["channel_name"].value_counts().head(5).reset_index()
        top_channels.columns = ["Channel", "Orders"]
        fig_top = px.bar(top_channels, x="Channel", y="Orders", color="Channel",
                         title="Top 5 Order Channels")
        st.plotly_chart(fig_top, use_container_width=True)

    # Additional Stats
    st.subheader("📌 STATS & ORDER")
    avg_completion = 0
    if "ps_ts" in filtered and "io_ts" in filtered:
        completion_time = (filtered["ps_ts"] - filtered["io_ts"]).dropna()
        if len(completion_time) > 0:
            avg_completion = completion_time.mean().days
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("Avg Completion (days)", f"{avg_completion:.1f}")
    with col_s2:
        st.metric("Total Orders", total_orders)
    with col_s3:
        st.metric("Active Orders", total_orders - complete_orders)
    with col_s4:
        st.metric("Fallout Rate", f"{fallout_pct:.1f}%")

# ------------------------------
# OTHER PAGES (placeholders)
# ------------------------------
elif menu == "Branch Performance":
    st.header("🏢 Branch Performance")
    st.info("Detailed branch performance – coming soon. Will use separate branch/region data.")
elif menu == "Agency Performance":
    st.header("🤝 Agency Performance")
    st.info("Detailed agency performance – coming soon. Agency users see only their company.")
elif menu == "Alpro":
    st.header("🔌 Alpro (ODP Production)")
    st.info("Detailed Alpro page – coming soon. Will use separate ODP data.")