import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import base64
import os
import traceback
from github import Auth, Github, GithubException

st.set_page_config(page_title="Sales Dashboard - Manado", layout="wide")

# ------------------------------
# LOGIN
# ------------------------------
users = {
    "it_admin":    {"password": "itpass",   "role": "IT",                "company": None},
    "manager":     {"password": "admin123", "role": "Manager",           "company": None},
    "supervisor":  {"password": "sup456",   "role": "Supervisor",        "company": None},
    "agency1":     {"password": "agency1",  "role": "Agency Manager",    "company": "KOPEGTEL MANGGATA"},
    "agency2":     {"password": "agency2",  "role": "Agency Team Leader","company": "CV GLOBAL MANDIRI MOBILINDO"},
    "johndoe":     {"password": "1234",     "role": "Manager",           "company": None},
}

def check_login():
    if "logged_in" in st.session_state and st.session_state.logged_in:
        return True
    if "user" in st.query_params:
        username = st.query_params["user"]
        if username in users:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = users[username]["role"]
            st.session_state.company = users[username]["company"]
            return True
    if not st.session_state.get("logged_in", False):
        st.title("🔐 Login to Sales Dashboard")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username in users and users[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = users[username]["role"]
                st.session_state.company = users[username]["company"]
                st.query_params["user"] = username
                st.rerun()
            else:
                st.error("Invalid username or password")
        return False
    return True

def logout():
    for key in ["logged_in", "username", "role", "company"]:
        if key in st.session_state:
            del st.session_state[key]
    st.query_params.clear()
    st.rerun()

# ------------------------------------------------------------
# LOAD PARQUET SUMMARIES FROM GITHUB
# ------------------------------------------------------------
@st.cache_data(ttl=60)
def load_summary_data():
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        files = ["daily.parquet", "fallout.parquet", "status.parquet", "channel.parquet", "top_channels.parquet"]
        data = {}
        for fname in files:
            contents = repo.get_contents(f"summary/{fname}")
            file_content = base64.b64decode(contents.content)
            temp = f"temp_{fname}"
            with open(temp, "wb") as f:
                f.write(file_content)
            df = pd.read_parquet(temp)
            os.remove(temp)
            data[fname.replace(".parquet", "")] = df
        return data["daily"], data["fallout"], data["status"], data["channel"], data["top_channels"]
    except Exception as e:
        st.error(f"Failed to load summary data: {e}")
        st.code(traceback.format_exc())
        return None, None, None, None, None

# ------------------------------
# MAIN APP
# ------------------------------
if not check_login():
    st.stop()

with st.sidebar:
    st.title("📋 MENU")
    if st.button("🚪 Logout", use_container_width=True):
        logout()
    st.markdown("---")
    if st.session_state.role == "IT":
        st.subheader("📂 Data Management")
        st.info("Data is pre‑aggregated. To update, run aggregation script locally and upload new Parquet files to GitHub.")
    menu = st.radio("Go to", ["Home", "Branch Performance", "Agency Performance", "Alpro", "Collection"], index=0)

daily, fallout, status, channel, top = load_summary_data()
if daily is None:
    st.stop()

# ------------------------------
# DATE RANGE (using direct date objects)
# ------------------------------
min_date = daily["date"].min()
max_date = daily["date"].max()
default_start = min_date
default_end = max_date

st.markdown("## 🏠 SALES DASHBOARD – BRANCH MANADO")
col_date, col_user = st.columns([3,1])
with col_date:
    date_range = st.date_input("📅 Select Date Range", value=(default_start, default_end),
                               min_value=min_date, max_value=max_date)
with col_user:
    st.write(f"👤 **{st.session_state.username}** | Role: {st.session_state.role}")

if len(date_range) == 2:
    start, end = date_range
    filtered_daily = daily[(daily["date"] >= start) & (daily["date"] <= end)]
else:
    filtered_daily = daily.copy()
    start, end = default_start, default_end

st.sidebar.markdown(f"**Data period:** {start} to {end}")

# ------------------------------
# HOME PAGE
# ------------------------------
if menu == "Home":
    st.header("📊 Area of Operations Analysis (AOA)")

    total_orders = filtered_daily["IO"].sum()
    complete_orders = filtered_daily["Complete"].sum()
    fallout_orders = filtered_daily["Fallout"].sum()
    complete_pct = (complete_orders / total_orders * 100) if total_orders > 0 else 0
    fallout_pct = (fallout_orders / total_orders * 100) if total_orders > 0 else 0

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("📉 FALLOUT", f"{fallout_pct:.1f}%", delta=f"{fallout_orders} orders")
    with col_b:
        st.metric("✅ COMPLETE", f"{complete_pct:.1f}%", delta=f"{complete_orders} orders")

    # IO/RE/PS trend
    st.subheader("📈 IO / RE / PS TREND")
    trend = filtered_daily[["date", "IO", "RE", "PS"]].copy()
    trend.rename(columns={"date": "Date"}, inplace=True)
    if not trend.empty:
        fig_trend = px.line(trend, x="Date", y=["IO", "RE", "PS"],
                            title="Daily Orders Progress",
                            labels={"value": "Count", "variable": "Stage"})
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No data in selected date range")

    # Fallout breakdown (global, not date‑filtered – you can enhance later)
    st.subheader("⚠️ TREND FALLOUT KENDALA")
    if not fallout.empty:
        fig_fallout = px.bar(fallout, x="category", y="count", color="category",
                             title="Fallout by Category (full data)")
        st.plotly_chart(fig_fallout, use_container_width=True)
    else:
        st.info("No fallout data")

    # Status donut
    st.subheader("📊 STATUS ORDER")
    if not status.empty:
        fig_donut = px.pie(status, values="count", names="status", hole=0.4,
                           title="Order Status Distribution")
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No status data")

    # Channel breakdown
    st.subheader("📢 Order Input by Channel")
    if not channel.empty:
        fig_channel = px.bar(channel, x="source", y="count", color="source",
                             title="Orders by Sales Force vs Other Channels")
        st.plotly_chart(fig_channel, use_container_width=True)
    else:
        st.info("No channel data")

    # Top channels
    if not top.empty:
        st.subheader("📢 Top Order Channels")
        fig_top = px.bar(top, x="channel", y="count", color="channel",
                         title="Top 5 Order Channels")
        st.plotly_chart(fig_top, use_container_width=True)

    # Stats
    st.subheader("📌 STATS & ORDER")
    avg_completion = 0  # we don't have completion days in summaries now
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("Avg Completion (days)", "Coming soon")
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
    st.info("Detailed branch performance – coming soon.")
elif menu == "Agency Performance":
    st.header("🤝 Agency Performance")
    st.info("Detailed agency performance – coming soon.")
elif menu == "Alpro":
    st.header("🔌 Alpro (ODP Production)")
    st.info("Detailed Alpro page – coming soon.")
elif menu == "Collection":
    st.header("💰 Collection (C3MR, PRANPC and CT0)")
    st.info("Detailed Collection page – coming soon.")