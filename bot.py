import os
import urllib.parse
import urllib.request
import json

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": CHAT_ID,
    "text": "ON24 News Monitor ishga tushdi! ✅"
}).encode()

request = urllib.request.Request(url, data=data)

with urllib.request.urlopen(request) as response:
    result = json.loads(response.read().decode())
    print(result)
