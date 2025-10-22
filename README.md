# Business Case Studies Dashboard (Ola Ride Insights)

A Streamlit dashboard that connects to a MySQL database and explores ride‑sharing analytics using interactive tables and Plotly charts. The app implements ten business case studies such as successful bookings exploration, customer/driver cancellations, UPI payments, ratings analysis, and revenue summaries.

> Built with: **Streamlit, Pandas, Plotly, MySQL**

---

## ✨ Features (Mapped to the Sidebar Cases)

1. **Successful Bookings Explorer (DB)**  
   - Server‑side (SQL) date/time filtering using a robust `event_dt` expression that merges `date` and `time`.  
   - Auto‑granularity time‑series line chart or overall distribution by vehicle type.

2. **Average Ride Distance per Vehicle Type**  
   - Aggregates and visualizes mean distance (km) and count per vehicle type.

3. **Total Cancelled Rides by Customers**  
   - Lists all customer‑cancelled rides with a time‑series trend and breakdowns.

4. **Top 5 Customers by Number of Rides**  
   - Ranks customers by total rides with a simple bar chart.

5. **Driver Cancellations — Personal & Car related issue**  
   - Filters by a specific driver cancellation reason and aggregates by vehicle type.

6. **Driver Ratings (Prime Sedan)**  
   - Summary stats (min/max/avg) plus histogram/boxplot for driver ratings in *Prime Sedan* bookings.

7. **Rides Paid Using UPI**  
   - Filters UPI payments; shows total rides, revenue via UPI, and ride counts by vehicle type.

8. **Average Customer Rating per Vehicle Type**  
   - Mean ratings per vehicle type with optional color scales and y‑axis constrained to 0–5.

9. **Total Booking Value of Successfully Completed Rides**  
   - Sum of booking values grouped by vehicle type and overall KPI for completed rides.

10. **Incomplete Rides with Reason**  
    - Lists incomplete rides and aggregates counts by reason.

---

## 🧱 Data Model (Columns Used)

The app expects a `bookings` table with (at least) these columns referenced by the queries/visuals:

```
date, time, booking_id, booking_status, customer_id, vehicle_type,
pickup_location, drop_location, v_tat, c_tat,
canceled_rides_by_customer, canceled_rides_by_driver,
incomplete_rides, incomplete_rides_reason,
booking_value, payment_method, ride_distance,
driver_ratings, customer_rating, vehicle_images
```

### Example MySQL DDL (adjust types/lengths to your data)
```sql
CREATE DATABASE IF NOT EXISTS ola_insights;
USE ola_insights;

CREATE TABLE IF NOT EXISTS bookings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  date DATETIME NULL,
  time VARCHAR(20) NULL,                      -- kept as text in source; merged with date by the app
  booking_id VARCHAR(64) NULL,
  booking_status VARCHAR(32) NULL,
  customer_id VARCHAR(64) NULL,
  vehicle_type VARCHAR(64) NULL,
  pickup_location VARCHAR(255) NULL,
  drop_location VARCHAR(255) NULL,
  v_tat VARCHAR(32) NULL,
  c_tat VARCHAR(32) NULL,
  canceled_rides_by_customer VARCHAR(255) NULL,
  canceled_rides_by_driver VARCHAR(255) NULL,
  incomplete_rides VARCHAR(32) NULL,
  incomplete_rides_reason VARCHAR(255) NULL,
  booking_value DECIMAL(12,2) NULL,
  payment_method VARCHAR(64) NULL,
  ride_distance DECIMAL(10,2) NULL,
  driver_ratings DECIMAL(4,2) NULL,
  customer_rating DECIMAL(4,2) NULL,
  vehicle_images TEXT NULL,
  INDEX idx_status (booking_status),
  INDEX idx_payment (payment_method),
  INDEX idx_vehicle (vehicle_type),
  INDEX idx_customer (customer_id),
  INDEX idx_date (date)
);
```
> The app builds an `event_dt` expression by combining `date` and `time`. If you can, **store a single DATETIME** column in your source to simplify parsing and improve performance.

---

## ⚙️ Configuration

By default, the app connects with these hardcoded credentials (see `get_conn()` in `app.py`):
```python
host="localhost", user="root", password="password", database="ola_insights"
```
For production, switch to **environment variables**:
```bash
# .env (example)
DB_HOST=localhost
DB_USER=ola_user
DB_PASS=strong_password
DB_NAME=ola_insights
```
…and update `get_conn()` in your code to read from `os.environ` (or `python-dotenv`).

---

## 📦 Installation

> Requires **Python 3.8+** and **MySQL Server**.

```bash
# 1) Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt
```

---

## 🗃️ Database Setup

1. Start MySQL and create the DB/table using the DDL above.  
2. Load your CSVs into the `bookings` table (e.g., via MySQL Workbench, `LOAD DATA INFILE`, or a small Python loader).  
3. Verify there are rows:
```sql
SELECT COUNT(*) FROM bookings;
```

---

## ▶️ Run the App

```bash
streamlit run app.py
```
Open the URL that Streamlit prints (usually http://localhost:8501).  
Use the sidebar to navigate the ten business cases.

---

## 🧪 Notes & Best Practices

- **Server‑side filtering**: Case 1 pushes date/time filtering into SQL for performance.  
- **Time handling**: If `time` is messy, the app falls back to safe defaults and coercion. Prefer a single `DATETIME` in your DB.  
- **Indexes**: Adding indexes on `booking_status`, `payment_method`, `vehicle_type`, and `date` improves WHERE + ORDER BY performance.  
- **NULLs / blanks**: Queries use `COALESCE`/`TRIM` checks; clean data yields better UX.  
- **Plotly**: All charts are interactive; exportable via the toolbar.

---

## 🧰 Troubleshooting

- **Cannot connect to MySQL**: Check credentials, host, and ensure MySQL is running and accessible.  
- **Empty charts/tables**: Verify the table/columns exist and the dataset is loaded.  
- **Date parsing issues**: Ensure `date` is a valid DATETIME; if `time` is a string, keep `HH:MM:SS` format.  
- **Slow queries**: Add indexes; try limiting date ranges; consider a consolidated `event_dt` column.

---

## 📝 License

For educational and portfolio use. Attribution appreciated.
