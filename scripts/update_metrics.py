import os
import json
import datetime
import shutil
from collections import defaultdict
import requests


# =========================================================
# Configuration
# =========================================================

CLIENT_ID = os.environ["YT_OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["YT_OAUTH_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YT_OAUTH_REFRESH_TOKEN"]
API_KEY = os.environ["YT_API_KEY"]
CHANNEL_ID = os.environ["YT_CHANNEL_ID"]
GIST_ID = os.environ.get("GIST_ID")
GIST_TOKEN = os.environ.get("GIST_TOKEN")

# Repository variables for static image asset resolution
REPO_OWNER = os.environ.get(
    "REPO_OWNER",
    "MostlyFunctionalEngineering",
)
REPO_NAME = os.environ.get(
    "REPO_NAME",
    "yt-dashboard-data",
)
BRANCH = os.environ.get(
    "REPO_BRANCH",
    "main",
)

# These must be REAL PNG files committed once to assets/
# in your repo.
# Do not regenerate these per-run — there are only two
# states (up/down).
ARROW_UP_URL = (
    f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/"
    f"{BRANCH}/assets/arrow_up.png"
)

ARROW_DOWN_URL = (
    f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/"
    f"{BRANCH}/assets/arrow_down.png"
)

OUTPUT_FILE = "yt_metrics.json"


# =========================================================
# Authentication
# =========================================================

def get_access_token():
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )

    r.raise_for_status()

    return r.json()["access_token"]


AUTH = {
    "Authorization": f"Bearer {get_access_token()}"
}


# =========================================================
# Date range
# =========================================================

# Analytics data typically lags 1–2 days behind real time.
END = (
    datetime.date.today()
    - datetime.timedelta(days=2)
)

START = (
    END
    - datetime.timedelta(days=400)
)


# =========================================================
# Analytics metrics
# =========================================================

METRICS = ",".join([
    "views",
    "likes",
    "comments",
    "shares",
    "estimatedMinutesWatched",
    "averageViewPercentage",
    "subscribersGained",
    "subscribersLost",
])


# =========================================================
# Daily channel analytics
# =========================================================

resp = requests.get(
    "https://youtubeanalytics.googleapis.com/v2/reports",
    headers=AUTH,
    params={
        "ids": f"channel=={CHANNEL_ID}",
        "startDate": START.isoformat(),
        "endDate": END.isoformat(),
        "metrics": METRICS,
        "dimensions": "day",
        "sort": "day",
    },
)

if not resp.ok:
    print("Google API Error Body:", resp.text)

resp.raise_for_status()

report = resp.json()

columns = [
    h["name"]
    for h in report["columnHeaders"]
]

daily_rows = {
    row[0]: dict(
        zip(
            columns[1:],
            row[1:],
        )
    )
    for row in report.get("rows", [])
}

dates_sorted = sorted(daily_rows)


# =========================================================
# Top videos this week
# =========================================================

week_start = (
    END
    - datetime.timedelta(days=6)
)

# Get more than 3 so that if metadata is unavailable
# for one video we still have backup candidates.
resp = requests.get(
    "https://youtubeanalytics.googleapis.com/v2/reports",
    headers=AUTH,
    params={
        "ids": f"channel=={CHANNEL_ID}",
        "startDate": week_start.isoformat(),
        "endDate": END.isoformat(),
        "metrics": ",".join([
            "views",
            "likes",
            "comments",
            "shares",
            "estimatedMinutesWatched",
            "averageViewPercentage",
            "subscribersGained",
            "subscribersLost",
        ]),
        "dimensions": "video",
        "sort": "-views",
        "maxResults": 5,
    },
)

resp.raise_for_status()

video_report = resp.json()

video_columns = [
    h["name"]
    for h in video_report["columnHeaders"]
]

top_rows = video_report.get("rows", [])

video_data = {}

for row in top_rows:
    video_id = row[0]

    values = dict(
        zip(
            video_columns[1:],
            row[1:],
        )
    )

    video_data[video_id] = {
        "views": int(
            values.get("views", 0)
        ),

        "likes": int(
            values.get("likes", 0)
        ),

        "comments": int(
            values.get("comments", 0)
        ),

        "shares": int(
            values.get("shares", 0)
        ),

        "estimated_minutes_watched": int(
            values.get(
                "estimatedMinutesWatched",
                0,
            )
        ),

        "average_view_percentage": round(
            float(
                values.get(
                    "averageViewPercentage",
                    0,
                )
            ),
            2,
        ),

        "subscribers_gained": int(
            values.get(
                "subscribersGained",
                0,
            )
        ),

        "subscribers_lost": int(
            values.get(
                "subscribersLost",
                0,
            )
        ),
    }


video_ids = [
    row[0]
    for row in top_rows
]


# =========================================================
# Get video titles
# =========================================================

titles = {}

if video_ids:
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "part": "snippet",
            "id": ",".join(video_ids),
            "key": API_KEY,
        },
    )

    r.raise_for_status()

    titles = {
        item["id"]: item["snippet"]["title"]
        for item in r.json()["items"]
    }


# =========================================================
# Build individual top-video records
# =========================================================

def build_video_record(video_id, rank):

    data = video_data.get(
        video_id,
        {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "estimated_minutes_watched": 0,
            "average_view_percentage": 0.0,
            "subscribers_gained": 0,
            "subscribers_lost": 0,
        },
    )

    views = data["views"]

    gained = data[
        "subscribers_gained"
    ]

    lost = data[
        "subscribers_lost"
    ]

    net_subscribers = (
        gained - lost
    )

    if views:
        subscriber_conversion = round(
            (
                net_subscribers
                / views
            )
            * 1000,
            2,
        )
    else:
        subscriber_conversion = 0.0

    return {
        "rank": rank,

        "video_id": video_id,

        "title": titles.get(
            video_id,
            video_id,
        ),

        "views": views,

        "watch_hours": round(
            data[
                "estimated_minutes_watched"
            ]
            / 60,
            1,
        ),

        "average_view_percentage":
            data[
                "average_view_percentage"
            ],

        "likes": data["likes"],

        "comments": data[
            "comments"
        ],

        "shares": data["shares"],

        "subscribers_gained":
            gained,

        "subscribers_lost":
            lost,

        "net_subscribers":
            net_subscribers,

        "subscriber_conversion_per_1000_views":
            subscriber_conversion,
    }


top_video_records = []

for rank, video_id in enumerate(
    video_ids[:3],
    start=1,
):
    top_video_records.append(
        build_video_record(
            video_id,
            rank,
        )
    )


# Guarantee three individual objects exist
# even if fewer than three videos were returned.
while len(top_video_records) < 3:

    empty_rank = (
        len(top_video_records)
        + 1
    )

    top_video_records.append({
        "rank": empty_rank,
        "video_id": "",
        "title": "",
        "views": 0,
        "watch_hours": 0.0,
        "average_view_percentage": 0.0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "subscribers_gained": 0,
        "subscribers_lost": 0,
        "net_subscribers": 0,
        "subscriber_conversion_per_1000_views": 0.0,
    })


# =========================================================
# Channel totals (public Data API)
# =========================================================

r = requests.get(
    "https://www.googleapis.com/youtube/v3/channels",
    params={
        "part": "statistics,snippet",
        "id": CHANNEL_ID,
        "key": API_KEY,
    },
)

r.raise_for_status()

ch = r.json()["items"][0]

total_subs = int(
    ch["statistics"]["subscriberCount"]
)

total_views = int(
    ch["statistics"]["viewCount"]
)

channel_title = ch[
    "snippet"
]["title"]


# =========================================================
# Convert daily data into arrays
# =========================================================

def col(name, cast=float):
    return [
        cast(
            daily_rows[d].get(
                name,
                0,
            )
        )
        for d in dates_sorted
    ]


daily = {
    "dates": dates_sorted,

    "views": col(
        "views",
        int,
    ),

    "subscribers_gained": col(
        "subscribersGained",
        int,
    ),

    "subscribers_lost": col(
        "subscribersLost",
        int,
    ),

    "estimated_minutes_watched":
        col(
            "estimatedMinutesWatched",
            int,
        ),

    "average_view_percentage":
        col(
            "averageViewPercentage"
        ),

    "likes": col(
        "likes",
        int,
    ),

    "comments": col(
        "comments",
        int,
    ),

    "shares": col(
        "shares",
        int,
    ),
}


daily["net_subscribers"] = [
    g - l
    for g, l in zip(
        daily["subscribers_gained"],
        daily["subscribers_lost"],
    )
]


# =========================================================
# Rollups
# =========================================================

def rollup(
    period_days,
    num_periods,
):
    """
    Trailing fixed-length buckets,
    most recent last.
    """

    labels = []

    buckets = defaultdict(list)

    for i in range(num_periods):

        b_end = (
            END
            - datetime.timedelta(
                days=period_days * i
            )
        )

        b_start = (
            b_end
            - datetime.timedelta(
                days=period_days - 1
            )
        )

        labels.append(
            b_end.isoformat()
        )

        for d in dates_sorted:

            dd = (
                datetime.date.fromisoformat(
                    d
                )
            )

            if (
                b_start
                <= dd
                <= b_end
            ):
                buckets[
                    b_end.isoformat()
                ].append(d)

    labels.reverse()

    def agg(
        name,
        how,
        cast=float,
    ):
        out = []

        for label in labels:

            vals = [
                cast(
                    daily_rows[d].get(
                        name,
                        0,
                    )
                )
                for d in buckets[label]
            ]

            if not vals:
                out.append(0)

            elif how == "sum":
                out.append(
                    sum(vals)
                )

            else:
                out.append(
                    round(
                        sum(vals)
                        / len(vals),
                        2,
                    )
                )

        return out

    gained = agg(
        "subscribersGained",
        "sum",
        int,
    )

    lost = agg(
        "subscribersLost",
        "sum",
        int,
    )

    views = agg(
        "views",
        "sum",
        int,
    )

    watch_hours = [
        round(
            m / 60,
            1,
        )
        for m in agg(
            "estimatedMinutesWatched",
            "sum",
            int,
        )
    ]

    average_view_percentage = agg(
        "averageViewPercentage",
        "avg",
    )

    net_subscribers = [
        g - l
        for g, l in zip(
            gained,
            lost,
        )
    ]

    # Weekly subscriber conversion.
    #
    # This remains useful for the weekly chart data.
    # The baseline calculations below use aggregate
    # conversion instead of averaging these weekly rates.
    subscriber_conversion = []

    for (
        views_value,
        subs_value,
    ) in zip(
        views,
        net_subscribers,
    ):

        if views_value:
            conversion = round(
                (
                    subs_value
                    / views_value
                )
                * 1000,
                2,
            )
        else:
            conversion = 0.0

        subscriber_conversion.append(
            conversion
        )

    return {
        "labels": labels,

        "views": views,

        "subscribers_gained":
            gained,

        "subscribers_lost":
            lost,

        "net_subscribers":
            net_subscribers,

        "watch_hours":
            watch_hours,

        "average_view_percentage":
            average_view_percentage,

        "subscriber_conversion_per_1000_views":
            subscriber_conversion,

        "likes": agg(
            "likes",
            "sum",
            int,
        ),

        "comments": agg(
            "comments",
            "sum",
            int,
        ),

        "shares": agg(
            "shares",
            "sum",
            int,
        ),
    }


weekly = rollup(
    7,
    12,
)

monthly = rollup(
    30,
    12,
)


# =========================================================
# Utility functions
# =========================================================

def safe_pct(
    change,
    base,
):
    if not base:
        return 0.0

    return round(
        (change / base) * 100,
        1,
    )


def get_trend_meta(
    curr,
    prev,
):
    """
    Compare current value against previous value.
    """

    diff = curr - prev

    pct = safe_pct(
        diff,
        abs(prev),
    )

    direction = (
        "up"
        if diff >= 0
        else "down"
    )

    url = (
        ARROW_UP_URL
        if diff >= 0
        else ARROW_DOWN_URL
    )

    sign = (
        "+"
        if diff >= 0
        else ""
    )

    display_str = (
        f"{curr:,}   {sign}{pct}%"
    )

    return (
        pct,
        direction,
        url,
        display_str,
    )


def average(values):
    """
    Arithmetic average of a list of values.
    """

    if not values:
        return 0.0

    return round(
        sum(values)
        / len(values),
        2,
    )


def aggregate_conversion(
    views,
    subscribers,
):
    """
    Calculate subscriber conversion from
    aggregate totals rather than averaging
    individual weekly conversion rates.

    Result:
        net subscribers / total views * 1000
    """

    total_views = sum(views)

    total_subscribers = sum(
        subscribers
    )

    if not total_views:
        return 0.0

    return round(
        (
            total_subscribers
            / total_views
        )
        * 1000,
        2,
    )


# =========================================================
# Weekly metrics
# =========================================================

views_this_week = (
    weekly["views"][-1]
)

views_prev_week = (
    weekly["views"][-2]
    if len(weekly["views"]) > 1
    else 0
)

(
    views_wow_pct,
    views_wow_dir,
    views_wow_url,
    views_wow_disp,
) = get_trend_meta(
    views_this_week,
    views_prev_week,
)


subs_this_week = (
    weekly["net_subscribers"][-1]
)

subs_prev_week = (
    weekly["net_subscribers"][-2]
    if len(weekly["net_subscribers"]) > 1
    else 0
)

(
    subs_wow_pct,
    subs_wow_dir,
    subs_wow_url,
    subs_wow_disp,
) = get_trend_meta(
    subs_this_week,
    subs_prev_week,
)


watch_hrs_this_week = (
    weekly["watch_hours"][-1]
)

watch_hrs_prev_week = (
    weekly["watch_hours"][-2]
    if len(weekly["watch_hours"]) > 1
    else 0
)

(
    hrs_wow_pct,
    hrs_wow_dir,
    hrs_wow_url,
    hrs_wow_disp,
) = get_trend_meta(
    watch_hrs_this_week,
    watch_hrs_prev_week,
)


# =========================================================
# Current vs baseline
#
# IMPORTANT:
#
# This Week:
#   Most recently completed 7-day period.
#
# 4-Week Average:
#   Four completed weeks immediately before
#   the current week.
#
# 12-Week Average:
#   Twelve completed weeks immediately before
#   the current week.
#
# The current week is excluded from both baselines.
# =========================================================

# We generate 13 weeks:
#
#   weeks -13 through -2 = 12 completed
#   baseline weeks
#   week -1              = current week
#
# This gives us enough data to calculate both
# baselines without including the current week.

weekly_baseline = rollup(
    7,
    13,
)


# Current week is the final entry.
#
# Previous four completed weeks:
#   [-5:-1]
#
# Previous twelve completed weeks:
#   [-13:-1]

baseline_4_start = -5
baseline_4_end = -1

baseline_12_start = -13
baseline_12_end = -1


def average_metric(
    metric_name,
    start,
    end,
):
    values = (
        weekly_baseline[
            metric_name
        ][start:end]
    )

    return average(values)


# ---------------------------------------------------------
# Views
# ---------------------------------------------------------

views_4wk_avg = average_metric(
    "views",
    baseline_4_start,
    baseline_4_end,
)

views_12wk_avg = average_metric(
    "views",
    baseline_12_start,
    baseline_12_end,
)


# ---------------------------------------------------------
# Watch hours
# ---------------------------------------------------------

watch_hours_4wk_avg = average_metric(
    "watch_hours",
    baseline_4_start,
    baseline_4_end,
)

watch_hours_12wk_avg = average_metric(
    "watch_hours",
    baseline_12_start,
    baseline_12_end,
)


# ---------------------------------------------------------
# Net subscribers
# ---------------------------------------------------------

net_subs_4wk_avg = average_metric(
    "net_subscribers",
    baseline_4_start,
    baseline_4_end,
)

net_subs_12wk_avg = average_metric(
    "net_subscribers",
    baseline_12_start,
    baseline_12_end,
)


# ---------------------------------------------------------
# Retention
#
# Keep this as an average of the weekly
# average-view-percentage values.
# ---------------------------------------------------------

retention_4wk_avg = average_metric(
    "average_view_percentage",
    baseline_4_start,
    baseline_4_end,
)

retention_12wk_avg = average_metric(
    "average_view_percentage",
    baseline_12_start,
    baseline_12_end,
)


# ---------------------------------------------------------
# Subscriber conversion
#
# IMPORTANT:
#
# Do NOT average weekly conversion rates.
#
# Instead:
#
#     total net subscribers
#     --------------------- x 1000
#       total views
#
# This prevents a tiny low-view week from
# having the same weight as a large week.
# ---------------------------------------------------------

conversion_4wk_views = (
    weekly_baseline["views"][
        baseline_4_start:
        baseline_4_end
    ]
)

conversion_4wk_subscribers = (
    weekly_baseline[
        "net_subscribers"
    ][
        baseline_4_start:
        baseline_4_end
    ]
)

conversion_12wk_views = (
    weekly_baseline["views"][
        baseline_12_start:
        baseline_12_end
    ]
)

conversion_12wk_subscribers = (
    weekly_baseline[
        "net_subscribers"
    ][
        baseline_12_start:
        baseline_12_end
    ]
)


conversion_4wk_avg = aggregate_conversion(
    conversion_4wk_views,
    conversion_4wk_subscribers,
)

conversion_12wk_avg = aggregate_conversion(
    conversion_12wk_views,
    conversion_12wk_subscribers,
)


# ---------------------------------------------------------
# Current-week health values
# ---------------------------------------------------------

retention_this_week = (
    weekly[
        "average_view_percentage"
    ][-1]
)

conversion_this_week = (
    weekly[
        "subscriber_conversion_per_1000_views"
    ][-1]
)


# =========================================================
# Current Health comparison records
# =========================================================

def build_health_metric(
    this_week,
    four_week_avg,
    twelve_week_avg,
):
    """
    Build a complete health record.

    Comparison 1:
        This Week vs 4-Week Average

    Comparison 2:
        4-Week Average vs 12-Week Average
    """

    (
        current_vs_4wk_pct,
        current_vs_4wk_direction,
        current_vs_4wk_arrow,
        current_vs_4wk_display,
    ) = get_trend_meta(
        this_week,
        four_week_avg,
    )

    (
        four_week_vs_12wk_pct,
        four_week_vs_12wk_direction,
        four_week_vs_12wk_arrow,
        four_week_vs_12wk_display,
    ) = get_trend_meta(
        four_week_avg,
        twelve_week_avg,
    )

    return {
        # Raw values
        "this_week": this_week,

        "previous_4_week_average":
            four_week_avg,

        "previous_12_week_average":
            twelve_week_avg,

        # This Week vs 4-Week Average
        "this_week_vs_4_week_pct":
            current_vs_4wk_pct,

        "this_week_vs_4_week_direction":
            current_vs_4wk_direction,

        "this_week_vs_4_week_arrow_url":
            current_vs_4wk_arrow,

        "this_week_vs_4_week_display":
            current_vs_4wk_display,

        # 4-Week Average vs 12-Week Average
        "4_week_vs_12_week_pct":
            four_week_vs_12wk_pct,

        "4_week_vs_12_week_direction":
            four_week_vs_12wk_direction,

        "4_week_vs_12_week_arrow_url":
            four_week_vs_12wk_arrow,

        "4_week_vs_12_week_display":
            four_week_vs_12wk_display,
    }


current_health = {

    # -----------------------------------------------------
    # Views
    # -----------------------------------------------------

    "views": build_health_metric(
        views_this_week,
        views_4wk_avg,
        views_12wk_avg,
    ),

    # -----------------------------------------------------
    # Watch hours
    # -----------------------------------------------------

    "watch_hours": build_health_metric(
        watch_hrs_this_week,
        watch_hours_4wk_avg,
        watch_hours_12wk_avg,
    ),

    # -----------------------------------------------------
    # Net subscribers
    # -----------------------------------------------------

    "net_subscribers": build_health_metric(
        subs_this_week,
        net_subs_4wk_avg,
        net_subs_12wk_avg,
    ),

    # -----------------------------------------------------
    # Retention
    # -----------------------------------------------------

    "retention": build_health_metric(
        retention_this_week,
        retention_4wk_avg,
        retention_12wk_avg,
    ),

    # -----------------------------------------------------
    # Subscriber conversion
    # -----------------------------------------------------

    "subscriber_conversion_per_1000_views":
        build_health_metric(
            conversion_this_week,
            conversion_4wk_avg,
            conversion_12wk_avg,
        ),
}


# =========================================================
# 30-Day & 90-Day calculations
# =========================================================

views_30d_curr = (
    monthly["views"][-1]
)

views_30d_prev = (
    monthly["views"][-2]
    if len(monthly["views"]) > 1
    else 0
)

(
    v30_pct,
    v30_dir,
    v30_url,
    v30_disp,
) = get_trend_meta(
    views_30d_curr,
    views_30d_prev,
)


hrs_30d_curr = (
    monthly["watch_hours"][-1]
)

hrs_30d_prev = (
    monthly["watch_hours"][-2]
    if len(monthly["watch_hours"]) > 1
    else 0
)

(
    h30_pct,
    h30_dir,
    h30_url,
    h30_disp,
) = get_trend_meta(
    hrs_30d_curr,
    hrs_30d_prev,
)


subs_30d_curr = (
    monthly["net_subscribers"][-1]
)

subs_30d_prev = (
    monthly["net_subscribers"][-2]
    if len(monthly["net_subscribers"]) > 1
    else 0
)

(
    s30_pct,
    s30_dir,
    s30_url,
    s30_disp,
) = get_trend_meta(
    subs_30d_curr,
    subs_30d_prev,
)


views_90d_curr = sum(
    monthly["views"][-3:]
)

views_90d_prev = (
    sum(
        monthly["views"][-6:-3]
    )
    if len(monthly["views"]) >= 6
    else 0
)

(
    v90_pct,
    v90_dir,
    v90_url,
    v90_disp,
) = get_trend_meta(
    views_90d_curr,
    views_90d_prev,
)


hrs_90d_curr = sum(
    monthly["watch_hours"][-3:]
)

hrs_90d_prev = (
    sum(
        monthly["watch_hours"][-6:-3]
    )
    if len(monthly["watch_hours"]) >= 6
    else 0
)

(
    h90_pct,
    h90_dir,
    h90_url,
    h90_disp,
) = get_trend_meta(
    hrs_90d_curr,
    hrs_90d_prev,
)


subs_90d_curr = sum(
    monthly["net_subscribers"][-3:]
)

subs_90d_prev = (
    sum(
        monthly["net_subscribers"][-6:-3]
    )
    if len(monthly["net_subscribers"]) >= 6
    else 0
)

(
    s90_pct,
    s90_dir,
    s90_url,
    s90_disp,
) = get_trend_meta(
    subs_90d_curr,
    subs_90d_prev,
)


# =========================================================
# Summary
# =========================================================

summary = {

    # -----------------------------------------------------
    # Subscribers
    # -----------------------------------------------------

    "subscribers_total":
        total_subs,

    "subscribers_net_this_week":
        subs_this_week,

    "subscribers_wow_change_pct":
        subs_wow_pct,

    "subscribers_wow_direction":
        subs_wow_dir,

    "subscribers_wow_indicator_url":
        subs_wow_url,

    "subscribers_wow_display":
        subs_wow_disp,


    # -----------------------------------------------------
    # Views
    # -----------------------------------------------------

    "views_this_week":
        views_this_week,

    "views_wow_change_pct":
        views_wow_pct,

    "views_wow_direction":
        views_wow_dir,

    "views_wow_indicator_url":
        views_wow_url,

    "views_wow_display":
        views_wow_disp,


    # -----------------------------------------------------
    # Watch hours
    # -----------------------------------------------------

    "watch_hours_this_week":
        watch_hrs_this_week,

    "watch_hours_wow_change_pct":
        hrs_wow_pct,

    "watch_hours_wow_direction":
        hrs_wow_dir,

    "watch_hours_wow_indicator_url":
        hrs_wow_url,

    "watch_hours_wow_display":
        hrs_wow_disp,


    # -----------------------------------------------------
    # Retention
    # -----------------------------------------------------

    "average_view_percentage_this_week":
        retention_this_week,


    # -----------------------------------------------------
    # Subscriber conversion
    # -----------------------------------------------------

    "subscriber_conversion_per_1000_views_this_week":
        conversion_this_week,


    # -----------------------------------------------------
    # Engagement
    # -----------------------------------------------------

    "likes_this_week":
        weekly["likes"][-1],

    "comments_this_week":
        weekly["comments"][-1],

    "shares_this_week":
        weekly["shares"][-1],
}


# =========================================================
# 30 / 90 day ranges
# =========================================================

ranges = {

    "last_30_days": {

        "views":
            views_30d_curr,

        "views_mom_pct":
            v30_pct,

        "views_mom_direction":
            v30_dir,

        "views_mom_indicator_url":
            v30_url,

        "views_mom_display":
            v30_disp,


        "watch_hours":
            hrs_30d_curr,

        "watch_hours_mom_pct":
            h30_pct,

        "watch_hours_mom_direction":
            h30_dir,

        "watch_hours_mom_indicator_url":
            h30_url,

        "watch_hours_mom_display":
            h30_disp,


        "net_subscribers":
            subs_30d_curr,

        "net_subscribers_mom_pct":
            s30_pct,

        "net_subscribers_mom_direction":
            s30_dir,

        "net_subscribers_mom_indicator_url":
            s30_url,

        "net_subscribers_mom_display":
            s30_disp,
    },


    "last_90_days": {

        "views":
            views_90d_curr,

        "views_qoq_pct":
            v90_pct,

        "views_qoq_direction":
            v90_dir,

        "views_qoq_indicator_url":
            v90_url,

        "views_qoq_display":
            v90_disp,


        "watch_hours":
            hrs_90d_curr,

        "watch_hours_qoq_pct":
            h90_pct,

        "watch_hours_qoq_direction":
            h90_dir,

        "watch_hours_qoq_indicator_url":
            h90_url,

        "watch_hours_qoq_display":
            h90_disp,


        "net_subscribers":
            subs_90d_curr,

        "net_subscribers_qoq_pct":
            s90_pct,

        "net_subscribers_qoq_direction":
            s90_dir,

        "net_subscribers_qoq_indicator_url":
            s90_url,

        "net_subscribers_qoq_display":
            s90_disp,
    },
}


# =========================================================
# Weekly chart data
# =========================================================

weekly_totals = {

    "last_4_weeks": {

        "labels":
            weekly["labels"][-4:],

        "views":
            weekly["views"][-4:],

        "watch_hours":
            weekly["watch_hours"][-4:],

        "net_subscribers":
            weekly["net_subscribers"][-4:],
    },


    "last_12_weeks": {

        "labels":
            weekly["labels"][-12:],

        "views":
            weekly["views"][-12:],

        "watch_hours":
            weekly["watch_hours"][-12:],

        "net_subscribers":
            weekly["net_subscribers"][-12:],
    },
}


# =========================================================
# Final JSON output
# =========================================================

output = {

    "meta": {

        "last_updated":
            datetime.datetime.utcnow().isoformat(
                timespec="seconds"
            )
            + "Z",

        "channel_title":
            channel_title,
    },


    "summary":
        summary,


    # -----------------------------------------------------
    # NEW / EXPANDED:
    # Current channel health
    # -----------------------------------------------------

    "current_health":
        current_health,


    "ranges":
        ranges,


    "weekly_totals":
        weekly_totals,


    "daily":
        daily,


    "weekly":
        weekly,


    "monthly":
        monthly,


    # Keep the existing array for compatibility.
    "top_videos_this_week":
        top_video_records,


    # Individual entries for dashboard widgets.
    "top_video_1":
        top_video_records[0],

    "top_video_2":
        top_video_records[1],

    "top_video_3":
        top_video_records[2],
}


# =========================================================
# Write JSON
# =========================================================

with open(
    OUTPUT_FILE,
    "w",
) as f:

    json.dump(
        output,
        f,
        indent=2,
    )


# =========================================================
# Arrow assets
# =========================================================

ARROW_TARGETS = {

    # -----------------------------------------------------
    # Existing summary arrows
    # -----------------------------------------------------

    "trend_arrow_views_wow.png":
        views_wow_dir,

    "trend_arrow_subs_wow.png":
        subs_wow_dir,

    "trend_arrow_watch_hours_wow.png":
        hrs_wow_dir,


    "trend_arrow_views_30d.png":
        v30_dir,

    "trend_arrow_watch_hours_30d.png":
        h30_dir,

    "trend_arrow_subs_30d.png":
        s30_dir,


    "trend_arrow_views_90d.png":
        v90_dir,

    "trend_arrow_watch_hours_90d.png":
        h90_dir,

    "trend_arrow_subs_90d.png":
        s90_dir,


    # -----------------------------------------------------
    # Current Health arrows
    #
    # This Week vs Previous 4-Week Average
    # -----------------------------------------------------

    "trend_arrow_health_views_current_vs_4wk.png":
        current_health["views"][
            "this_week_vs_4_week_direction"
        ],

    "trend_arrow_health_watch_hours_current_vs_4wk.png":
        current_health["watch_hours"][
            "this_week_vs_4_week_direction"
        ],

    "trend_arrow_health_subs_current_vs_4wk.png":
        current_health["net_subscribers"][
            "this_week_vs_4_week_direction"
        ],

    "trend_arrow_health_retention_current_vs_4wk.png":
        current_health["retention"][
            "this_week_vs_4_week_direction"
        ],

    "trend_arrow_health_conversion_current_vs_4wk.png":
        current_health[
            "subscriber_conversion_per_1000_views"
        ][
            "this_week_vs_4_week_direction"
        ],


    # -----------------------------------------------------
    # Current Health arrows
    #
    # Previous 4-Week Average vs Previous 12-Week Average
    # -----------------------------------------------------

    "trend_arrow_health_views_4wk_vs_12wk.png":
        current_health["views"][
            "4_week_vs_12_week_direction"
        ],

    "trend_arrow_health_watch_hours_4wk_vs_12wk.png":
        current_health["watch_hours"][
            "4_week_vs_12_week_direction"
        ],

    "trend_arrow_health_subs_4wk_vs_12wk.png":
        current_health["net_subscribers"][
            "4_week_vs_12_week_direction"
        ],

    "trend_arrow_health_retention_4wk_vs_12wk.png":
        current_health["retention"][
            "4_week_vs_12_week_direction"
        ],

    "trend_arrow_health_conversion_4wk_vs_12wk.png":
        current_health[
            "subscriber_conversion_per_1000_views"
        ][
            "4_week_vs_12_week_direction"
        ],
}


# =========================================================
# Copy arrow assets
# =========================================================

os.makedirs(
    "assets",
    exist_ok=True,
)


for filename, direction in ARROW_TARGETS.items():

    src = (
        "assets/arrow_up.png"
        if direction == "up"
        else "assets/arrow_down.png"
    )

    shutil.copy(
        src,
        f"assets/{filename}",
    )


# =========================================================
# Debug output
# =========================================================

print(
    json.dumps(
        summary,
        indent=2,
    )
)


print(
    "\nCurrent Health:"
)

print(
    json.dumps(
        current_health,
        indent=2,
    )
)


print(
    "\nTop Videos:"
)

print(
    json.dumps(
        {
            "top_video_1":
                top_video_records[0],

            "top_video_2":
                top_video_records[1],

            "top_video_3":
                top_video_records[2],
        },
        indent=2,
    )
)


print(
    "\nArrow assets updated:",
    list(
        ARROW_TARGETS.keys()
    ),
)
