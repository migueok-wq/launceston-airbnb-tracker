import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta

st.set_page_config(
    page_title="Launceston Airbnb Tracker",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Launceston Airbnb Competitor Tracker")
st.caption("Competitor availability — latest observation for each stay date")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# --------------------------------------------------
# DATE RANGE
# --------------------------------------------------

today = date.today()
end_date = today + timedelta(days=30)

# --------------------------------------------------
# GET DATA FROM SUPABASE
# --------------------------------------------------

params = {
    "select": (
        "listing_id,listing_name,stay_date,"
        "available,available_for_checkin,"
        "available_for_checkout,min_nights,"
        "observed_at"
    ),
    "stay_date": f"gte.{today.isoformat()}",
    "order": "observed_at.desc",
    "limit": "5000",
}

try:
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_calendar_history",
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

except Exception as error:
    st.error("Could not load availability data from Supabase.")
    st.code(str(error))
    st.stop()

# --------------------------------------------------
# PREPARE DATA
# --------------------------------------------------

df = pd.DataFrame(data)

if df.empty:
    st.warning("No availability data found.")
    st.stop()

df["stay_date"] = pd.to_datetime(df["stay_date"]).dt.date
df["observed_at"] = pd.to_datetime(df["observed_at"])

# Only next 30 days
df = df[
    (df["stay_date"] >= today)
    & (df["stay_date"] <= end_date)
].copy()

# Keep only the newest observation
# for each listing + stay date
df = (
    df.sort_values("observed_at", ascending=False)
    .drop_duplicates(
        subset=["listing_id", "stay_date"],
        keep="first",
    )
)

# --------------------------------------------------
# SHORT COMPETITOR NAMES
# --------------------------------------------------

NAME_MAP = {
    "1611465816539756387": "Hideaway",
    "948350790129829517": "Inner City",
    "923522276768207018": "Central City",
    "965095191282208498": "Moonshine",
}

df["competitor"] = (
    df["listing_id"]
    .astype(str)
    .map(NAME_MAP)
    .fillna(df["listing_name"])
)

# --------------------------------------------------
# AVAILABILITY DISPLAY
# --------------------------------------------------

def availability_label(row):
    if row["available"] is True:
        min_nights = row["min_nights"]

        if pd.notna(min_nights):
            return f"🟢 Available ({int(min_nights)}n min)"

        return "🟢 Available"

    if row["available"] is False:
        return "🔴 Unavailable"

    return "⚪ Unknown"


df["status"] = df.apply(
    availability_label,
    axis=1,
)

# --------------------------------------------------
# CREATE CALENDAR TABLE
# --------------------------------------------------

calendar = df.pivot(
    index="stay_date",
    columns="competitor",
    values="status",
)

competitor_order = [
    "Hideaway",
    "Inner City",
    "Central City",
    "Moonshine",
]

for competitor in competitor_order:
    if competitor not in calendar.columns:
        calendar[competitor] = "⚪ No data"

calendar = calendar[competitor_order]

calendar = calendar.reindex(
    pd.date_range(
        today,
        end_date,
        freq="D",
    ).date
)

calendar = calendar.fillna("⚪ No data")

calendar.index = [
    day.strftime("%a %d %b")
    for day in calendar.index
]

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

latest_observation = df["observed_at"].max()

available_count = int(
    (df["available"] == True).sum()
)

unavailable_count = int(
    (df["available"] == False).sum()
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Available observations",
    available_count,
)

col2.metric(
    "Unavailable observations",
    unavailable_count,
)

col3.metric(
    "Latest update",
    latest_observation.strftime("%d %b %Y"),
)

st.divider()

# --------------------------------------------------
# CALENDAR
# --------------------------------------------------

st.subheader("📅 Next 30 days")

st.dataframe(
    calendar,
    use_container_width=True,
    height=900,
)

st.caption(
    "🟢 Available = Airbnb calendar currently allows the date. "
    "🔴 Unavailable does not necessarily mean booked; the date may "
    "also be blocked or restricted by the host."
)
