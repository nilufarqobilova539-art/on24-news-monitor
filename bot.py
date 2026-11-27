
import os
import re
import html
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]

LOCAL_TZ = timezone(timedelta(hours=5))

FEEDS = {
    "Kun.uz": "https://kun.uz/news/rss",
    "Gazeta.uz": "https://www.gazeta.uz/ru/rss/",
    "Nuz.uz": "https://nuz.uz/feed",
    "UzNews": "https://uznews.uz/rss",
    "UzA": "https://uza.uz/uz/rss",
    "Podrobno.uz": "https://podrobno.uz/rss/",
    "Spot.uz": "https://www.spot.uz/ru/rss/",
    "UzNet Press UZ": "https://uznet.press/rss/today_uz.xml",
    "UzNet Press RU": "https://uznet.press/rss/today_ru.xml",
}

IMPORTANT_WORDS = [
    "halok", "vafot", "o'ldir", "öldir", "qotillik",
    "zo'ravon", "zöravon", "portlash", "yong'in",
    "avariya", "falokat", "qidiruv", "hibsga",
    "firibgarlik", "sud", "jazo", "hodisa",
    "favqulodda", "taqiqlan", "cheklov",
    "narx osh", "qimmatlash", "dollar",
    "qaror", "qonun", "iste'fo", "tayinlandi",
    "namoyish", "urush", "hujum", "skandal",
    "смерть", "погиб", "убийств", "насили",
    "взрыв", "пожар", "авари", "задержан",
    "арест", "мошеннич", "суд", "запрет",
    "ограничен", "повышен цен", "скандал",
    "срочно", "чп", "назначен", "отставка",
]

def github_request(path, payload=None):
    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/contents/{path}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ON24-News-Monitor",
    }

    if payload is None:
        request = urllib.request.Request(url, headers=headers)
    else:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                **headers,
                "Content-Type": "application/json",
            },
            method="PUT",
        )

    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())

def read_state(filename):
    try:
        data = github_request(filename)
        content = base64.b64decode(data["content"]).decode()
        return json.loads(content), data["sha"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}, None
        raise

def write_state(filename, state, sha, message):
    content = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    payload = {
        "message": message,
        "content": base64.b64encode(
            content.encode()
        ).decode(),
    }

    if sha:
        payload["sha"] = sha

    github_request(filename, payload)

def should_run():
    now = datetime.now(LOCAL_TZ)

    if not (8 <= now.hour < 23):
        print("Hozir belgilangan ish vaqti emas.")
        return False

    state, sha = read_state("schedule_state.json")

    last_run_text = state.get("last_run")

    if last_run_text:
        last_run = datetime.fromisoformat(last_run_text)

        if now - last_run < timedelta(minutes=25):
            print("25 daqiqa hali o'tmadi. Keyingi tekshiruv kutiladi.")
            return False

    state["last_run"] = now.isoformat()

    write_state(
        "schedule_state.json",
        state,
        sha,
        "Update ON24 schedule"
    )

    print("Yangiliklarni tekshirish boshlandi.")
    return True

def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(
        re.sub(r"\s+", " ", text)
    ).strip()

def get_value(element, name):
    for child in element:
        if child.tag.split("}")[-1].lower() == name.lower():
            return child.text or child.attrib.get("href", "")
    return ""

def get_link(entry):
    link = get_value(entry, "link")

    if link.startswith("http"):
        return link

    for child in entry:
        if child.tag.split("}")[-1].lower() == "link":
            href = child.attrib.get("href", "")
            if href.startswith("http"):
                return href

    return ""

def parse_date(value):
    if not value:
        return None

    try:
        date = parsedate_to_datetime(value)
    except Exception:
        try:
            date = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except Exception:
            return None

    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    return date.astimezone(timezone.utc)

def score_news(title, summary):
    text = (title + " " + summary).lower()
    score = 0

    for word in IMPORTANT_WORDS:
        if word in text:
            score += 3

    return score

def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": "false",
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=20) as response:
        print(response.read().decode())

def main():
    if not should_run():
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)

    sent_state, sent_sha = read_state("sent_items.json")
    sent_items = set(sent_state.get("items", []))

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
                if element.tag.split("}")[-1].lower()
                in ("item", "entry")
            ]

            for entry in entries:
                title = clean(get_value(entry, "title"))
                link = get_link(entry)

                summary = clean(
                    get_value(entry, "description")
                    or get_value(entry, "summary")
                )

                date_text = (
                    get_value(entry, "pubDate")
                    or get_value(entry, "published")
                    or get_value(entry, "updated")
                )

                published = parse_date(date_text)

                if not title or not link or not published:
                    continue

                if not (cutoff <= published <= now + timedelta(minutes=5)):
                    continue

                item_id = link.split("?")[0].rstrip("/")

                if item_id in sent_items:
                    continue

                news.append({
                    "date": published,
                    "source": source,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "id": item_id,
                    "score": score_news(title, summary),
                })

            print(f"{source}: tekshirildi")

        except Exception as error:
            print(f"{source}: xatolik - {error}")

    news.sort(
        key=lambda item: (item["score"], item["date"]),
        reverse=True
    )

    if not news:
        print("Yangi xabar topilmadi.")
        return

    for item in news[:10]:
        local_time = item["date"].astimezone(
            LOCAL_TZ
        ).strftime("%H:%M")

        summary = item["summary"][:450]

        message = (
            f"📰 {item['title']}\n\n"
            f"{summary}\n\n"
            f"Manba: {item['source']}\n"
            f"E'lon vaqti: {local_time}\n"
            f"🔗 {item['link']}\n\n"
            f"⚠️ Nashrdan oldin tekshiring."
        )

        send(message)
        sent_items.add(item["id"])

    write_state(
        "sent_items.json",
        {"items": sorted(sent_items)[-1000:]},
        sent_sha,
        "Update sent news history"
    )

    print(f"Yuborilgan xabarlar: {min(len(news), 10)}")

if __name__ == "__main__":
    main()
