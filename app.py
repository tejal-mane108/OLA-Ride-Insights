import streamlit as st
import pandas as pd
import plotly.express as px
import mysql.connector
from datetime import datetime, time
from typing import Optional

st.set_page_config(page_title="Business Case Studies Dashboard", layout="wide")

# ---------------------------
# DB connection (edit creds)
# ---------------------------
def get_conn():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="ola_insights",
    )

# ---------------------------
# Common SQL fragments
# ---------------------------
# Build a consistent event_dt from (date + time)
EVENT_DT_EXPR = """
CAST(
  CASE
    WHEN COALESCE(TRIM(time),'') <> '' THEN CONCAT(DATE(date), ' ', TRIM(time))
    ELSE date
  END AS DATETIME
)
"""

# "Successful bookings" condition (booking_status says completed, or no cancels/incomplete)
SUCCESS_WHERE = """
(
  LOWER(COALESCE(booking_status,'')) = 'success'
#   OR (
#     CAST(COALESCE(canceled_rides_by_customer,'0') AS UNSIGNED) = 0
#     AND CAST(COALESCE(canceled_rides_by_driver,'0') AS UNSIGNED) = 0
#     AND CAST(COALESCE(incomplete_rides,'0') AS UNSIGNED) = 0
#   )
)
"""

def fetch_minmax(successful_only: bool) -> pd.DataFrame:
    where_clause = f"WHERE {SUCCESS_WHERE}" if successful_only else ""
    sql = f"""
        SELECT MIN(event_dt) AS min_dt, MAX(event_dt) AS max_dt
        FROM (
            SELECT {EVENT_DT_EXPR} AS event_dt
            FROM bookings
            {where_clause}
        ) t
    """
    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def fetch_rows(successful_only: bool,
               start_dt: Optional[datetime],
               end_dt: Optional[datetime],
               apply_filter: bool) -> pd.DataFrame:
    where_parts = []
    if successful_only:
        where_parts.append(SUCCESS_WHERE)

    # Build event_dt BETWEEN condition only when filter is applied
    if apply_filter and start_dt and end_dt:
        where_parts.append(f"{EVENT_DT_EXPR} BETWEEN %s AND %s")

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT
          {EVENT_DT_EXPR} AS event_dt,
          date, time, booking_id, booking_status, customer_id, vehicle_type, pickup_location,
          drop_location, v_tat, c_tat, canceled_rides_by_customer, canceled_rides_by_driver,
          incomplete_rides, incomplete_rides_reason, booking_value, payment_method,
          ride_distance, driver_ratings, customer_rating, vehicle_images
        FROM bookings
        {where_sql}
        ORDER BY event_dt
    """
    params = [start_dt, end_dt] if (apply_filter and start_dt and end_dt) else None
    conn = get_conn()
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df

# ---------------------------
# Sidebar: pick a case
# ---------------------------
st.sidebar.title("📚 Business Case Studies")
cases = [
    "Case 1 — Successful Bookings Explorer (DB)",
    "Case 2 — Average Ride Distance per Vehicle Type",
    "Case 3 — Total Cancelled Rides by Customers",
    "Case 4 — Top 5 Customers by Number of Rides",
    "Case 5 — Driver Cancellations: Personal & Car related issue",
    "Case 6 — Driver Ratings (Prime Sedan)",
    "Case 7 — Rides Paid Using UPI",
    "Case 8 — Average Customer Rating per Vehicle Type",
    "Case 9 — Total Booking Value of Successfully Completed Rides",
    "Case 10 — Incomplete Rides with Reason",
]
selected_case = st.sidebar.selectbox("Choose a case", cases, index=0)

# =========================================================
# CASE 1 IMPLEMENTATION (uses your exact table schema)
# =========================================================
if selected_case == "Case 1 — Successful Bookings Explorer (DB)":
    st.title("✅ Case 1 — Successful Bookings Explorer (Database)")

    # Controls
    colc1, colc2, colc3 = st.columns(3)
    with colc1:
        successful_only = st.checkbox("Successful bookings only", value=True)
    with colc2:
        apply_filter = st.checkbox("Apply date & time filter", value=False)

    # Get min/max event_dt to seed controls
    mm = fetch_minmax(successful_only)
    if mm.empty or pd.isna(mm.loc[0, "min_dt"]) or pd.isna(mm.loc[0, "max_dt"]):
        st.warning("No data found (check table contents or success filter).")
        st.stop()

    min_dt = pd.to_datetime(mm.loc[0, "min_dt"])
    max_dt = pd.to_datetime(mm.loc[0, "max_dt"])

    colA, colB = st.columns(2)
    with colA:
        date_range = st.date_input(
            "Date range",
            value=(min_dt.date(), max_dt.date()),
            min_value=min_dt.date(),
            max_value=max_dt.date(),
            disabled=not apply_filter
        )
    with colB:
        t1 = st.time_input("Start time", value=time(0, 0), disabled=not apply_filter)
        t2 = st.time_input("End time",   value=time(23, 59), disabled=not apply_filter)

    start_dt = end_dt = None
    if apply_filter and isinstance(date_range, tuple) and len(date_range) == 2:
        start_dt = datetime.combine(date_range[0], t1)
        end_dt   = datetime.combine(date_range[1], t2)

    # Query data (filter pushed to SQL)
    df = fetch_rows(successful_only, start_dt, end_dt, apply_filter)

    if df.empty:
        st.warning("No rows match the current settings.")
        st.stop()

    # Show table
    st.subheader("Bookings (Result Table)")
    st.dataframe(df, use_container_width=True)

    # Charts
    if apply_filter and start_dt and end_dt:
        # LINE chart — bookings over time (auto granularity)
        st.subheader("Line Chart — Bookings Over Time")
        granularity = "H" if (end_dt - start_dt).days <= 3 else "D"
        tdf = df.copy()
        tdf["event_dt"] = pd.to_datetime(tdf["event_dt"], errors="coerce")
        tdf = tdf.dropna(subset=["event_dt"])
        # Count bookings (use booking_id if present)
        count_col = "booking_id" if "booking_id" in tdf.columns else tdf.columns[0]
        ts = (
            tdf.set_index("event_dt")
               .resample(granularity)[count_col]
               .count()
               .reset_index()
               .rename(columns={count_col: "bookings_count"})
        )
        fig = px.line(
            ts, x="event_dt", y="bookings_count",
            markers=True,
            labels={"event_dt": "Time", "bookings_count": "Bookings"},
            title=f"Bookings Over Time ({granularity}-level)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        # BAR chart — overall distribution by vehicle_type
        st.subheader("Bar Chart — Total Bookings by Vehicle Type (All Data)")
        if "vehicle_type" in df.columns:
            by_vt = (
                df.groupby("vehicle_type", dropna=False)
                  .size()
                  .reset_index(name="total_bookings")
                  .sort_values("total_bookings", ascending=False)
                  .head(20)
            )
            fig = px.bar(
                by_vt,
                x="vehicle_type",
                y="total_bookings",
                text="total_bookings",
                labels={"vehicle_type": "Vehicle Type", "total_bookings": "Bookings"},
                title="Top Vehicle Types by Total Bookings"
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Column 'vehicle_type' not found — showing bookings over time instead.")
            tdf = df.copy()
            tdf["event_dt"] = pd.to_datetime(tdf["event_dt"], errors="coerce")
            tdf = tdf.dropna(subset=["event_dt"])
            count_col = "booking_id" if "booking_id" in tdf.columns else tdf.columns[0]
            ts = (
                tdf.set_index("event_dt")
                   .resample("D")[count_col]
                   .count()
                   .reset_index()
                   .rename(columns={count_col: "bookings_count"})
            )
            st.plotly_chart(
                px.line(ts, x="event_dt", y="bookings_count", markers=True,
                        title="Bookings Over Time (Daily)"),
                use_container_width=True
            )

# =========================================================
# PLACEHOLDERS for other cases
# =========================================================
elif selected_case == "Case 2 — Average Ride Distance per Vehicle Type":
    st.title("🚗 Case 2 — Average Ride Distance per Vehicle Type")

    # SQL query to compute averages
    sql = """
        SELECT
            vehicle_type,
            ROUND(AVG(CAST(ride_distance AS DECIMAL(10,2))),2) AS avg_distance_km,
            COUNT(*) AS total_rides
        FROM bookings
        WHERE ride_distance IS NOT NULL AND TRIM(ride_distance) <> ''
        GROUP BY vehicle_type
        ORDER BY avg_distance_km DESC;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No ride distance data found.")
        st.stop()

    # Show the data table
    st.subheader("Average Ride Distance per Vehicle Type (km)")
    st.dataframe(df, use_container_width=True)

    # Visualize as bar chart
    st.subheader("Visualization — Average Ride Distance by Vehicle Type")
    fig = px.bar(
        df,
        x="vehicle_type",
        y="avg_distance_km",
        text="avg_distance_km",
        labels={"vehicle_type": "Vehicle Type", "avg_distance_km": "Average Distance (km)"},
        title="Average Ride Distance per Vehicle Type",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Optional: Add pie or comparison chart
    st.subheader("Ride Share by Vehicle Type")
    pie = px.pie(
        df,
        names="vehicle_type",
        values="total_rides",
        title="Proportion of Rides per Vehicle Type",
        hole=0.4
    )
    st.plotly_chart(pie, use_container_width=True)

# =========================================================
# CASE 3 — All Cancelled Rides by Customers (with Time Trend)
# =========================================================
elif selected_case == "Case 3 — Total Cancelled Rides by Customers":
    st.title("🚫 Case 3 — All Cancelled Rides by Customers")

    # SQL query: fetch all cancelled rides by customers
    sql = """
        SELECT
            date,
            time,
            booking_id,
            customer_id,
            vehicle_type,
            pickup_location,
            drop_location,
            booking_value,
            ride_distance,
            driver_ratings,
            customer_rating
        FROM bookings
        WHERE canceled_rides_by_customer IS NOT NULL
          AND TRIM(canceled_rides_by_customer) <> ''
        ORDER BY date, time;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No customer-cancelled rides found.")
        st.stop()

    # --- Safely combine date and time ---
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    else:
        df["date_str"] = df["date"].astype(str)

    df["time_str"] = df["time"].fillna("00:00:00").astype(str)
    df["event_dt"] = pd.to_datetime(df["date_str"] + " " + df["time_str"], errors="coerce")
    # --- Compute total ---
    total_cancelled = len(df)
    st.metric(label="Total Cancelled Rides by Customers", value=f"{total_cancelled:,}")

    # --- Show detailed data table ---
    st.subheader("Cancelled Rides — Detailed Records")
    st.dataframe(df, use_container_width=True)

    # --- Bar Chart: Cancelled Rides by Vehicle Type ---
    st.subheader("Bar Chart — Cancelled Rides by Vehicle Type")
    cancel_counts = (
        df.groupby("vehicle_type", dropna=False)
          .size()
          .reset_index(name="cancelled_rides")
          .sort_values("cancelled_rides", ascending=False)
    )

    fig1 = px.bar(
        cancel_counts,
        x="vehicle_type",
        y="cancelled_rides",
        text="cancelled_rides",
        title="Customer-Cancelled Rides by Vehicle Type",
        labels={"vehicle_type": "Vehicle Type", "cancelled_rides": "Cancelled Rides"},
    )
    fig1.update_traces(textposition="outside")
    st.plotly_chart(fig1, use_container_width=True)

    # --- Line Chart: Cancelled Rides over Time ---
    # st.subheader("Line Chart — Cancelled Rides Over Time")
    # timeline = (
    #     df.set_index("event_dt")
    #       .resample("D")  # daily resolution; can change to "H" for hourly
    #       .size()
    #       .reset_index(name="cancelled_rides")
    # )

    # fig2 = px.line(
    #     timeline,
    #     x="event_dt",
    #     y="cancelled_rides",
    #     markers=True,
    #     labels={"event_dt": "Date", "cancelled_rides": "Cancelled Rides"},
    #     title="Customer-Cancelled Rides Over Time (Daily Trend)",
    # )
    # st.plotly_chart(fig2, use_container_width=True)
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["event_dt"] = df["date"].copy()
    else:
        # Otherwise combine string date + time safely
        df["date_str"] = df["date"].astype(str).str.strip()
        df["time_str"] = df["time"].replace([None, np.nan, ""], "00:00:00").astype(str)
        df["event_dt"] = pd.to_datetime(df["date_str"] + " " + df["time_str"],
                                        errors="coerce", utc=False)

    # Drop rows where event_dt could not be parsed
    df = df.dropna(subset=["event_dt"]).copy()
    df["event_dt"] = pd.to_datetime(df["event_dt"])   # ensure dtype
    df = df.sort_values("event_dt")

    if df.empty:
        st.warning("No valid timestamps found after cleaning — check that your 'date' "
                "column contains proper datetimes or that 'time' values are valid.")
    else:
        # Choose granularity interactively
        granularity = st.radio("Time Interval", ["Daily", "Hourly"], horizontal=True)
        freq = "H" if granularity == "Hourly" else "D"

        # Count by time group
        count_col = "booking_id" if "booking_id" in df.columns else df.columns[0]
        timeline = (
            df.groupby(pd.Grouper(key="event_dt", freq=freq))[count_col]
            .size()
            .reset_index(name="cancelled_rides")
        )

        fig = px.line(
            timeline,
            x="event_dt",
            y="cancelled_rides",
            markers=True,
            labels={"event_dt": "Time", "cancelled_rides": "Cancelled Rides"},
            title=f"Customer-Cancelled Rides Over Time ({granularity})",
        )
        st.plotly_chart(fig, use_container_width=True)
# elif selected_case.startswith("Case 3"):
#     st.title("Case 3 — Placeholder"); st.info("Implement Case 3 here.")
# =========================================================
# CASE 4 — Top 5 Customers by Number of Rides
# =========================================================
elif selected_case == "Case 4 — Top 5 Customers by Number of Rides":
    st.title("👑 Case 4 — Top 5 Customers by Number of Rides")

    # SQL: group by customer_id, count rides
    sql = """
        SELECT
            customer_id,
            COUNT(booking_id) AS total_rides
        FROM bookings
        WHERE customer_id IS NOT NULL AND TRIM(customer_id) <> ''
        GROUP BY customer_id
        ORDER BY total_rides DESC
        LIMIT 5;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()
    # Show the data table
    st.subheader("Top 5 Customers by Number of Rides")
    st.dataframe(df, use_container_width=True)

    if df.empty:
        st.warning("No customer data found.")
        st.stop()

    # --- Bar chart of Top 5 Customers ---
    fig = px.bar(
        df,
        x="customer_id",
        y="total_rides",
        text="total_rides",
        title="Top 5 Customers by Total Number of Rides",
        labels={"customer_id": "Customer ID", "total_rides": "Number of Rides"},
        color="total_rides",
        color_continuous_scale="blues"
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False)

    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# CASE 5 — Driver Cancellations: "Personal & Car related issue"
# =========================================================
elif selected_case == "Case 5 — Driver Cancellations: Personal & Car related issue":
    st.title("🛑 Case 5 — Driver Cancellations: Personal & Car related issue")

    # Pull all bookings where driver cancelled due to the specified reason
    sql = """
        SELECT
            date,
            time,
            booking_id,
            customer_id,
            vehicle_type,
            pickup_location,
            drop_location,
            booking_value,
            ride_distance,
            driver_ratings,
            customer_rating,
            canceled_rides_by_driver
        FROM bookings
        WHERE LOWER(TRIM(canceled_rides_by_driver)) = 'personal & car related issue'
        ORDER BY date, time
    """
    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No driver-cancelled rides found for reason: Personal & Car related issue.")
        st.stop()

    # Show the raw rows
    st.subheader("Filtered Records — Driver Cancellations: Personal & Car related issue")
    st.dataframe(df, use_container_width=True)

    # One graph only: count by vehicle type (top categories first)
    st.subheader("Bar Chart — Cancellations by Vehicle Type")
    by_vt = (
        df.groupby("vehicle_type", dropna=False)
          .size()
          .reset_index(name="cancelled_rides")
          .sort_values("cancelled_rides", ascending=False)
    )

    fig = px.bar(
        by_vt,
        x="vehicle_type",
        y="cancelled_rides",
        text="cancelled_rides",
        labels={"vehicle_type": "Vehicle Type", "cancelled_rides": "Cancelled Rides"},
        title="Driver Cancellations (Personal & Car related issue) by Vehicle Type"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# CASE 6 — Driver Ratings Analysis for Prime Sedan
# =========================================================
elif selected_case == "Case 6 — Driver Ratings (Prime Sedan)":
    st.title("⭐ Case 6 — Driver Ratings Analysis for Prime Sedan Bookings")

    # SQL: fetch driver ratings for Prime Sedan
    sql = """
        SELECT
            date,
            time,
            booking_id,
            customer_id,
            vehicle_type,
            driver_ratings,
            customer_rating
        FROM bookings
        WHERE LOWER(TRIM(vehicle_type)) = 'prime sedan'
          AND driver_ratings IS NOT NULL
        ORDER BY date, time;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No Prime Sedan bookings with driver ratings found.")
        st.stop()

    # --- Compute statistics ---
    max_rating = df["driver_ratings"].max()
    min_rating = df["driver_ratings"].min()
    avg_rating = df["driver_ratings"].mean()

    # --- Show summary metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Maximum Rating", f"{max_rating:.2f}")
    c2.metric("Minimum Rating", f"{min_rating:.2f}")
    c3.metric("Average Rating", f"{avg_rating:.2f}")

    # --- Show dataframe ---
    st.subheader("Prime Sedan Bookings — Driver Ratings Data")
    st.dataframe(df, use_container_width=True)

    # --- Visualization choice ---
    st.subheader("Driver Ratings Distribution")
    chart_type = st.radio("Choose visualization type:",
                          ["Histogram", "Box Plot"], horizontal=True)

    # --- Histogram ---
    if chart_type == "Histogram":
        fig = px.histogram(
            df,
            x="driver_ratings",
            nbins=10,
            title="Distribution of Driver Ratings for Prime Sedan",
            labels={"driver_ratings": "Driver Rating"},
            color_discrete_sequence=["#1f77b4"]
        )
        fig.update_traces(opacity=0.75)
        st.plotly_chart(fig, use_container_width=True)

    # --- Box Plot ---
    else:
        fig = px.box(
            df,
            y="driver_ratings",
            points="all",
            title="Box Plot — Driver Ratings for Prime Sedan Bookings",
            labels={"driver_ratings": "Driver Rating"},
            color_discrete_sequence=["#2ca02c"]
        )
        st.plotly_chart(fig, use_container_width=True)
# elif selected_case.startswith("Case 4"):
#     st.title("Case 4 — Placeholder"); st.info("Implement Case 4 here.")
# elif selected_case.startswith("Case 5"):
#     st.title("Case 5 — Placeholder"); st.info("Implement Case 5 here.")
# elif selected_case.startswith("Case 6"):
#     st.title("Case 6 — Placeholder"); st.info("Implement Case 6 here.")

# =========================================================
# CASE 7 — Rides Paid Using UPI
# =========================================================
elif selected_case == "Case 7 — Rides Paid Using UPI":
    st.title("💸 Case 7 — Rides Paid Using UPI")

    # SQL query to retrieve all rides where payment was made using UPI
    sql = """
        SELECT
            date,
            time,
            booking_id,
            customer_id,
            vehicle_type,
            pickup_location,
            drop_location,
            booking_value,
            ride_distance,
            driver_ratings,
            customer_rating,
            payment_method
        FROM bookings
        WHERE LOWER(TRIM(payment_method)) = 'upi'
        ORDER BY date, time;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No rides found where payment was made using UPI.")
        st.stop()

    # --- Display summary metrics ---
    total_upi_rides = len(df)
    total_revenue_upi = df["booking_value"].sum() if "booking_value" in df.columns else None

    c1, c2 = st.columns(2)
    c1.metric("Total UPI Rides", f"{total_upi_rides:,}")
    if total_revenue_upi:
        c2.metric("Total Revenue via UPI", f"₹{total_revenue_upi:,.0f}")

    # --- Show data table ---
    st.subheader("UPI Payment Rides — Detailed Data")
    st.dataframe(df, use_container_width=True)

    # --- Visualization: Total UPI Rides by Vehicle Type ---
    st.subheader("Bar Chart — UPI Rides by Vehicle Type")
    rides_by_vehicle = (
        df.groupby("vehicle_type", dropna=False)
          .size()
          .reset_index(name="total_upi_rides")
          .sort_values("total_upi_rides", ascending=False)
    )

    fig = px.bar(
        rides_by_vehicle,
        x="vehicle_type",
        y="total_upi_rides",
        text="total_upi_rides",
        title="Total Number of UPI Payment Rides by Vehicle Type",
        labels={"vehicle_type": "Vehicle Type", "total_upi_rides": "Number of UPI Rides"},
        color="total_upi_rides",
        color_continuous_scale="teal"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# CASE 8 — Average Customer Rating per Vehicle Type
# =========================================================
elif selected_case == "Case 8 — Average Customer Rating per Vehicle Type":
    st.title("🌟 Case 8 — Average Customer Rating per Vehicle Type")

    # SQL query to compute average ratings grouped by vehicle type
    sql = """
        SELECT
            vehicle_type,
            ROUND(AVG(customer_rating), 2) AS avg_customer_rating,
            COUNT(customer_rating) AS total_rated_rides
        FROM bookings
        WHERE customer_rating IS NOT NULL
        GROUP BY vehicle_type
        ORDER BY avg_customer_rating DESC;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No customer rating data found in the bookings table.")
        st.stop()

    # --- Summary metrics ---
    overall_avg = df["avg_customer_rating"].mean()
    st.metric("Overall Average Customer Rating Across All Vehicle Types", f"{overall_avg:.2f}")

    # --- Show DataFrame ---
    st.subheader("Average Customer Rating by Vehicle Type")
    st.dataframe(df, use_container_width=True)

    # --- Visualization: Bar chart ---
    st.subheader("Bar Chart — Average Customer Rating per Vehicle Type")
    fig = px.bar(
        df,
        x="vehicle_type",
        y="avg_customer_rating",
        text="avg_customer_rating",
        title="Average Customer Rating by Vehicle Type",
        labels={
            "vehicle_type": "Vehicle Type",
            "avg_customer_rating": "Average Rating (1–5)"
        },
        color="avg_customer_rating",
        color_continuous_scale="viridis"
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis=dict(range=[0, 5]))  # Ratings are between 1 and 5
    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# CASE 9 — Total Booking Value of Successfully Completed Rides
# =========================================================
elif selected_case == "Case 9 — Total Booking Value of Successfully Completed Rides":
    st.title("💰 Case 9 — Total Booking Value of Successfully Completed Rides")

    # SQL: sum of booking_value where booking_status is completed
    sql = """
        SELECT
            vehicle_type,
            SUM(booking_value) AS total_booking_value,
            COUNT(*) AS total_completed_rides
        FROM bookings
        WHERE LOWER(TRIM(booking_status)) = 'success'
          AND booking_value IS NOT NULL
        GROUP BY vehicle_type
        ORDER BY total_booking_value DESC;
    """

    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No completed rides or booking value data found.")
        st.stop()

    # --- Calculate grand total ---
    grand_total = df["total_booking_value"].sum()

    # --- Summary metric ---
    st.metric(label="Grand Total Booking Value (All Completed Rides)",
              value=f"₹{grand_total:,.0f}")

    # --- Show data table ---
    st.subheader("Total Booking Value by Vehicle Type")
    st.dataframe(df, use_container_width=True)

    # --- Visualization: Bar chart of total booking value by vehicle type ---
    st.subheader("Bar Chart — Total Booking Value of Completed Rides by Vehicle Type")
    fig = px.bar(
        df,
        x="vehicle_type",
        y="total_booking_value",
        text="total_booking_value",
        title="Total Booking Value (₹) — Completed Rides by Vehicle Type",
        labels={
            "vehicle_type": "Vehicle Type",
            "total_booking_value": "Total Booking Value (₹)"
        },
        color="total_booking_value",
        color_continuous_scale="cividis"
    )
    fig.update_traces(texttemplate="₹%{text:.2s}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
# =========================================================
# CASE 10 — List All Incomplete Rides with Reason
# =========================================================
elif selected_case == "Case 10 — Incomplete Rides with Reason":
    st.title("🧩 Case 10 — Incomplete Rides with Reason")

    # Fetch all incomplete rides with their reasons
    sql = """
        SELECT
            date,
            time,
            booking_id,
            customer_id,
            vehicle_type,
            pickup_location,
            drop_location,
            booking_status,
            booking_value,
            ride_distance,
            driver_ratings,
            customer_rating,
            incomplete_rides,
            incomplete_rides_reason
        FROM bookings
        WHERE incomplete_rides != "No"
          AND TRIM(incomplete_rides) <> ''
        ORDER BY date, time;
    """
    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()

    if df.empty:
        st.warning("No incomplete rides found.")
        st.stop()

    # Show the detailed table
    st.subheader("Incomplete Rides — Detailed List with Reasons")
    st.dataframe(df, use_container_width=True)

    # One graph: count of incomplete rides by reason
    st.subheader("Bar Chart — Incomplete Rides by Reason")
    by_reason = (
        df.assign(reason=df["incomplete_rides_reason"].fillna("Unknown / Not Provided").str.strip())
          .groupby("reason", dropna=False)
          .size()
          .reset_index(name="incomplete_count")
          .sort_values("incomplete_count", ascending=False)
    )

    fig = px.bar(
        by_reason,
        x="reason",
        y="incomplete_count",
        text="incomplete_count",
        title="Incomplete Rides by Reason",
        labels={"reason": "Reason", "incomplete_count": "Number of Incomplete Rides"},
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)