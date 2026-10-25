import streamlit as st
import requests

st.set_page_config(
    page_title="Launceston Airbnb Tracker",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Launceston Airbnb Competitor Tracker")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

st.subheader("📊 Database status")

try:
    calendar_response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_calendar_history",
        headers={
            **headers,
            "Prefer": "count=exact",
            "Range": "0-0",
        },
        timeout=20,
    )

    price_response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_price_quotes",
        headers={
            **headers,
            "Prefer": "count=exact",
            "Range": "0-0",
        },
        timeout=20,
    )

    calendar_response.raise_for_status()
    price_response.raise_for_status()

    calendar_range = calendar_response.headers.get(
        "Content-Range", "*/0"
    )
    price_range = price_response.headers.get(
        "Content-Range", "*/0"
    )

    calendar_count = int(calendar_range.split("/")[-1])
    price_count = int(price_range.split("/")[-1])

    st.success("✅ Connected to Supabase successfully")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Availability observations",
            calendar_count,
        )

    with col2:
        st.metric(
            "Price observations",
            price_count,
        )

except Exception as error:
    st.error("❌ Could not connect to Supabase")
    st.code(str(error))
