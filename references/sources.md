# Sources

## Live station directory

- Primary source: Radio Browser
- Website: `https://www.radio-browser.info/`
- API pattern used by the helper:

```text
https://de1.api.radio-browser.info/json/stations/search?countrycode=SG&hidebroken=true&limit=500&order=votes&reverse=true
```

## Notes

- Radio Browser is a live community-maintained station directory, so station names, codecs, and stream URLs can change.
- The helper filters for `countrycode=SG`, hides known broken streams, and deduplicates repeated station entries before presenting results.
- Some results may be TV audio or repeated brand entries that still point at valid Singapore streams. Treat the live directory as the source of truth for what is currently available.

## Playback fallback

The helper tries to launch a local player or opener in this order:

1. `mpv`
2. `vlc`
3. `ffplay`
4. `mplayer`
5. `mpg123`
6. `xdg-open`
7. `open`

If none are available, use `--url-only` and return the stream URL.
