# AGENTS.md: aiometeo3r

Guidance for AI coding agents and contributors working on this repository.
`CLAUDE.md` imports this file.

aiometeo3r is an async Python client (asyncio, aiohttp) for the measurements
of Meteo 3R, the weather app of Arpa Piemonte: the stations of the Piedmont
network and their readings every 30 minutes. It is fully typed, has no Home
Assistant dependency and is published to PyPI.

Its main user is the Home Assistant integration Arpa Piemonte
(`arpa_piemonte`), which pins an exact version and falls back to the official
sources of [aioarpapiemonte](https://github.com/webysther/aio-arpa-piemonte)
when Meteo 3R fails. Meteo 3R parsing and HTTP fixes belong here; Home
Assistant code and the fallback belong in the integration.

## Ground rules

- **Do not commit, amend, push, tag, publish or move branches** (`reset`,
  `branch -f`, `rebase`). Leave every change uncommitted in the working tree;
  the maintainer reviews and commits it. Read-only git commands are fine.
- Ask before anything that leaves the machine: releases, PRs, issues,
  comments.
- Reply in the language the person writes in. Code, comments, docstrings,
  docs, the changelog and commit messages are in English.
- Check instead of guessing: Meteo 3R has no documented format. Answer data
  questions by measuring the live files with a throwaway script outside the
  repository, politely (a few requests, with pauses), and write the
  measurement in the docstring of the constant it sets.

## Layout

```text
src/aiometeo3r/
  client.py      Meteo3rClient: get_stations(), get_station_data(); the two
                 hosts in order, conditional requests
  _http.py       ConditionalCache: the latest answer of each URL, with its
                 validators (each host has its own)
  parsers.py     pure parsing of the decoded JSON, without I/O; Italian times
                 to UTC (rome_times_to_utc)
  models.py      frozen dataclasses and enums; exceptions.py
  urls.py        Host, REGISTRY_PATH, station_path(); const.py
tests/           pytest; tests/server.py is a local HTTPS server standing in
                 for both hosts, answering 304 to conditional requests
docs/            meteo3r-data.md: the study of the files of Meteo 3R
```

The public API is what `aiometeo3r/__init__.py` exports in `__all__`, plus the
documented modules `parsers` and `urls`.

## Checks

```bash
python -m venv .venv && . .venv/bin/activate
pip install --editable . --group dev   # pip >= 25.1
ruff format --check . && ruff check .  # every rule ("ALL"), see pyproject.toml
mypy                                   # strict, src and tests
pytest --cov
npx prettier --check .                 # the YAML of the workflows
```

CI runs the same on Python 3.13 and 3.14. Warnings are errors in pytest. The
coverage gate is 95% with branches; keep it at 100%.

## Tests

- Never reach Meteo 3R: `tests/server.py` answers for both hosts over HTTPS
  (certificates from trustme).
- `tests/fixtures/real` holds unmodified files of Meteo 3R that guard the
  format: never edit them. Hand-made data is built in the tests
  (`synthetic()` in `tests/test_parsers.py`).
- Never depend on the current date or time zone of the machine.

## Meteo 3R data

Read [docs/meteo3r-data.md](docs/meteo3r-data.md) before researching the
source again: the files, hosts, series, quantities and registry facts measured
on 2026-11-16 and 17, and what is still unverified. Add what you measure to
it, with the date.

Facts that are easy to get wrong (measured on 2026-11-17, see the README):

- The times (`DATA_ORA`, `*_DATA`) are Italian times without offset. The hour
  that repeats when summer time ends is placed by order; a time that does not
  exist when it starts is dropped. Readings are kept in UTC.
- Wind and gust are in km/h; the official files of the Arpa website give them
  in m/s.
- A series the station does not measure is a list of nulls; `DATI` can be
  empty. `DATA_ORA_HS_V` and `HS_V` are a daily snow depth with its own times.
- Thresholds and hydrometric zero are texts, `""` when missing.
- The extremes of `DATI_STAT` start again at midnight, Italian time.
- The two hosts send different `Last-Modified` for the same file: each host is
  asked with its own validators.
- Only the network `PIE`: the stations of Liguria and Valle d'Aosta belong to
  other bodies, under terms not confirmed.

## Versioning and releases

- Semantic Versioning: before 1.0 a minor version may change the API.
- To prepare a release, add a `## [X.Y.Z] - Unreleased` section to
  `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)),
  written for the users of the library, with its compare link at the end of
  the file, and set `__version__` in `src/aiometeo3r/__init__.py` to `X.Y.Z`.
- The maintainer commits and runs `./publish.sh X.Y.Z [--dry-run]`: it dates
  the section, creates the GitHub release, and the release workflow tests,
  builds and publishes to PyPI (trusted publishing).

## Code style

- Readable, descriptive code over clever code: descriptive names, typed models
  and enums instead of raw dicts, small focused helpers, docstrings that say
  what and why.
- No magic numbers: a `Final` constant whose docstring says where its value
  comes from (see `HOST_RETRY_AFTER`).
- Parsing stays pure and I/O stays in the client.
- Every value of an enum has a numeric `code`; a released code never changes
  and is never reused.
- mypy strict, ruff with every rule. A `# noqa` or `# type: ignore[code]`
  needs a reason.
- Comments explain why, not what.
