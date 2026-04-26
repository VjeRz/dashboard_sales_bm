import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import base64
import os
import traceback
from github import Auth, Github, GithubException

# ------------------------------
# PAGE CONFIG
# ------------------------------
st.set_page_config(page_title="Sales Dashboard - Manado", layout="wide")

# ------------------------------
# LOGIN (with roles)
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
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🔐 Login to Sales Dashboard")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username in users and users[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = users[username]["role"]
                st.session_state.company = users[username]["company"]
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid username or password")
        return False
    return True

# ------------------------------------------------------------
# DATA LOADING FROM GITHUB (CSV with dayfirst)
# ------------------------------------------------------------
@st.cache_data(ttl=60)
def load_orders_from_github():
    """Download orders.csv from private GitHub repo and parse Indonesian dates."""
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        contents = repo.get_contents("orders.csv")
        
        file_content = base64.b64decode(contents.content)
        temp_file = "temp_orders.csv"
        with open(temp_file, "wb") as f:
            f.write(file_content)
        
        # Read all columns as string first to avoid automatic date conversion
        df = pd.read_csv(temp_file, dtype=str)
        os.remove(temp_file)
        
        # Convert Indonesian date columns (DD/MM/YYYY HH:MM:SS)
        date_cols = ["io_ts", "re_ts", "ps_ts", "provi_ts", "fallout_ts", "completed_ts"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
        return df
    except GithubException as e:
        if e.status == 404:
            st.warning("No orders.csv found. Please ask IT to upload the file.")
        else:
            st.error(f"GitHub error: {e}")
        return None
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.code(traceback.format_exc())
        return None

# ------------------------------------------------------------
# UPLOAD TO GITHUB (IT role)
# ------------------------------------------------------------
def upload_to_github(uploaded_file, file_name="orders.csv"):
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        file_bytes = uploaded_file.getvalue()
        
        try:
            contents = repo.get_contents(file_name)
            repo.update_file(
                contents.path,
                f"Update {file_name} from Streamlit dashboard",
                file_bytes,
                contents.sha
            )
            st.success(f"✅ {file_name} updated successfully!")
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    file_name,
                    f"Create {file_name} from Streamlit dashboard",
                    file_bytes
                )
                st.success(f"✅ {file_name} created successfully!")
            else:
                raise e
    except Exception as e:
        st.error(f"Upload failed: {e}")

# ------------------------------------------------------------
# LAST UPDATE TIME
# ------------------------------------------------------------
def get_last_update_time():
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        commits = repo.get_commits(path="orders.csv")
        if commits.totalCount > 0:
            return commits[0].commit.author.date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return "Unknown"
    except:
        return "Unknown"

# ------------------------------------------------------------
# ROLE FILTER (agency users only see their company)
# ------------------------------------------------------------
def apply_role_filters(df):
    role = st.session_state.role
    company = st.session_state.company
    if role in ["Agency Manager", "Agency Team Leader"] and company is not None:
        if "sf_company_name" in df.columns:
            df = df[df["sf_company_name"] == company]
    return df

# ------------------------------
# MAIN APP
# ------------------------------
if not check_login():
    st.stop()

# Sidebar
with st.sidebar:
    st.title("📋 MENU")
    
    if st.button("🚪 Logout", use_container_width=True):
        for key in ["logged_in", "username", "role", "company"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    
    if st.session_state.role == "IT":
        st.subheader("📂 Data Management")
        uploaded_file = st.file_uploader("Upload Orders CSV file (UTF-8)", type=["csv"])
        if uploaded_file is not None:
            upload_to_github(uploaded_file, "orders.csv")
            st.cache_data.clear()
            st.rerun()
        st.caption(f"📅 Last updated: {get_last_update_time()}")
        st.markdown("---")
    
    menu = st.radio(
        "Go to",
        ["Home", "Branch Performance", "Agency Performance", "Alpro", "Collection"],
        index=0
    )

# Load data
orders_raw = load_orders_from_github()
if orders_raw is None:
    st.stop()

orders = apply_role_filters(orders_raw.copy())

# Date range filter (using io_ts)
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

if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (orders["io_ts"] >= pd.to_datetime(start_date)) & (orders["io_ts"] <= pd.to_datetime(end_date))
    filtered = orders[mask].copy()
else:
    filtered = orders.copy()
    start_date, end_date = default_start, default_end

st.sidebar.markdown(f"**Data period:** {start_date} to {end_date}")

# ------------------------------
# HOME PAGE (AOA Summary)
# ------------------------------
if menu == "Home":
    st.header("📊 Area of Operations Analysis (AOA)")

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

    # IO/RE/PS trend
    st.subheader("📈 IO / RE / PS TREND")
    daily = filtered.groupby(filtered["io_ts"].dt.date).agg(
        IO=("order_id", "count"),
        RE=("re_ts", lambda x: x.notna().sum()),
        PS=("ps_ts", lambda x: x.notna().sum())
    ).reset_index()
    daily.rename(columns={"io_ts": "Date"}, inplace=True)
    if not daily.empty:
        fig_trend = px.line(daily, x="Date", y=["IO", "RE", "PS"],
                            title="Daily Orders Progress",
                            labels={"value": "Count", "variable": "Stage"})
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No data in selected date range")

    # Fallout & Status
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("⚠️ TREND FALLOUT KENDALA")
        if "fallout_category" in filtered.columns and filtered["fallout_category"].notna().any():
            fallout_counts = filtered["fallout_category"].value_counts().reset_index()
            fallout_counts.columns = ["Kendala", "Jumlah"]
            fig_fallout = px.bar(fallout_counts, x="Kendala", y="Jumlah", color="Kendala",
                                 title="Fallout by Category")
            st.plotly_chart(fig_fallout, use_container_width=True)
        else:
            st.info("No fallout data in selected period")

    with col_right:
        st.subheader("📊 STATUS ORDER")
        if "process_state" in filtered.columns:
            status_counts = filtered["process_state"].value_counts()
            status_map = {
                "PROVISION_ISSUED": "Provision Issued",
                "TECH_ASSIGNED": "Tecn Assigned",
                "COMPLETED": "Complete"
            }
            renamed = {status_map.get(k, k): v for k, v in status_counts.items()}
            status_df = pd.DataFrame(list(renamed.items()), columns=["Status", "Count"])
            fig_donut = px.pie(status_df, values="Count", names="Status", hole=0.4,
                               title="Order Status Distribution")
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No process_state column")

    # Channel breakdown
    st.subheader("📢 Order Input by Channel")
    filtered["source_type"] = filtered["sf_name"].apply(lambda x: "Sales Force" if pd.notna(x) else "Other Channel")
    channel_counts = filtered["source_type"].value_counts().reset_index()
    channel_counts.columns = ["Source", "Orders"]
    fig_channel = px.bar(channel_counts, x="Source", y="Orders", color="Source",
                         title="Orders by Sales Force vs Other Channels")
    st.plotly_chart(fig_channel, use_container_width=True)

    if "channel_name" in filtered.columns:
        st.subheader("📢 Top Order Channels")
        top_channels = filtered["channel_name"].value_counts().head(5).reset_index()
        top_channels.columns = ["Channel", "Orders"]
        fig_top = px.bar(top_channels, x="Channel", y="Orders", color="Channel",
                         title="Top 5 Order Channels")
        st.plotly_chart(fig_top, use_container_width=True)

    # Stats
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
    st.info("Detailed branch performance – coming soon. Will use orders, sales_force, alpro, collection, djp, new_lop.")
elif menu == "Agency Performance":
    st.header("🤝 Agency Performance")
    st.info("Detailed agency performance – coming soon. Agency users see only their company data.")
elif menu == "Alpro":
    st.header("🔌 Alpro (ODP Production)")
    st.info("Detailed Alpro page – coming soon. Will use alpro.xlsx.")
elif menu == "Collection":
    st.header("💰 Collection (C3MR, PRANPC and CT0)")
    st.info("Detailed Collection page – coming soon.")