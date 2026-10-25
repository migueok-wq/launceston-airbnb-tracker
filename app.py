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
st.caption(
    "Latest competitor availability and observed 2-night price quotes"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

today = date.today()
end_date = today + timedelta(days=30)

NAME_MAP = {
    "1611465816539756387": "Hideaway",
    "948350790129829517": "Inner City",
    "923522276768207018": "Central City",
    "965095191282208498": "Moonshine",
}

competitor_order = [
    "Hideaway",
    "Inner City",
    "Central City",
    "Moonshine",
]

# --------------------------------------------------
# LOAD AVAILABILITY
# --------------------------------------------------

calendar_params = {
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
    calendar_response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_calendar_history",
        headers=headers,
        params=calendar_params,
        timeout=30,
    )

    calendar_response.raise_for_status()
    calendar_data = calendar_response.json()

except Exception as error:
    st.error("Could not load availability data.")
    st.code(str(error))
    st.stop()

# --------------------------------------------------
# LOAD PRICE QUOTES
# --------------------------------------------------

price_params = {
    "select": (
        "listing_id,listing_name,checkin_date,"
        "checkout_date,nights,total_price_aud,"
        "average_price_per_night_aud,observed_at"
    ),
    "checkin_date": f"gte.{today.isoformat()}",
    "order": "observed_at.desc",
    "limit": "5000",
}

try:
    price_response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_price_quotes",
        headers=headers,
        params=price_params,
        timeout=30,
    )

    price_response.raise_for_status()
    price_data = price_response.json()

except Exception as error:
    st.error("Could not load price data.")
    st.code(str(error))
    st.stop()

# --------------------------------------------------
# PREPARE AVAILABILITY
# --------------------------------------------------

df = pd.DataFrame(calendar_data)

if df.empty:
    st.warning("No availability data found.")
    st.stop()

df["stay_date"] = pd.to_datetime(
    df["stay_date"]
).dt.date

df["observed_at"] = pd.to_datetime(
    df["observed_at"]
)

df = df[
    (df["stay_date"] >= today)
    & (df["stay_date"] <= end_date)
].copy()

# Latest observation for each competitor/date
df = (
    df.sort_values(
        "observed_at",
        ascending=False,
    )
    .drop_duplicates(
        subset=["listing_id", "stay_date"],
        keep="first",
    )
)

df["competitor"] = (
    df["listing_id"]
    .astype(str)
    .map(NAME_MAP)
    .fillna(df["listing_name"])
)

# --------------------------------------------------
# PREPARE PRICE QUOTES
# --------------------------------------------------

price_df = pd.DataFrame(price_data)

if not price_df.empty:

    price_df["checkin_date"] = pd.to_datetime(
        price_df["checkin_date"]
    ).dt.date

    price_df["checkout_date"] = pd.to_datetime(
        price_df["checkout_date"]
    ).dt.date

    price_df["observed_at"] = pd.to_datetime(
        price_df["observed_at"]
    )

    price_df = price_df[
        (price_df["checkin_date"] >= today)
        & (price_df["checkin_date"] <= end_date)
    ].copy()

    price_df["competitor"] = (
        price_df["listing_id"]
        .astype(str)
        .map(NAME_MAP)
        .fillna(price_df["listing_name"])
    )

    # Keep latest quote for each competitor/check-in/check-out
    price_df = (
        price_df.sort_values(
            "observed_at",
            ascending=False,
        )
        .drop_duplicates(
            subset=[
                "listing_id",
                "checkin_date",
                "checkout_date",
            ],
            keep="first",
        )
    )

# --------------------------------------------------
# BUILD PRICE LOOKUP
# --------------------------------------------------

price_lookup = {}

if not price_df.empty:

    for _, row in price_df.iterrows():

        key = (
            str(row["listing_id"]),
            row["checkin_date"],
        )

        price_lookup[key] = {
            "average": row[
                "average_price_per_night_aud"
            ],
            "total": row[
                "total_price_aud"
            ],
            "nights": row["nights"],
            "checkout": row["checkout_date"],
        }

# --------------------------------------------------
# CREATE DISPLAY STATUS
# --------------------------------------------------

def display_status(row):

    if row["available"] is True:

        min_nights = row["min_nights"]

        if pd.notna(min_nights):
            status = (
                f"🟢 Available "
                f"({int(min_nights)}n min)"
            )
        else:
            status = "🟢 Available"

    elif row["available"] is False:
        status = "🔴 Unavailable"

    else:
        status = "⚪ Unknown"

    # Add a price quote only when this exact
    # date was the check-in date of a quote.
    key = (
        str(row["listing_id"]),
        row["stay_date"],
    )

    quote = price_lookup.get(key)

    if quote:

        average = quote["average"]
        total = quote["total"]
        nights = int(quote["nights"])

        status += (
            f"\n💰 A${average:,.2f}/night avg"
            f"\nA${total:,.2f} / {nights} nights"
        )

    return status


df["status"] = df.apply(
    display_status,
    axis=1,
)

# --------------------------------------------------
# CREATE CALENDAR
# --------------------------------------------------

calendar = df.pivot(
    index="stay_date",
    columns="competitor",
    values="status",
)

for competitor in competitor_order:

    if competitor not in calendar.columns:
        calendar[competitor] = "⚪ No data"

calendar = calendar[
    competitor_order
]

calendar = calendar.reindex(
    pd.date_range(
        today,
        end_date,
        freq="D",
    ).date
)

calendar = calendar.fillna(
    "⚪ No data"
)

calendar.index = [
    day.strftime("%a %d %b")
    for day in calendar.index
]

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

latest_observation = df[
    "observed_at"
].max()

available_count = int(
    (df["available"] == True).sum()
)

unavailable_count = int(
    (df["available"] == False).sum()
)

quote_count = len(price_df)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Available",
    available_count,
)

col2.metric(
    "Unavailable",
    unavailable_count,
)

col3.metric(
    "Price quotes",
    quote_count,
)

col4.metric(
    "Latest update",
    latest_observation.strftime(
        "%d %b %Y"
    ),
)

st.divider()

# --------------------------------------------------
# CALENDAR
# --------------------------------------------------

st.subheader("📅 Competitor calendar — next 30 days")

st.dataframe(
    calendar,
    use_container_width=True,
    height=900,
)

st.caption(
    "🟢 Available = Airbnb currently allows the date. "
    "🔴 Unavailable does not necessarily mean booked; "
    "the date may be booked, blocked, or restricted. "
    "💰 Prices are observed stay quotes. The displayed "
    "per-night value is the average for the quoted stay, "
    "not the confirmed price of an individual night."
)

# --------------------------------------------------
# PRICE QUOTES
# --------------------------------------------------

st.divider()
st.subheader("💰 Latest observed price quotes")

if price_df.empty:

    st.info(
        "No price quotes are currently available "
        "for the next 30 days."
    )

else:

    price_table = price_df[
        [
            "competitor",
            "checkin_date",
            "checkout_date",
            "nights",
            "total_price_aud",
            "average_price_per_night_aud",
            "observed_at",
        ]
    ].copy()

    price_table = price_table.rename(
        columns={
            "competitor": "Competitor",
            "checkin_date": "Check-in",
            "checkout_date": "Check-out",
            "nights": "Nights",
            "total_price_aud": "Total A$",
            "average_price_per_night_aud":
                "Average A$/night",
            "observed_at": "Observed",
        }
    )

    price_table["Observed"] = (
        price_table["Observed"]
        .dt.strftime("%d %b %Y %H:%M")
    )

    price_table = price_table.sort_values(
        ["Check-in", "Competitor"]
    )

    st.dataframe(
        price_table,
        use_container_width=True,
        hide_index=True,
    )
