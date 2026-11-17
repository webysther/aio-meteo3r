# aiometeo3r

Async Python client for the measurements of **Meteo 3R**, the weather app of
[Arpa Piemonte](https://www.arpa.piemonte.it): river levels, rain, temperature,
humidity, wind and snow of the 374 stations of the Piedmont network, every 30
minutes, with the alert thresholds of the 110 hydrometers.

- asyncio and aiohttp, fully typed (mypy strict), no other dependency;
- the files are on two hosts: when one fails, the other answers;
- each host is asked whether a file changed (`If-None-Match`,
  `If-Modified-Since`): an unchanged file is neither downloaded nor parsed
  again;
- times in UTC, also across the changes of summer time.

Meteo 3R has no documented API: aiometeo3r reads the files of the app, whose
format was measured (see [The data](#the-data)) and may change without notice.
For the documented sources of Arpa Piemonte, see
[aioarpapiemonte](https://github.com/webysther/aio-arpa-piemonte).

## Installation

```bash
pip install aiometeo3r
```

Python 3.13 or newer.

## Usage

The level of a river at a station, and how it compares with the thresholds:

```python
import asyncio

from aiometeo3r import Meteo3rClient, ROME_TZ


async def main() -> None:
    async with Meteo3rClient() as client:
        data = await client.get_station_data("188")  # Pray Sessera

    level = data.level
    if level is None:
        print(f"{data.station.name}: no level")
        return
    when = level.time.astimezone(ROME_TZ)
    print(f"{data.station.name} ({data.station.river}): {level.value} m at {when:%H:%M}")
    print(f"Status: {data.level_status}, thresholds: {data.station.thresholds}")


asyncio.run(main())
```

```text
Pray Sessera (SESSERA): 0.86 m at 03:00
Status: normal, thresholds: Thresholds(pre_alarm=2.3, guard=3.0, danger=3.8)
```

<details>
<summary>The stations, and several of them</summary>

```python
import asyncio

from aiometeo3r import Meteo3rClient, Quantity, SensorType


async def main() -> None:
    async with Meteo3rClient() as client:
        stations = await client.get_stations()
        hydrometers = [s for s in stations if s.has(SensorType.HYDROMETER)]
        print(f"{len(stations)} stations, {len(hydrometers)} hydrometers")
        sesia = [s for s in hydrometers if s.basin == "SESIA"]
        for station in sesia[:3]:
            data = await client.get_station_data(station.code)
            rain = data.latest(Quantity.RAIN_24H)
            print(f"{station.name}: level {data.level.value if data.level else '-'} m,"
                  f" rain 24 h {rain.value if rain else '-'} mm")


asyncio.run(main())
```

```text
374 stations, 110 hydrometers
Pray Sessera: level 0.86 m, rain 24 h 0.0 mm
Palestro Sesia: level 2.01 m, rain 24 h - mm
Passobreve Cervo: level 0.93 m, rain 24 h - mm
```

</details>

## Reference

### Client

`Meteo3rClient(session=None, *, request_timeout=10.0, user_agent=None, hosts=(Host.PRIMARY, Host.MIRROR))`

- Pass the `aiohttp.ClientSession` of your application: the client never
  closes it. Without one, use the client as an async context manager.
- `get_stations()`: the stations of Piedmont. Meteo 3R writes the list again
  every 30 minutes (280 KB): read it to choose a station, not at every update.
- `get_station_data(code)`: a station with its readings of the last 3 days.
  `code` is the code of the station in the network (`"188"`, `"001"`,
  `"S4059"`).
- `active_host`: the host of the latest answer.
- `user_agent` names your application in the requests. The default is
  `aiometeo3r/<version> (+<repository>)`; it is sent with each request, so it
  replaces the one of a shared session.

Polling: Meteo 3R writes the files every 30 minutes, about 30 to 45 minutes
after the measurement. Asking every 10 minutes is enough; most answers are
then a `304 Not Modified`, and the client returns the object it returned
before.

### Hosts

| `Host` | URL | Validators |
| --- | --- | --- |
| `PRIMARY` | `https://staticm3r.arpa.piemonte.it/meteo3r_production/` | `ETag`, `Last-Modified` |
| `MIRROR` | `https://www.meteo3r.it/dati/` | `Last-Modified` |

Each request asks the hosts in order and returns the first answer. A host that
failed (timeout, error status, an answer that is not the expected JSON) is
asked last for `HOST_RETRY_AFTER` (30 minutes).

### Models

- `Station`: code, name, coordinates, altitude, municipality, river, basin,
  hydrometric zero, `thresholds`, and its sensors (`sensor_types`, from the
  letters of `sensor_letters`).
- `StationData`: the `station`, its `series` (one `Series` per `Quantity` with
  readings), the `extremes` of today, and shortcuts: `latest(quantity)`,
  `series_of(quantity)`, `level`, `level_status`.
- `Reading`: `time` (UTC) and `value`.
- `Thresholds`: `pre_alarm`, `guard`, `danger` (any may be missing) and
  `status(level)`, a `LevelStatus`: `UNKNOWN` (no threshold), `NORMAL`,
  `PRE_ALARM`, `GUARD`, `DANGER`.

| `Quantity` | Key | Unit |
| --- | --- | --- |
| `LEVEL` | `I` | m above the hydrometric zero |
| `TEMPERATURE` | `T` | °C |
| `HUMIDITY` | `RH` | % |
| `RAIN_1H`, `RAIN_3H`, `RAIN_24H` | `P_1H`, `P_3H`, `P_24H` | mm, in the hours that end at the reading |
| `WIND_SPEED`, `GUST_SPEED` | `VV`, `VVR` | km/h |
| `WIND_DIRECTION`, `GUST_DIRECTION` | `DD`, `DDR` | degrees, where it comes from |
| `SNOW_DEPTH` | `HS` | cm |
| `DAILY_SNOW_DEPTH` | `HS_V` | cm, read at 08:00 Italian time |

Every enum value has a numeric `code` and `from_code()`; a released code never
changes.

### Errors

All errors derive from `Meteo3rError`:

- `Meteo3rConnectionError`: no host answered (network error, error status,
  timeout);
- `Meteo3rParseError`: a host answered something that is not the expected
  format: this is how a change of the app shows;
- `Meteo3rNotFoundError`: every host answered 404, Meteo 3R has no such station.

An invalid station code raises `ValueError` before any request.

## The data

Measured on the 374 stations on 2026-11-17:

- Every reading equals the [api_realtime](https://utility.arpa.piemonte.it/api_realtime/docs)
  of Arpa Piemonte at the same time, for every quantity (5,000 to 20,000
  readings each), which publishes them about 3 hours later.
- Level, temperature, humidity and snow equal the files of the website of
  Arpa, which state their units; wind and gust are 3.6 times those in m/s:
  Meteo 3R gives them in km/h.
- The times are Italian times without offset: aiometeo3r places them in UTC,
  the repeated hour when summer time ends included.
- A series the station does not measure is all nulls, and is left out; two
  stations had no readings at all.
- The extremes of `DATI_STAT` start again at midnight, Italian time.
- `I_STATO` was 0 with every level and 4 where the level is missing:
  aiometeo3r does not return it.
- The letters of `TIPO` come in any order; G, W, S and F also appear, without
  meaning for the series (`SensorType.UNKNOWN`).
- Meteo 3R also lists the stations of Liguria and Valle d'Aosta, which belong
  to other bodies under other terms: aiometeo3r leaves them out.

## Data source and attribution

The data is by **Arpa Piemonte**, under the
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
license ([legal notes](https://www.arpa.piemonte.it/note-legali)). Credit it as
`ATTRIBUTION` does: "Fonte: Arpa Piemonte - www.arpa.piemonte.it".

aiometeo3r is **not affiliated with or endorsed by Arpa Piemonte**. The data is
validated automatically only, and may be corrected later by Arpa Piemonte; it
comes without any guarantee of availability. Do not rely on it for safety: for
alerts, follow the official bulletins and the civil protection.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install --editable . --group dev   # pip >= 25.1
ruff format --check . && ruff check .
mypy
pytest --cov
```

The tests never reach Meteo 3R: a local HTTPS server answers for both hosts
(`tests/server.py`), with real files in `tests/fixtures/real`.

## License

MIT, see [LICENSE](https://github.com/webysther/aio-meteo3r/blob/main/LICENSE).
