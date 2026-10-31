import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Launceston Airbnb Tracker",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Launceston Airbnb Competitor Tracker")

st.caption(
    "Competitor availability, recent changes, market signals "
    "and observed price quotes"
)


# ==================================================
# SUPABASE
# ==================================================

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}


# ==================================================
# SETTINGS
# ==================================================

today = date.today()
max_end_date = today + timedelta(days=90)

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


# ==================================================
# DASHBOARD RANGE
# ==================================================

range_option = st.segmented_control(
    "Dashboard horizon",
    options=[30, 60, 90],
    default=90,
    format_func=lambda x: f"Next {x} days",
)

if range_option is None:
    range_option = 90

end_date = today + timedelta(days=range_option)


# ==================================================
# LOAD AVAILABILITY HISTORY
# ==================================================

calendar_params = {
    "select": (
        "listing_id,listing_name,stay_date,"
        "available,available_for_checkin,"
        "available_for_checkout,min_nights,"
        "observed_at,apify_run_id"
    ),
    "stay_date": f"gte.{today.isoformat()}",
    "order": "observed_at.desc",
    "limit": "10000",
}

try:

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_calendar_history",
        headers=headers,
        params=calendar_params,
        timeout=30,
    )

    response.raise_for_status()

    calendar_data = response.json()

except Exception as error:

    st.error(
        "Could not load availability data."
    )

    st.code(str(error))

    st.stop()


history_df = pd.DataFrame(
    calendar_data
)

if history_df.empty:

    st.warning(
        "No availability data found."
    )

    st.stop()


history_df["stay_date"] = pd.to_datetime(
    history_df["stay_date"]
).dt.date

history_df["observed_at"] = pd.to_datetime(
    history_df["observed_at"],
    utc=True,
)

history_df = history_df[
    (history_df["stay_date"] >= today)
    & (history_df["stay_date"] <= max_end_date)
].copy()

history_df["competitor"] = (
    history_df["listing_id"]
    .astype(str)
    .map(NAME_MAP)
    .fillna(history_df["listing_name"])
)


# ==================================================
# FILTER SELECTED RANGE
# ==================================================

range_history_df = history_df[
    history_df["stay_date"] <= end_date
].copy()


# ==================================================
# LATEST AVAILABILITY SNAPSHOT
# ==================================================

df = (
    range_history_df
    .sort_values(
        "observed_at",
        ascending=False,
    )
    .drop_duplicates(
        subset=[
            "listing_id",
            "stay_date",
        ],
        keep="first",
    )
    .copy()
)


# ==================================================
# CHANGE DETECTION
# ==================================================

change_rows = []

for (
    listing_id,
    stay_date,
), group in range_history_df.groupby(
    [
        "listing_id",
        "stay_date",
    ]
):

    group = (
        group
        .sort_values(
            "observed_at",
            ascending=False,
        )
        .drop_duplicates(
            subset=["apify_run_id"],
            keep="first",
        )
    )

    if len(group) < 2:
        continue

    latest = group.iloc[0]
    previous = group.iloc[1]

    latest_available = (
        latest["available"]
    )

    previous_available = (
        previous["available"]
    )

    if (
        pd.isna(latest_available)
        or pd.isna(previous_available)
    ):
        continue

    # Available -> unavailable
    if (
        bool(previous_available) is True
        and bool(latest_available) is False
    ):

        change_rows.append(
            {
                "listing_id": str(
                    listing_id
                ),
                "competitor":
                    latest["competitor"],
                "stay_date":
                    stay_date,
                "change":
                    "📉 Availability lost",
                "previous":
                    "Available",
                "current":
                    "Unavailable",
                "observed_at":
                    latest["observed_at"],
            }
        )

    # Unavailable -> available
    elif (
        bool(previous_available) is False
        and bool(latest_available) is True
    ):

        change_rows.append(
            {
                "listing_id": str(
                    listing_id
                ),
                "competitor":
                    latest["competitor"],
                "stay_date":
                    stay_date,
                "change":
                    "📈 Availability opened",
                "previous":
                    "Unavailable",
                "current":
                    "Available",
                "observed_at":
                    latest["observed_at"],
            }
        )


changes_df = pd.DataFrame(
    change_rows
)


# ==================================================
# LOAD PRICE QUOTES
# ==================================================

price_params = {
    "select": (
        "listing_id,listing_name,checkin_date,"
        "checkout_date,nights,total_price_aud,"
        "average_price_per_night_aud,observed_at"
    ),
    "checkin_date": f"gte.{today.isoformat()}",
    "order": "observed_at.desc",
    "limit": "10000",
}

try:

    price_response = requests.get(
        f"{SUPABASE_URL}/rest/v1/airbnb_price_quotes",
        headers=headers,
        params=price_params,
        timeout=30,
    )

    price_response.raise_for_status()

    price_data = (
        price_response.json()
    )

except Exception as error:

    st.error(
        "Could not load price data."
    )

    st.code(str(error))

    st.stop()


price_df = pd.DataFrame(
    price_data
)


if not price_df.empty:

    price_df["checkin_date"] = (
        pd.to_datetime(
            price_df["checkin_date"]
        ).dt.date
    )

    price_df["checkout_date"] = (
        pd.to_datetime(
            price_df["checkout_date"]
        ).dt.date
    )

    price_df["observed_at"] = (
        pd.to_datetime(
            price_df["observed_at"],
            utc=True,
        )
    )

    price_df[
        "average_price_per_night_aud"
    ] = pd.to_numeric(
        price_df[
            "average_price_per_night_aud"
        ],
        errors="coerce",
    )

    price_df[
        "total_price_aud"
    ] = pd.to_numeric(
        price_df[
            "total_price_aud"
        ],
        errors="coerce",
    )

    price_df = price_df[
        (
            price_df["checkin_date"]
            >= today
        )
        & (
            price_df["checkin_date"]
            <= end_date
        )
    ].copy()

    price_df["competitor"] = (
        price_df["listing_id"]
        .astype(str)
        .map(NAME_MAP)
        .fillna(
            price_df["listing_name"]
        )
    )

    # Keep latest quote for each
    # competitor/check-in/check-out
    price_df = (
        price_df
        .sort_values(
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


# ==================================================
# PRICE LOOKUP
# ==================================================

price_lookup = {}

if not price_df.empty:

    for _, row in price_df.iterrows():

        key = (
            str(row["listing_id"]),
            row["checkin_date"],
        )

        price_lookup[key] = {
            "average":
                row[
                    "average_price_per_night_aud"
                ],
            "total":
                row["total_price_aud"],
            "nights":
                row["nights"],
        }


# ==================================================
# DISPLAY STATUS
# ==================================================

def display_status(row):

    if row["available"] is True:

        if pd.notna(
            row["min_nights"]
        ):

            status = (
                f"🟢 Available "
                f"({int(row['min_nights'])}n min)"
            )

        else:

            status = (
                "🟢 Available"
            )

    elif row["available"] is False:

        status = (
            "🔴 Unavailable"
        )

    else:

        status = (
            "⚪ Unknown"
        )

    key = (
        str(row["listing_id"]),
        row["stay_date"],
    )

    quote = price_lookup.get(
        key
    )

    if quote:

        average = quote[
            "average"
        ]

        total = quote[
            "total"
        ]

        nights = quote[
            "nights"
        ]

        if (
            pd.notna(average)
            and pd.notna(total)
            and pd.notna(nights)
        ):

            status += (
                f"\n💰 A${average:,.2f}/night avg"
                f"\nA${total:,.2f} / "
                f"{int(nights)} nights"
            )

    return status


df["status"] = df.apply(
    display_status,
    axis=1,
)


# ==================================================
# DATE RANGE
# ==================================================

all_dates = pd.date_range(
    today,
    end_date,
    freq="D",
).date


# ==================================================
# MARKET AVAILABILITY
# ==================================================

market_rows = []

for stay_date in all_dates:

    day_data = df[
        df["stay_date"]
        == stay_date
    ]

    available = int(
        (
            day_data["available"]
            == True
        ).sum()
    )

    unavailable = int(
        (
            day_data["available"]
            == False
        ).sum()
    )

    observed = (
        available
        + unavailable
    )

    if observed == 0:

        availability_pct = None

        signal = (
            "⚪ No data"
        )

    else:

        availability_pct = (
            available
            / observed
        ) * 100

        if available == 0:

            signal = (
                "🔥 Very tight"
            )

        elif availability_pct <= 25:

            signal = (
                "🟠 Tight"
            )

        elif availability_pct <= 50:

            signal = (
                "🟡 Moderate"
            )

        elif availability_pct <= 75:

            signal = (
                "🔵 Available"
            )

        else:

            signal = (
                "🟢 High availability"
            )

    if changes_df.empty:

        losses = 0
        openings = 0

    else:

        day_changes = changes_df[
            changes_df["stay_date"]
            == stay_date
        ]

        losses = int(
            (
                day_changes["change"]
                == "📉 Availability lost"
            ).sum()
        )

        openings = int(
            (
                day_changes["change"]
                == "📈 Availability opened"
            ).sum()
        )

    market_rows.append(
        {
            "Date":
                stay_date,
            "Available":
                available,
            "Observed":
                observed,
            "Market availability":
                availability_pct,
            "Recent losses":
                losses,
            "Recent openings":
                openings,
            "Signal":
                signal,
        }
    )


market_df = pd.DataFrame(
    market_rows
)


# ==================================================
# SUMMARY METRICS
# ==================================================

latest_observation = (
    df["observed_at"].max()
)

available_count = int(
    (
        df["available"]
        == True
    ).sum()
)

unavailable_count = int(
    (
        df["available"]
        == False
    ).sum()
)

quote_count = len(
    price_df
)

tight_days = int(
    market_df[
        "Signal"
    ]
    .isin(
        [
            "🔥 Very tight",
            "🟠 Tight",
        ]
    )
    .sum()
)

if changes_df.empty:

    recent_losses = 0

else:

    recent_losses = int(
        (
            changes_df["change"]
            == "📉 Availability lost"
        ).sum()
    )


# ==================================================
# TOP METRICS
# ==================================================

st.subheader(
    f"Overview — next {range_option} days"
)

col1, col2, col3, col4, col5, col6 = (
    st.columns(6)
)

col1.metric(
    "Available",
    available_count,
)

col2.metric(
    "Unavailable",
    unavailable_count,
)

col3.metric(
    "Tight market days",
    tight_days,
)

col4.metric(
    "Recent losses",
    recent_losses,
)

col5.metric(
    "Price quotes",
    quote_count,
)

col6.metric(
    "Latest update",
    latest_observation.strftime(
        "%d %b %Y"
    ),
)


st.divider()


# ==================================================
# MARKET AVAILABILITY CHART
# ==================================================

st.subheader(
    f"📈 Market availability — "
    f"next {range_option} days"
)

chart_df = market_df[
    [
        "Date",
        "Market availability",
    ]
].copy()

chart_df = chart_df.dropna(
    subset=[
        "Market availability"
    ]
)

chart_df = chart_df.set_index(
    "Date"
)

if chart_df.empty:

    st.info(
        "No market availability data "
        "is available for this period."
    )

else:

    st.line_chart(
        chart_df,
        y="Market availability",
        height=350,
    )

st.caption(
    "The chart shows the percentage of tracked competitors "
    "displaying availability for each date. 0% means none "
    "of the tracked competitors are showing availability; "
    "100% means all four are showing availability."
)


# ==================================================
# DAILY MARKET SIGNAL
# ==================================================

st.subheader(
    "🔥 Daily market signal"
)

market_display = (
    market_df.copy()
)

market_display["Date"] = (
    pd.to_datetime(
        market_display["Date"]
    ).dt.strftime(
        "%a %d %b"
    )
)

market_display[
    "Available competitors"
] = (
    market_display[
        "Available"
    ].astype(str)
    + "/"
    + market_display[
        "Observed"
    ].astype(str)
)

market_display[
    "Market availability"
] = market_display[
    "Market availability"
].apply(
    lambda x:
        f"{x:.0f}%"
        if pd.notna(x)
        else "No data"
)

market_display = (
    market_display[
        [
            "Date",
            "Available competitors",
            "Market availability",
            "Recent losses",
            "Recent openings",
            "Signal",
        ]
    ]
)

st.dataframe(
    market_display,
    use_container_width=True,
    hide_index=True,
    height=500,
)

st.caption(
    "Market availability is based on the four tracked "
    "competitors. A tight signal means fewer tracked "
    "listings are showing availability. It does not prove "
    "that unavailable properties are booked."
)


st.divider()


# ==================================================
# RECENT AVAILABILITY CHANGES
# ==================================================

st.subheader(
    "🔄 Recent availability changes"
)

if changes_df.empty:

    st.info(
        "No availability changes were detected "
        "between the latest two snapshots."
    )

else:

    changes_display = (
        changes_df[
            [
                "competitor",
                "stay_date",
                "previous",
                "current",
                "change",
                "observed_at",
            ]
        ].copy()
    )

    changes_display = (
        changes_display.rename(
            columns={
                "competitor":
                    "Competitor",
                "stay_date":
                    "Stay date",
                "previous":
                    "Previous",
                "current":
                    "Current",
                "change":
                    "Change",
                "observed_at":
                    "Detected",
            }
        )
    )

    changes_display[
        "Stay date"
    ] = pd.to_datetime(
        changes_display[
            "Stay date"
        ]
    ).dt.strftime(
        "%a %d %b"
    )

    changes_display[
        "Detected"
    ] = (
        changes_display[
            "Detected"
        ]
        .dt.tz_convert(
            "Australia/Hobart"
        )
        .dt.strftime(
            "%d %b %Y %H:%M"
        )
    )

    changes_display = (
        changes_display
        .sort_values(
            [
                "Detected",
                "Stay date",
            ],
            ascending=[
                False,
                True,
            ],
        )
    )

    st.dataframe(
        changes_display,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# ==================================================
# COMPETITOR CALENDAR
# ==================================================

st.subheader(
    f"📅 Competitor calendar — "
    f"next {range_option} days"
)

calendar = df.pivot(
    index="stay_date",
    columns="competitor",
    values="status",
)

for competitor in competitor_order:

    if competitor not in calendar.columns:

        calendar[
            competitor
        ] = "⚪ No data"


calendar = calendar[
    competitor_order
]

calendar = calendar.reindex(
    all_dates
)

calendar = calendar.fillna(
    "⚪ No data"
)

calendar.index = [
    day.strftime(
        "%a %d %b"
    )
    for day in calendar.index
]

st.dataframe(
    calendar,
    use_container_width=True,
    height=900,
)

st.caption(
    "🟢 Available = Airbnb currently allows the date. "
    "🔴 Unavailable does not necessarily mean booked; "
    "it may be booked, blocked or restricted. "
    "💰 Price is the average nightly value of an observed "
    "2-night stay quote, not an exact nightly rate."
)


st.divider()


# ==================================================
# COMPETITOR PRICE TREND
# ==================================================

st.subheader(
    f"💰 Competitor price trend — "
    f"next {range_option} days"
)

if price_df.empty:

    st.info(
        "Not enough price data yet. "
        "This chart will populate automatically "
        "as new price observations are collected."
    )

else:

    price_chart_df = (
        price_df[
            [
                "checkin_date",
                "competitor",
                "average_price_per_night_aud",
            ]
        ].copy()
    )

    price_chart_df = (
        price_chart_df.dropna(
            subset=[
                "average_price_per_night_aud"
            ]
        )
    )

    price_chart = (
        price_chart_df.pivot(
            index="checkin_date",
            columns="competitor",
            values="average_price_per_night_aud",
        )
    )

    existing_competitors = [
        competitor
        for competitor in competitor_order
        if competitor
        in price_chart.columns
    ]

    if existing_competitors:

        price_chart = price_chart[
            existing_competitors
        ]

        price_chart = (
            price_chart.sort_index()
        )

        st.line_chart(
            price_chart,
            height=400,
        )

        st.caption(
            "Each line represents the observed average "
            "nightly price for a 2-night Airbnb quote. "
            "Missing points remain empty. The dashboard "
            "does not estimate or interpolate missing "
            "competitor prices."
        )

    else:

        st.info(
            "No usable competitor price "
            "observations are available yet."
        )


# ==================================================
# MARKET AVERAGE PRICE
# ==================================================

st.subheader(
    "📊 Market average observed price"
)

if price_df.empty:

    st.info(
        "No market average can be calculated yet."
    )

else:

    market_price_source = (
        price_df[
            [
                "checkin_date",
                "competitor",
                "average_price_per_night_aud",
            ]
        ]
        .dropna(
            subset=[
                "average_price_per_night_aud"
            ]
        )
        .copy()
    )

    market_price = (
        market_price_source
        .groupby(
            "checkin_date"
        )
        .agg(
            market_average=(
                "average_price_per_night_aud",
                "mean",
            ),
            competitors_with_price=(
                "competitor",
                "nunique",
            ),
        )
        .reset_index()
        .sort_values(
            "checkin_date"
        )
    )

    if market_price.empty:

        st.info(
            "No market average can be "
            "calculated yet."
        )

    else:

        market_price_chart = (
            market_price[
                [
                    "checkin_date",
                    "market_average",
                ]
            ]
            .set_index(
                "checkin_date"
            )
        )

        st.line_chart(
            market_price_chart,
            height=350,
        )

        st.caption(
            "The market average uses only competitors "
            "that returned a valid quote for that check-in "
            "date. Missing competitor prices are not "
            "estimated."
        )

        # ------------------------------------------
        # MARKET PRICE SUPPORT TABLE
        # ------------------------------------------

        market_price_display = (
            market_price.copy()
        )

        market_price_display[
            "Check-in"
        ] = pd.to_datetime(
            market_price_display[
                "checkin_date"
            ]
        ).dt.strftime(
            "%a %d %b"
        )

        market_price_display[
            "Market average A$/night"
        ] = market_price_display[
            "market_average"
        ].apply(
            lambda x:
                f"A${x:,.2f}"
        )

        market_price_display[
            "Price coverage"
        ] = market_price_display[
            "competitors_with_price"
        ].apply(
            lambda x:
                f"{int(x)}/4"
        )

        market_price_display = (
            market_price_display[
                [
                    "Check-in",
                    "Market average A$/night",
                    "Price coverage",
                ]
            ]
        )

        st.dataframe(
            market_price_display,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Price coverage shows how many of the four "
            "tracked competitors contributed to each "
            "average. A 4/4 average is more representative "
            "than a 1/4 average."
        )


st.divider()


# ==================================================
# LATEST PRICE QUOTES
# ==================================================

st.subheader(
    f"💰 Latest observed price quotes — "
    f"next {range_option} days"
)

if price_df.empty:

    st.info(
        "No price quotes are currently "
        "available for the selected period."
    )

else:

    price_table = (
        price_df[
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
    )

    price_table = (
        price_table.rename(
            columns={
                "competitor":
                    "Competitor",
                "checkin_date":
                    "Check-in",
                "checkout_date":
                    "Check-out",
                "nights":
                    "Nights",
                "total_price_aud":
                    "Total A$",
                "average_price_per_night_aud":
                    "Average A$/night",
                "observed_at":
                    "Observed",
            }
        )
    )

    price_table[
        "Observed"
    ] = (
        price_table[
            "Observed"
        ]
        .dt.tz_convert(
            "Australia/Hobart"
        )
        .dt.strftime(
            "%d %b %Y %H:%M"
        )
    )

    price_table = (
        price_table.sort_values(
            [
                "Check-in",
                "Competitor",
            ]
        )
    )

    st.dataframe(
        price_table,
        use_container_width=True,
        hide_index=True,
    )
