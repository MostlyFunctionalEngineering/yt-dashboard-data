# YouTube Metrics Data Collector

Automated GitHub Action pipeline that daily fetches YouTube Analytics and
Data API metrics for a specified channel and publishes the structured JSON
output — plus a set of dynamic trend-arrow images — to an unlisted (secret)
GitHub Gist.

Built to let a Seeed Studio E1004 e-ink display, driven by SenseCraft HMI,
read deep YouTube channel statistics from a reachable but unlisted endpoint,
without exposing sensitive analytics data in a public repository.

---

## Overview

The script pulls channel totals, daily/weekly/monthly rollups (views, watch
time, subscribers gained/lost, likes, comments, shares, retention,
subscriber conversion rate), and top-video performance for the trailing
week. It also determines, for each tracked metric, whether the trend is up
or down across three comparison windows — week-over-week, this-week-vs-
4-week-average, and this-week-vs-12-week-average — and points to the
matching arrow image accordingly.

The output (`yt_metrics.json`) and a set of fixed-filename trend arrow PNGs
are pushed to a secret Gist via a real `git` clone/commit/push — not the
Gist REST API, which corrupts binary file content by forcing it through
JSON text encoding. Cloning the Gist as a git repo avoids that entirely.

---

## Setup & Configuration Guide

### Step 1: Create Google Cloud OAuth 2.0 Credentials & Enable APIs

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Select an existing project or create a new one.
3. In the left navigation, go to **APIs & Services → Library**.
4. Search for and enable both:
   * **YouTube Data API v3**
   * **YouTube Analytics API**
5. Go to **APIs & Services → Credentials**.
6. Click **+ Create Credentials → API Key**. Copy this key (used for
   `YT_API_KEY`).
7. Click **+ Create Credentials → OAuth client ID**:
   * **Application type:** Web application
   * **Name:** YouTube Analytics Sync
   * **Authorized redirect URIs:** `https://developers.google.com/oauthplayground`
8. Save and copy both the **Client ID** and **Client Secret**.
9. On the **OAuth consent screen**, set publishing status to **In
   production** (not Testing) — refresh tokens for apps left in Testing
   mode expire after 7 days and will silently break the daily Action.

### Step 2: Mint a Long-Lived Refresh Token via Google OAuth Playground

1. Open the [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground).
2. Click the gear icon (top right):
   * Check **Use your own OAuth credentials**.
   * Enter the Client ID and Client Secret from Step 1.
3. In the left panel, find and select:
   `https://www.googleapis.com/auth/yt-analytics.readonly`
4. Click **Authorize APIs** and sign in with the account that manages the
   channel.
5. Click **Exchange authorization code for tokens**.
6. Copy the `refresh_token` value (begins with `1//0...`).

### Step 3: Create the Unlisted Target Gist

1. Go to [gist.github.com](https://gist.github.com).
2. Name the file `yt_metrics.json`, enter `{}` as placeholder content.
3. Click **Create secret gist**.
4. Copy the 32-character ID from the end of the Gist's URL
   (`https://gist.github.com/<username>/<GIST_ID>`).

### Step 4: Create a Personal Access Token (PAT)

1. In GitHub: **Settings → Developer Settings → Personal Access Tokens →
   Tokens (classic)**.
2. **Generate new token (classic)**.
3. Select the **`gist`** scope only.
4. Copy the generated token (`ghp_...`).

### Step 5: Add Two Static Arrow Images to the Main Repo

Commit two real PNG files (not SVG, not text) to `assets/` in this
repository:

* `assets/arrow_up.png`
* `assets/arrow_down.png`

These are the two source templates every trend indicator gets copied from
at runtime. They only need to be added once — the daily Action never
regenerates them, it only copies one or the other into a per-metric
fixed-name file.

### Step 6: Configure GitHub Secrets

In this repository: **Settings → Secrets and variables → Actions**, add:

| Secret Name | Description |
| :--- | :--- |
| `YT_API_KEY` | YouTube Data API key from Step 1 |
| `YT_CHANNEL_ID` | Channel ID (starts with `UC...`) |
| `YT_OAUTH_CLIENT_ID` | OAuth 2.0 Client ID from Step 1 |
| `YT_OAUTH_CLIENT_SECRET` | OAuth 2.0 Client Secret from Step 1 |
| `YT_OAUTH_REFRESH_TOKEN` | Refresh token from Step 2 |
| `GIST_ID` | Gist ID from Step 3 |
| `GIST_TOKEN` | PAT with `gist` scope from Step 4 |
| `GIST_USER` | Your GitHub username (used to build endpoint URLs) |

### Step 7: Configure Repository Variables

Unlike the secrets above, these two values aren't sensitive — they're just
used to build the URL to this repo's static arrow images. Set them under
**Settings → Secrets and variables → Actions → Variables tab → New
repository variable** (a separate tab from Secrets, on the same page):

| Variable Name | Description |
| :--- | :--- |
| `REPO_OWNER` | Your GitHub username or org (e.g. `MostlyFunctionalEngineering`) |
| `REPO_NAME` | This repository's name (e.g. `yt-dashboard-data`) |

The workflow reads these as required — if either is missing, the script
fails immediately rather than silently pointing at someone else's assets.
If you fork this repo, you must set both of these to your own fork's
owner/name before the Action will run successfully.

## How the Pipeline Runs

`.github/workflows/update_metrics.yml` runs daily at 06:00 UTC (and on
manual dispatch):

1. Checks out the repo and installs `requests`.
2. Runs `scripts/update_metrics.py`, which:
   - Refreshes an OAuth access token from the stored refresh token.
   - Queries the YouTube Analytics API for daily metrics over a rolling
     window, and separately for the top 5 videos by views in the trailing
     week (titles resolved via the public Data API).
   - Computes weekly/monthly rollups and trend direction/percentage across
     WoW, 4-week, 12-week, 30-day, and 90-day comparisons.
   - Writes `yt_metrics.json` locally.
   - Copies `assets/arrow_up.png` or `assets/arrow_down.png` over each
     fixed per-metric filename (e.g. `trend_arrow_views_wow.png`) based on
     that metric's current direction.
3. A second workflow step clones the secret Gist as a real git repository,
   copies in `yt_metrics.json` and all `trend_arrow_*.png` files, and
   pushes — preserving binary integrity, unlike a REST API update would.

---

## Data Access & Security Considerations

The `contents: read` permission is sufficient for this workflow — nothing
is committed back to the main repository. All generated output goes to the
Gist via its own git remote, authenticated separately with `GIST_TOKEN`.

**Privacy note:** a secret Gist is *unlisted*, not access-controlled —
anyone with the exact URL can read it. It won't appear in search or your
public profile, but it isn't a substitute for real authentication if the
data needs to stay genuinely private.

### Accessing the Data

```
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/yt_metrics.json
```

### Accessing the Trend Arrows

Each of the following is a fixed URL whose underlying image is overwritten
daily to reflect current trend direction:

```
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_views_wow.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_subs_wow.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_watch_hours_wow.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_views_30d.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_watch_hours_30d.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_subs_30d.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_views_90d.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_watch_hours_90d.png
https://gist.githubusercontent.com/<GIST_USER>/<GIST_ID>/raw/trend_arrow_subs_90d.png
```

Point a SenseCraft Image widget at any of these — the URL never changes,
only the bytes behind it.