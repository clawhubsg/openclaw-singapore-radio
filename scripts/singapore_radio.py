#!/usr/bin/env python3
"""List and play live Singapore internet radio streams."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


API_URL = "https://de1.api.radio-browser.info/json/stations/search"
COUNTRY_CODE = "SG"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
USER_AGENT = "openclaw-singapore-radio/1.0"
PLAYER_ORDER = ("mpv", "vlc", "ffplay", "mplayer", "mpg123", "xdg-open", "open")
DEFAULT_CHAT_LIMIT = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List and play live Singapore internet radio streams."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List Singapore stations.")
    add_filter_arguments(list_parser)
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum stations to show unless --all is set. Default: 20.",
    )
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="Show all matching stations.",
    )
    list_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    list_parser.add_argument(
        "--chat",
        action="store_true",
        help="Render a Telegram/WhatsApp-friendly list reply.",
    )
    list_parser.add_argument(
        "--web-base-url",
        help="Base HTTPS player URL, for example https://example.com/radio.",
    )

    play_parser = subparsers.add_parser("play", help="Play one Singapore station.")
    play_parser.add_argument("station", help="Exact or partial station name.")
    add_filter_arguments(play_parser)
    play_parser.add_argument(
        "--index",
        type=int,
        help="Choose a 1-based station index from the filtered match list when multiple match.",
    )
    play_parser.add_argument(
        "--player",
        help="Preferred player command, for example mpv or vlc.",
    )
    play_parser.add_argument(
        "--url-only",
        action="store_true",
        help="Print the resolved stream URL without launching a player.",
    )
    play_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the chosen station and player without launching playback.",
    )
    play_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    play_parser.add_argument(
        "--chat",
        action="store_true",
        help="Render a Telegram/WhatsApp-friendly station reply.",
    )
    play_parser.add_argument(
        "--web-base-url",
        help="Base HTTPS player URL, for example https://example.com/radio.",
    )

    return parser.parse_args()


def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", help="Filter by station name, language, or tags.")
    parser.add_argument("--language", help="Filter by language.")
    parser.add_argument("--tag", help="Filter by tag.")


def fetch_json(url: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
                if not isinstance(payload, list):
                    raise RuntimeError("Unexpected Radio Browser response format.")
                return payload
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Request failed for {url}: {exc}") from exc
            time.sleep(0.5 * attempt)

    raise RuntimeError(f"Unreachable fetch retry loop for {url}")


def normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def build_station_url() -> str:
    query = urllib.parse.urlencode(
        {
            "countrycode": COUNTRY_CODE,
            "hidebroken": "true",
            "limit": 500,
            "order": "votes",
            "reverse": "true",
        }
    )
    return f"{API_URL}?{query}"


def serialize_station(raw: dict[str, Any]) -> dict[str, Any]:
    resolved_url = (raw.get("url_resolved") or raw.get("url") or "").strip()
    return {
        "name": (raw.get("name") or "").strip() or "Unnamed station",
        "stationuuid": raw.get("stationuuid"),
        "language": (raw.get("language") or "").strip(),
        "languagecodes": (raw.get("languagecodes") or "").strip(),
        "tags": (raw.get("tags") or "").strip(),
        "codec": (raw.get("codec") or "").strip() or "unknown",
        "bitrate": int(raw.get("bitrate") or 0),
        "votes": int(raw.get("votes") or 0),
        "homepage": (raw.get("homepage") or "").strip(),
        "url": resolved_url,
    }


def load_stations() -> list[dict[str, Any]]:
    stations = []
    seen: set[tuple[str, str]] = set()

    for raw in fetch_json(build_station_url()):
        station = serialize_station(raw)
        if not station["url"]:
            continue
        key = (normalize(station["name"]), station["url"])
        if key in seen:
            continue
        seen.add(key)
        stations.append(station)

    stations.sort(
        key=lambda station: (
            -station["votes"],
            normalize(station["name"]),
        )
    )
    return stations


def filter_stations(
    stations: list[dict[str, Any]],
    query: str | None,
    language: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    query_text = normalize(query)
    language_text = normalize(language)
    tag_text = normalize(tag)
    filtered = []

    for station in stations:
        blob = " ".join(
            [
                station["name"],
                station["language"],
                station["languagecodes"],
                station["tags"],
            ]
        ).lower()
        if query_text and query_text not in blob:
            continue
        if language_text:
            language_blob = f"{station['language']} {station['languagecodes']}".lower()
            if language_text not in language_blob:
                continue
        if tag_text and tag_text not in station["tags"].lower():
            continue
        filtered.append(station)

    return filtered


def render_station_line(index: int, station: dict[str, Any]) -> str:
    language = station["language"] or station["languagecodes"] or "unknown language"
    bitrate = f"{station['bitrate']} kbps" if station["bitrate"] else "bitrate unknown"
    return (
        f"{index}. {station['name']} | {language} | {station['codec']} | {bitrate}\n"
        f"   {station['url']}"
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "station"


def resolve_web_base_url(explicit_base_url: str | None) -> str | None:
    base_url = explicit_base_url or os.environ.get("OPENCLAW_RADIO_PLAYER_BASE_URL")
    if not base_url:
        return None
    return base_url.rstrip("/")


def build_web_player_url(base_url: str | None, station: dict[str, Any]) -> str | None:
    if not base_url:
        return None
    encoded_stream = urllib.parse.quote(station["url"], safe="")
    return f"{base_url}/{slugify(station['name'])}?stream={encoded_stream}"


def station_title(station: dict[str, Any]) -> str:
    language = station["language"] or station["languagecodes"] or "unknown language"
    bitrate = f"{station['bitrate']} kbps" if station["bitrate"] else "bitrate unknown"
    return f"{station['name']} | {language} | {station['codec']} | {bitrate}"


def render_chat_list(
    stations: list[dict[str, Any]],
    web_base_url: str | None,
    query: str | None,
    language: str | None,
    tag: str | None,
) -> str:
    heading = "Singapore radio"
    filters = [value for value in (query, language, tag) if value]
    if filters:
        heading = f"{heading} ({', '.join(filters)})"

    lines = [heading]
    for index, station in enumerate(stations, start=1):
        lines.append(f"{index}. {station['name']}")

    lines.append("")
    lines.append("Reply:")
    lines.append("- play 1")
    lines.append("- search tamil")
    if len(stations) >= DEFAULT_CHAT_LIMIT:
        lines.append("- more")

    if web_base_url:
        lines.append("")
        lines.append("Open now:")
        for index, station in enumerate(stations, start=1):
            player_url = build_web_player_url(web_base_url, station)
            lines.append(f"{index}. {player_url}")

    lines.append("")
    lines.append("Checked live from the Singapore station directory.")
    return "\n".join(lines)


def render_chat_station(station: dict[str, Any], web_base_url: str | None) -> str:
    lines = [station["name"], station_title(station)]
    player_url = build_web_player_url(web_base_url, station)
    if player_url:
        lines.append(f"Open player: {player_url}")
    lines.append(f"Direct stream: {station['url']}")
    lines.append("Use the player link on Android, iPhone, or desktop browser.")
    return "\n".join(lines)


def command_for_player(player: str, url: str) -> list[str]:
    if player == "ffplay":
        return [player, "-loglevel", "warning", url]
    return [player, url]


def pick_player(preferred_player: str | None) -> str | None:
    if preferred_player:
        if shutil.which(preferred_player):
            return preferred_player
        raise SystemExit(f"Requested player '{preferred_player}' was not found in PATH.")

    for player in PLAYER_ORDER:
        if shutil.which(player):
            return player
    return None


def choose_station(
    stations: list[dict[str, Any]],
    station_query: str,
    index: int | None,
) -> dict[str, Any]:
    exact_matches = [
        station for station in stations if normalize(station["name"]) == normalize(station_query)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    if len(stations) == 1:
        return stations[0]

    if index is not None:
        if index < 1 or index > len(stations):
            raise SystemExit(f"--index must be between 1 and {len(stations)}.")
        return stations[index - 1]

    if exact_matches:
        names = "\n".join(render_station_line(i + 1, station) for i, station in enumerate(exact_matches))
        raise SystemExit(
            "Multiple exact station names matched. Re-run with --index.\n"
            f"{names}"
        )

    suggestions = "\n".join(
        render_station_line(i + 1, station) for i, station in enumerate(stations[:10])
    )
    raise SystemExit(
        "Multiple stations matched. Re-run with --index or a more exact name.\n"
        f"{suggestions}"
    )


def launch_player(player: str, url: str) -> int:
    command = command_for_player(player, url)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process.pid


def handle_list(args: argparse.Namespace) -> int:
    stations = filter_stations(load_stations(), args.query, args.language, args.tag)
    if not args.all:
        stations = stations[: max(args.limit, 0)]

    if args.format == "json":
        print(json.dumps({"count": len(stations), "stations": stations}, indent=2))
        return 0

    if not stations:
        print("No matching Singapore stations found.")
        return 0

    if args.chat:
        print(
            render_chat_list(
                stations,
                resolve_web_base_url(args.web_base_url),
                args.query,
                args.language,
                args.tag,
            )
        )
        return 0

    print(f"Singapore stations: {len(stations)}")
    for index, station in enumerate(stations, start=1):
        print(render_station_line(index, station))
    return 0


def handle_play(args: argparse.Namespace) -> int:
    query = args.query or args.station
    matches = filter_stations(load_stations(), query, args.language, args.tag)
    if not matches:
        print("No matching Singapore stations found.", file=sys.stderr)
        return 1

    station = choose_station(matches, args.station, args.index)
    result: dict[str, Any] = {"station": station}
    web_base_url = resolve_web_base_url(args.web_base_url)

    if args.url_only:
        result["mode"] = "url-only"
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(station["url"])
        return 0

    if args.chat:
        result["mode"] = "chat"
        if web_base_url:
            result["player_url"] = build_web_player_url(web_base_url, station)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(render_chat_station(station, web_base_url))
        return 0

    player = pick_player(args.player)
    if not player:
        result["mode"] = "no-player"
        result["message"] = "No local player found. Use the stream URL directly."
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print("No local player found. Use this stream URL:")
            print(station["url"])
        return 0

    result["player"] = player
    if args.dry_run:
        result["mode"] = "dry-run"
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"Would play: {station['name']}")
            print(f"Player: {player}")
            print(f"Stream: {station['url']}")
        return 0

    pid = launch_player(player, station["url"])
    result["mode"] = "playing"
    result["pid"] = pid

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Playing: {station['name']}")
        print(f"Player: {player}")
        print(f"PID: {pid}")
        print(f"Stream: {station['url']}")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "list":
        return handle_list(args)
    if args.command == "play":
        return handle_play(args)
    raise RuntimeError(f"Unsupported command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
