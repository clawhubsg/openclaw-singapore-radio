---
name: openclaw-singapore-radio
description: Browse and play live Singapore internet radio streams. Use when the user wants a list of Singapore online radio stations, wants to search Singapore stations by name, language, or tag, needs stream URLs/codecs/bitrates, or wants a local player or browser opened for a specific Singapore radio stream.
---

# Openclaw Singapore Radio

List live Singapore internet radio stations and open a selected stream in a local player or browser.

## Workflow

1. Classify the request:
- List all Singapore stations
- Search for stations by name, language, or tag
- Play one specific station
2. Fetch live station data with the bundled helper. Do not invent station availability from memory.
3. If playback is requested, prefer an exact station name. If the name is ambiguous, list the candidates first and then play the selected one.

## List Or Search Stations

Run the helper:

```bash
python3 /home/dreamtcs/.codex/skills/openclaw-singapore-radio/scripts/singapore_radio.py list --all
```

Filter by station name:

```bash
python3 /home/dreamtcs/.codex/skills/openclaw-singapore-radio/scripts/singapore_radio.py list --query "cna"
```

Filter by language:

```bash
python3 /home/dreamtcs/.codex/skills/openclaw-singapore-radio/scripts/singapore_radio.py list --language english
```

Use `--format json` when you want machine-readable results before summarizing.

Rules:

1. Treat the helper output as live data from Radio Browser.
2. Use `--all` when the user explicitly asks for every Singapore station.
3. Use `--query`, `--language`, or `--tag` to narrow a long list before presenting it.
4. Mention that station directories and stream URLs can change over time.

## Play A Station

Play an exact station:

```bash
python3 /home/dreamtcs/.codex/skills/openclaw-singapore-radio/scripts/singapore_radio.py play "YES 933 Radio"
```

Preview the chosen stream URL without launching anything:

```bash
python3 /home/dreamtcs/.codex/skills/openclaw-singapore-radio/scripts/singapore_radio.py play "YES 933 Radio" --url-only
```

Rules:

1. Prefer exact station names for playback.
2. If multiple stations match, do not guess. Show the matching names and use `--index` only after confirming the intended one.
3. The helper tries local players in this order: `mpv`, `vlc`, `ffplay`, `mplayer`, `mpg123`, `xdg-open`, `open`.
4. If no player is available, return the stream URL clearly instead of failing silently.

## Response Style

Keep replies short and practical.

Preferred shape:

1. Best matching station or top matches first
2. Name, language, codec/bitrate, and stream URL when useful
3. One note that the list was checked live

## Resources

- [references/sources.md](references/sources.md): Live source details and playback notes
- `scripts/singapore_radio.py`: List, search, and play Singapore internet radio streams
