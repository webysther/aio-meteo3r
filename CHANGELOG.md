# Changelog

All notable changes to aiometeo3r are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html): before 1.0, a
minor version may change the API.

## [0.1.0] - 2026-11-17

First release.

### Added

- `Meteo3rClient`: the stations of Piedmont (`get_stations()`) and the readings
  of a station of the last 3 days (`get_station_data()`), from the two hosts of
  Meteo 3R, the second answering when the first fails, with conditional
  requests.
- Models of the stations, the readings in UTC, the thresholds of the
  hydrometers with `LevelStatus`, and the extremes of today.

[0.1.0]: https://github.com/webysther/aio-meteo3r/releases/tag/v0.1.0
