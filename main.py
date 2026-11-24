import re
import datetime as dt
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests
import discord

from google.colab import userdata
await client.start(userdata.get("DISCORD_TOKEN"))

MY_NAME = "Vanesa"
PLACE = "Rovaniemi"

FMI_URL = "https://opendata.fmi.fi/wfs"
NS = {"BsWfs": "http://xml.fmi.fi/schema/wfs/2.0"}


def get_latest_weather(place=PLACE):
    """Return (temperature °C, wind m/s, observation time UTC) from FMI open data."""
    start = (dt.datetime.utcnow() - dt.timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "getFeature",
        "storedquery_id": "fmi::observations::weather::simple",
        "place": place,
        "parameters": "t2m,ws_10min",
        "starttime": start,
    }
    r = requests.get(FMI_URL, params=params, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    latest = {}  # parameter -> (time, value)
    for el in root.iter("{http://xml.fmi.fi/schema/wfs/2.0}BsWfsElement"):
        name = el.find("BsWfs:ParameterName", NS).text
        value = el.find("BsWfs:ParameterValue", NS).text
        time = el.find("BsWfs:Time", NS).text
        if value is None or value == "NaN":
            continue
        if name not in latest or time > latest[name][0]:
            latest[name] = (time, float(value))

    if "t2m" not in latest:
        raise ValueError("No temperature observation found")
    time, temp = latest["t2m"]
    wind = latest.get("ws_10min", (None, None))[1]
    return temp, wind, time


def memegen_text(text):
    """Escape text for memegen.link URLs."""
    text = (
        text.replace("-", "--")
        .replace("_", "__")
        .replace(" ", "_")
        .replace("?", "~q")
        .replace("/", "~s")
        .replace("#", "~h")
        .replace("%", "~p")
        .replace('"', "''")
    )
    return quote(text, safe="_-~'")


def pick_meme(temp):
    """Choose a meme template + captions based on temperature."""
    t = f"{temp:.1f}°C"
    if temp <= -20:
        tpl, top, bottom = "fine", f"{t} in Rovaniemi", "This is fine"
    elif temp <= -10:
        tpl, top, bottom = "buzz", "Snow", "Snow everywhere"
    elif temp < 0:
        tpl, top, bottom = (
            "rollsafe",
            f"It's only {t}",
            "Can't be cold if you stay inside",
        )
    elif temp < 10:
        tpl, top, bottom = "drake", f"{t} outside", "Hot chocolate inside"
    elif temp < 20:
        tpl, top, bottom = "doge", f"Such {t}", "Very spring. Wow"
    else:
        tpl, top, bottom = "success", f"{t} in Lapland", "Summer actually happened"
    return f"https://api.memegen.link/images/{tpl}/{memegen_text(top)}/{memegen_text(bottom)}.png"


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
name_pattern = re.compile(rf"\b{re.escape(MY_NAME)}\b", re.IGNORECASE)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not name_pattern.search(message.content):
        return
    try:
        temp, wind, time = get_latest_weather()
        obs_time = dt.datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ") + dt.timedelta(
            hours=2
        )
        text = f"Hi {MY_NAME}! Latest observation in {PLACE} ({obs_time:%d.%m.%Y %H:%M} Finnish time): **{temp:.1f} °C**"
        if wind is not None:
            text += f", wind {wind:.1f} m/s"
        embed = discord.Embed(description=text)
        embed.set_image(url=pick_meme(temp))
        embed.set_footer(text="Data: Finnish Meteorological Institute open data")
        await message.channel.send(embed=embed)
    except Exception as e:
        await message.channel.send(f"Sorry {MY_NAME}, couldn't get the weather: {e}")
