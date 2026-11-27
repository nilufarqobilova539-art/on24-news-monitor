import os
import urllib.parse
import urllib.request
import urllib.error

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": CHAT_ID,
    "text": "ON24 News Monitor ishga tushdi! ✅"
}).encode()

request = urllib.request.Request(url, data=data)

try:
    with urllib.request.urlopen(request) as response:
        print(response.read().decode())
except urllib.error.HTTPError as error:
    print(error.read().decode())
    raise
