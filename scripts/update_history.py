import json, os, datetime
import requests

API_KEY = os.environ["YT_API_KEY"]
CHANNEL_ID = os.environ["YT_CHANNEL_ID"]
HISTORY_FILE = "yt_history_chart.json"

resp = requests.get(
    "https://www.googleapis.com/youtube/v3/channels",
    params={"part": "statistics", "id": CHANNEL_ID, "key": API_KEY},
    timeout=10,
)
resp.raise_for_status()
subs = int(resp.json()["items"][0]["statistics"]["subscriberCount"])

today = datetime.date.today().isoformat()

with open(HISTORY_FILE) as f:
    data = json.load(f)

if data["dates"] and data["dates"][-1] == today:
    data["subscribers"][-1] = subs      # already ran today, overwrite
else:
    data["dates"].append(today)
    data["subscribers"].append(subs)

with open(HISTORY_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"{today}: {subs} subscribers")