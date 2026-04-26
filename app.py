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
# LOAD ALL PARQUET SUMMARIES FROM GITHUB
# ------------------------------------------------------------
@st.cache_data(ttl=60)
def load_all_summaries():
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        files = [
            "daily_metrics.parquet",
            "daily_fallout.parquet",
            "daily_process.parquet",
            "daily_subchannel.parquet"
        ]
        data = {}
        for fname in files:
            contents = repo.get_contents(f"summary/{fname}")
            file_content = base64.b64decode(contents.content)
            temp = f"temp_{fname}"
            with open(temp, "wb") as f:
                f.write(file_content)
            df = pd.read_parquet(temp)
            os.remove(temp)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            data[fname.replace(".parquet", "")] = df
        return data["daily_metrics"], data["daily_fallout"], data["daily_process"], data["daily_subchannel"]
    except Exception as e:
        st.error(f"Failed to load summary data: {e}")
        st.code(traceback.format_exc())
        return None, None, None, None

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

daily_metrics, daily_fallout, daily_process, daily_subchannel = load_all_summaries()
if daily_metrics is None:
    st.stop()

# ------------------------------
# DATE RANGE SELECTOR
# ------------------------------
min_date = daily_metrics["date"].min()
max_date = daily_metrics["date"].max()
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
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end

# Filter each table by date range
filtered_metrics = daily_metrics[(daily_metrics["date"] >= start_date) & (daily_metrics["date"] <= end_date)].copy()
filtered_fallout = daily_fallout[(daily_fallout["date"] >= start_date) & (daily_fallout["date"] <= end_date)].copy()
filtered_process = daily_process[(daily_process["date"] >= start_date) & (daily_process["date"] <= end_date)].copy()
filtered_sub = daily_subchannel[(daily_subchannel["date"] >= start_date) & (daily_subchannel["date"] <= end_date)].copy()

st.sidebar.markdown(f"**Data period:** {start_date} to {end_date}")

# ------------------------------
# HOME PAGE
# ------------------------------
if menu == "Home":
    st.header("📊 Area of Operations Analysis (AOA)")

    # ----- 1. Process state breakdown as cards (icon, name, percentage | total) -----
    st.subheader("📋 Status Breakdown")
    if not filtered_process.empty:
        # Aggregate counts per state over the date range
        process_agg = filtered_process.groupby("process_state")["count"].sum().reset_index()
        total_state_orders = process_agg["count"].sum()
        process_agg["percentage"] = (process_agg["count"] / total_state_orders * 100).round(1)
        # Sort by percentage descending
        process_agg = process_agg.sort_values("percentage", ascending=False)

        # Define icon mapping (you can extend)
        icon_map = {
            "PENDING_CUSTOMER_VERIFICATION": "🕒",
            "PROVISION_START": "⚙️",
            "TECH_ASSIGNED": "👨‍🔧",
            "PENDING_APPOINTMENT_CREATION": "📅",
            "PENDING_CONTRACT_APPROVAL": "✍️",
            "PROVISION_ISSUED": "📄",
            "COMPLETED": "✅",
            "OSS_TESTING_SERVICE": "🧪",
            "RE": "🔄",
            "FALLOUT": "⚠️",
            "ODP_AVAILABLE": "🔌",
            "CANCELLED": "❌",
            "PENDING_PAYMENT_FOLLOWUP": "💳",
            "PAYMENT_INPROGRESS": "💰",
            "CANCEL_OSM_COMPLETED": "🚫",
            "TSEL_ACTIVATION_FALLOUT": "📡",
            "CANCEL_ORDER_INPROGRESS": "⏹️",
            "TECH_ARRIVED": "🚐",
            "CANCELLED_SLA": "⏰",
            "PENDING_DUNNING_PAYMENT_FOLLOWUP": "📞",
            "PENDING_PAYMENT": "💵",
            "TECH_PICKED_UP": "🔧",
            "TECH_ON_THE_WAY": "🚗",
            "CONTRACT_APPROVED": "✅"
        }

        # Create a grid of cards (4 columns per row)
        num_cols = 4
        rows = [process_agg.iloc[i:i+num_cols] for i in range(0, len(process_agg), num_cols)]
        for row in rows:
            cols = st.columns(num_cols, gap="small")
            for idx, (_, row_data) in enumerate(row.iterrows()):
                state = row_data["process_state"]
                count = row_data["count"]
                pct = row_data["percentage"]
                icon = icon_map.get(state, "📊")
                with cols[idx]:
                    st.markdown(
                        f"""
                        <div style="text-align: center; padding: 0.5rem; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9;">
                            <div style="font-size: 2.5rem;">{icon}</div>
                            <div style="font-weight: bold; margin-top: 0.25rem;">{state.replace('_', ' ').title()}</div>
                            <div style="font-size: 1.2rem; font-weight: bold;">{pct}% | {count:,}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
    else:
        st.info("No process state data in selected period.")

    # ----- 2. IO/RE/PS trend (smooth line with markers and values) -----
    st.subheader("📈 IO / RE / PS TREND")
    if not filtered_metrics.empty:
        trend_data = filtered_metrics.melt(id_vars=["date"], value_vars=["IO", "RE", "PS"],
                                           var_name="Stage", value_name="Count")
        fig_trend = px.line(trend_data, x="date", y="Count", color="Stage",
                            title="Daily Orders Progress",
                            labels={"date": "Date", "Count": "Number of Orders"},
                            line_shape="spline", markers=True)
        # Add text labels at each point
        for stage in ["IO", "RE", "PS"]:
            stage_data = filtered_metrics[["date", stage]]
            for _, row in stage_data.iterrows():
                fig_trend.add_annotation(x=row["date"], y=row[stage],
                                         text=str(row[stage]),
                                         showarrow=False,
                                         font=dict(size=9),
                                         yshift=10)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No data in selected date range")

    # ----- 3. Fallout trend (date vs fallout category) -----
    st.subheader("⚠️ TREND FALLOUT KENDALA")
    if not filtered_fallout.empty:
        fig_fallout = px.line(filtered_fallout, x="date", y="count", color="fallout_category",
                              title="Daily Fallout Breakdown",
                              labels={"date": "Date", "count": "Number of Fallouts", "fallout_category": "Kendala"},
                              line_shape="spline", markers=True)
        st.plotly_chart(fig_fallout, use_container_width=True)
    else:
        st.info("No fallout data in selected period")

    # ----- 4. Subchannel donut chart (Status Order) -----
    st.subheader("📊 STATUS ORDER (by Subchannel)")
    if not filtered_sub.empty:
        sub_agg = filtered_sub.groupby("subchannel")["count"].sum().reset_index()
        sub_agg["percentage"] = (sub_agg["count"] / sub_agg["count"].sum() * 100).round(1)
        fig_donut = px.pie(sub_agg, values="count", names="subchannel", hole=0.4,
                           title=f"Order Distribution by Subchannel (Total: {sub_agg['count'].sum():,})",
                           labels={"subchannel": "Channel", "count": "Orders"})
        fig_donut.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No subchannel data in selected period")

    # ----- 5. Placeholder for interactive map -----
    st.subheader("🗺️ Interactive Map (Coming Soon)")
    st.info("Map will be added once data is ready.")

    # ----- 6. Additional stats from filtered_metrics -----
    st.subheader("📌 Additional Metrics")
    total_io = filtered_metrics["IO"].sum()
    total_re = filtered_metrics["RE"].sum()
    total_ps = filtered_metrics["PS"].sum()
    total_fallout = filtered_metrics["Fallout"].sum()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total IO", f"{total_io:,}")
    with col2:
        st.metric("Total RE", f"{total_re:,}")
    with col3:
        st.metric("Total PS (Complete)", f"{total_ps:,}")
    with col4:
        st.metric("Total Fallout", f"{total_fallout:,}")

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