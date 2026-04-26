import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import base64
import os
import traceback
import json
from github import Auth, Github, GithubException

st.set_page_config(page_title="Sales Dashboard - Manado", layout="wide")

# ------------------------------
# LOGIN (with query param persistence)
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
def load_all_data():
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        files = {
            "daily_metrics": "summary/daily_metrics.parquet",
            "daily_fallout": "summary/daily_fallout.parquet",
            "daily_process": "summary/daily_process.parquet",
            "daily_subchannel": "summary/daily_subchannel.parquet",
            "salesforce_summary": "summary/salesforce_summary.parquet",
            "odp_summary": "summary/odp_summary.parquet"
        }
        data = {}
        for name, path in files.items():
            contents = repo.get_contents(path)
            file_content = base64.b64decode(contents.content)
            temp = f"temp_{name}.parquet"
            with open(temp, "wb") as f:
                f.write(file_content)
            df = pd.read_parquet(temp)
            os.remove(temp)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            data[name] = df
        return data["daily_metrics"], data["daily_fallout"], data["daily_process"], data["daily_subchannel"], data["salesforce_summary"], data["odp_summary"]
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.code(traceback.format_exc())
        return None, None, None, None, None, None

# ------------------------------------------------------------
# LOAD GEOJSON WITH DEBUGGING
# ------------------------------------------------------------
@st.cache_data
def load_geojson():
    try:
        g = Github(auth=Auth.Token(st.secrets["GITHUB_TOKEN"]))
        repo = g.get_repo(st.secrets["DATA_REPO"])
        # Try root first, then summary
        try:
            contents = repo.get_contents("indonesia.json")
            st.info("✅ Found indonesia.json in root")
        except:
            contents = repo.get_contents("summary/indonesia.json")
            st.info("✅ Found indonesia.json in summary/ folder")
        
        file_content = base64.b64decode(contents.content)
        # DEBUG: print first 300 characters
        st.subheader("Debug: First 300 characters of indonesia.json")
        st.code(file_content[:300].decode('utf-8', errors='replace'))
        
        geojson = json.loads(file_content.decode('utf-8'))
        props = geojson["features"][0]["properties"]
        if "PROVINSI" in props:
            featureid = "PROVINSI"
        elif "NAME_1" in props:
            featureid = "NAME_1"
        elif "name" in props:
            featureid = "name"
        else:
            featureid = list(props.keys())[0]
        st.success(f"GeoJSON loaded. Using property: {featureid}")
        return geojson, featureid
    except Exception as e:
        st.error(f"Indonesia JSON error: {e}")
        return None, None

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
        st.info("Data is pre‑aggregated. To update, run aggregation scripts and upload new Parquet files.")
    menu = st.radio("Go to", ["Home", "Branch Performance", "Agency Performance", "Alpro", "Collection"], index=0)

daily_metrics, daily_fallout, daily_process, daily_subchannel, sf_summary, odp_summary = load_all_data()
if daily_metrics is None:
    st.stop()

# ------------------------------
# DATE RANGE FILTER (for orders)
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

filtered_metrics = daily_metrics[(daily_metrics["date"] >= start_date) & (daily_metrics["date"] <= end_date)].copy()
filtered_fallout = daily_fallout[(daily_fallout["date"] >= start_date) & (daily_fallout["date"] <= end_date)].copy()
filtered_process = daily_process[(daily_process["date"] >= start_date) & (daily_process["date"] <= end_date)].copy()
filtered_sub = daily_subchannel[(daily_subchannel["date"] >= start_date) & (daily_subchannel["date"] <= end_date)].copy()

st.sidebar.markdown(f"**Orders period:** {start_date} to {end_date}")

# ------------------------------
# HOME PAGE
# ------------------------------
if menu == "Home":
    st.header("📊 Area of Operations Analysis (AOA)")

    # ----- Interactive Map & Regional Cards -----
    st.subheader("🗺️ Regional Performance (Click on a province)")
    geojson, featureid = load_geojson()
    if sf_summary is not None and odp_summary is not None and geojson is not None:
        # Prepare data
        sf_renamed = sf_summary.rename(columns={"PROVINSI": "province"})
        odp_renamed = odp_summary.rename(columns={"PROVINSI": "province"})
        merged = sf_renamed.merge(odp_renamed, on="province", how="outer").fillna(0)
        for col in ["Agencies", "CTB", "SalesForce", "Technicians", "STO", "ODP", "Port", "PortGoLive2025", "Occupancy"]:
            if col in merged.columns:
                merged[col] = merged[col].astype(float)

        # Create choropleth map (auto-zoom to Sulawesi)
        fig_map = px.choropleth(merged,
                                geojson=geojson,
                                locations="province",
                                featureidkey=f"properties.{featureid}",
                                color="Agencies",
                                color_continuous_scale="Blues",
                                range_color=(0, merged["Agencies"].max() or 1),
                                labels={"Agencies": "Number of Agencies"},
                                hover_name="province",
                                hover_data=["Agencies", "SalesForce", "Technicians", "STO", "ODP", "Port", "PortGoLive2025", "Occupancy"])
        # Zoom to Sulawesi
        fig_map.update_geos(fitbounds="locations", visible=False)
        fig_map.update_layout(
            geo=dict(center=dict(lon=122.5, lat=0.8), projection_scale=3.5),
            margin={"r":0, "t":0, "l":0, "b":0},
            height=500
        )

        # Capture click
        if "selected_province" not in st.session_state:
            st.session_state.selected_province = None
        selected = st.plotly_chart(fig_map, use_container_width=True, key="map", on_select="rerun")
        if selected and selected.get("selection") and selected["selection"].get("points"):
            point = selected["selection"]["points"][0]
            st.session_state.selected_province = point.get("location", None)
        if st.session_state.selected_province is None and not merged.empty:
            st.session_state.selected_province = merged.iloc[0]["province"]

        # Get row for selected province
        if st.session_state.selected_province is not None:
            row = merged[merged["province"] == st.session_state.selected_province]
            if not row.empty:
                row = row.iloc[0]
            else:
                row = merged.iloc[0]
        else:
            row = merged.iloc[0]

        # Display metric cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Agencies", f"{int(row['Agencies']):,}")
        with col2:
            st.metric("🌐 CTB", f"{int(row['CTB']):,}")
        with col3:
            st.metric("👥 SalesForce", f"{int(row['SalesForce']):,}")
        with col4:
            st.metric("🔧 Technicians", f"{int(row['Technicians']):,}")

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("📡 STO", f"{int(row['STO']):,}")
        with col6:
            st.metric("🔌 ODP", f"{int(row['ODP']):,}")
        with col7:
            st.metric("🌉 Port", f"{int(row['Port']):,}")
        with col8:
            st.metric("✅ Port Go Live 2025", f"{int(row['PortGoLive2025']):,}")

        st.metric("🏠 Occupancy", f"{row['Occupancy']:.1f}%")
        st.caption(f"Showing data for: **{st.session_state.selected_province}**")
    else:
        st.warning("Map data incomplete. Ensure salesforce_summary.parquet, odp_summary.parquet and indonesia.json are uploaded.")

    # ----- Process state cards (dark transparent theme) -----
    st.subheader("📋 Status Breakdown")
    if not filtered_process.empty:
        process_agg = filtered_process.groupby("process_state")["count"].sum().reset_index()
        total_state_orders = process_agg["count"].sum()
        process_agg["percentage"] = (process_agg["count"] / total_state_orders * 100).round(1)
        process_agg = process_agg.sort_values("percentage", ascending=False)

        icon_map = {
            "PENDING_CUSTOMER_VERIFICATION": "🕒", "PROVISION_START": "⚙️", "TECH_ASSIGNED": "👨‍🔧",
            "PENDING_APPOINTMENT_CREATION": "📅", "PENDING_CONTRACT_APPROVAL": "✍️", "PROVISION_ISSUED": "📄",
            "COMPLETED": "✅", "OSS_TESTING_SERVICE": "🧪", "RE": "🔄", "FALLOUT": "⚠️",
            "ODP_AVAILABLE": "🔌", "CANCELLED": "❌", "PENDING_PAYMENT_FOLLOWUP": "💳",
            "PAYMENT_INPROGRESS": "💰", "CANCEL_OSM_COMPLETED": "🚫", "TSEL_ACTIVATION_FALLOUT": "📡",
            "CANCEL_ORDER_INPROGRESS": "⏹️", "TECH_ARRIVED": "🚐", "CANCELLED_SLA": "⏰",
            "PENDING_DUNNING_PAYMENT_FOLLOWUP": "📞", "PENDING_PAYMENT": "💵", "TECH_PICKED_UP": "🔧",
            "TECH_ON_THE_WAY": "🚗", "CONTRACT_APPROVED": "✅"
        }
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
                        <div style="text-align: center; padding: 0.75rem; border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; background-color: rgba(0,0,0,0.5); backdrop-filter: blur(2px);">
                            <div style="font-size: 2.8rem; line-height: 1.2;">{icon}</div>
                            <div style="font-weight: 600; margin-top: 0.5rem; font-size: 0.9rem; color: #f0f0f0;">{state.replace('_', ' ').title()}</div>
                            <div style="font-size: 1.2rem; font-weight: bold; margin-top: 0.25rem; color: #ffffff;">{pct}% | {count:,}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
    else:
        st.info("No process state data in selected period.")

    # ----- IO/RE/PS trend with conversion rates -----
    st.subheader("📈 IO / RE / PS TREND")
    if not filtered_metrics.empty:
        trend_data = filtered_metrics.melt(id_vars=["date"], value_vars=["IO", "RE", "PS"],
                                           var_name="Stage", value_name="Count")
        fig_trend = px.line(trend_data, x="date", y="Count", color="Stage",
                            title="Daily Orders Progress",
                            labels={"date": "Date", "Count": "Number of Orders"},
                            line_shape="spline", markers=True)
        for stage in ["IO", "RE", "PS"]:
            stage_data = filtered_metrics[["date", stage]]
            for _, row in stage_data.iterrows():
                fig_trend.add_annotation(x=row["date"], y=row[stage],
                                         text=str(row[stage]),
                                         showarrow=False,
                                         font=dict(size=11, color="white"),
                                         yshift=10)
        st.plotly_chart(fig_trend, use_container_width=True)

        total_io = filtered_metrics["IO"].sum()
        total_re = filtered_metrics["RE"].sum()
        total_ps = filtered_metrics["PS"].sum()
        io_to_re = (total_re / total_io * 100) if total_io > 0 else 0
        io_to_ps = (total_ps / total_io * 100) if total_io > 0 else 0
        re_to_ps = (total_ps / total_re * 100) if total_re > 0 else 0
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("IO → RE", f"{io_to_re:.1f}%")
        with col_m2:
            st.metric("IO → PS", f"{io_to_ps:.1f}%")
        with col_m3:
            st.metric("RE → PS", f"{re_to_ps:.1f}%")
    else:
        st.info("No data in selected date range")

    # ----- Fallout trend (line + percentage bar) -----
    st.subheader("⚠️ TREND FALLOUT KENDALA")
    if not filtered_fallout.empty:
        fig_fallout = px.line(filtered_fallout, x="date", y="count", color="fallout_category",
                              title="Daily Fallout Breakdown",
                              labels={"date": "Date", "count": "Number of Fallouts", "fallout_category": "Kendala"},
                              line_shape="spline", markers=True)
        fig_fallout.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5))
        for cat in filtered_fallout["fallout_category"].unique():
            cat_data = filtered_fallout[filtered_fallout["fallout_category"] == cat]
            for _, row in cat_data.iterrows():
                if row["count"] > 0:
                    fig_fallout.add_annotation(x=row["date"], y=row["count"],
                                               text=str(row["count"]),
                                               showarrow=False,
                                               font=dict(size=10, color="white"),
                                               yshift=8)
        st.plotly_chart(fig_fallout, use_container_width=True)

        fallout_pct = filtered_fallout.groupby("fallout_category")["count"].sum().reset_index()
        total_fallout = fallout_pct["count"].sum()
        fallout_pct["percentage"] = (fallout_pct["count"] / total_fallout * 100).round(1)
        fallout_pct = fallout_pct.sort_values("percentage", ascending=False)
        fig_pct = px.bar(fallout_pct, x="fallout_category", y="percentage",
                         title="Fallout Category Distribution (%)",
                         labels={"fallout_category": "Kendala", "percentage": "Percentage (%)"},
                         text="percentage")
        fig_pct.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig_pct, use_container_width=True)
    else:
        st.info("No fallout data in selected period")

    # ----- Subchannel donut -----
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

    # ----- Additional metrics (totals) -----
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