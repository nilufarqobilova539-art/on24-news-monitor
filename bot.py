
import os
import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

FEEDS = {
    "Kun.uz": "https://kun.uz/news/rss",
    "Gazeta.uz": "https://www.gazeta.uz/uz/rss/",
    "Nuz.uz": "https://nuz.uz/feed",
    "UzNews": "https://uznews.uz/rss",
}

def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()

def get_value(element, name):
    for child in element:
        if child.tag.split("}")[-1].lower() == name.lower():
            return child.text or child.attrib.get("href", "")
    return ""

def parse_date(value):
    if not value:
        return None
    try:
        date = parsedate_to_datetime(value)
    except Exception:
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)

def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": "false"
    }).encode()
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=20) as response:
        print(response.read().decode())

def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)
    news = []

    for source, feed_url in FEEDS.items():
        try:
            request = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "ON24NewsMonitor/1.0"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                root = ET.fromstring(response.read())

            entries = [
                element for element in root.iter()
                if element.tag.split("}")[-1].lower() in ("item", "entry")
            ]

            for entry in entries:
                title = clean(get_value(entry, "title"))
                link = get_value(entry, "link")
                if link and not link.startswith("http"):
                    link = ""

                date_text = (
                    get_value(entry, "pubDate")
                    or get_value(entry, "published")
                    or get_value(entry, "updated")
                )
                published = parse_date(date_text)

                if title and link and published and cutoff <= published <= now + timedelta(minutes=5):
                    news.append((published, source, title, link))

            print(f"{source}: tekshirildi")

        except Exception as error:
            print(f"{source}: xatolik - {error}")

    news.sort(reverse=True)

    if not news:
        send("ON24 News Monitor: oxirgi 35 daqiqada RSS manbalarida yangi xabar topilmadi.")
        return

    for published, source, title, link in news[:15]:
        local_time = published.astimezone(
            timezone(timedelta(hours=5))
        ).strftime("%H:%M")
        message = (
            f"📰 {title}\n\n"
            f"Manba: {source}\n"
            f"E'lon qilingan vaqt: {local_time}\n"
            f"🔗 {link}\n\n"
            f"⚠️ Tahririyat tekshiruvidan o'tkazilsin."
        )
        send(message)

    print(f"Yuborilgan xabarlar: {min(len(news), 15)}")

if __name__ == "__main__":
    main()
