# Meteo 3R data: what was measured

The files of Meteo 3R behind aiometeo3r, as studied for the
[ARPA Piemonte](https://github.com/webysther/ha-arpa-piemonte) integration.

Measured on 2026-11-16 and 17. The numbers are measurements of those days:
measure again, politely, before relying on one. Anything not confirmed is
marked **Unverified**.

The other sources of Arpa Piemonte are documented in aioarpapiemonte:
[the station files of the website and the api_realtime](https://github.com/webysther/aio-arpa-piemonte/blob/main/docs/arpa-data.md)
and [the natural-risk products](https://github.com/webysther/aio-arpa-piemonte/blob/main/docs/arpa-risk-products.md).
The decisions and the roadmap of the integration are in
[its research notes](https://github.com/webysther/ha-arpa-piemonte/blob/main/docs/research.md).

## Files and hosts

- **Registry:** `misureAnagrafica.json`, 280,537 B, 675 records (PIE 374,
  LIG 209, VDA 92). Only PIE is Arpa Piemonte; LIG and VDA belong to other
  bodies, under other terms.
- **Station file:** `misure/misure_PIE_{code}.json`, 14,475–15,438 B raw
  (571 B when empty), 1,660–2,140 B gzip.
- **Hosts:**
  - primary `https://staticm3r.arpa.piemonte.it/meteo3r_production/` (weak
    ETag + Last-Modified);
  - mirror `https://www.meteo3r.it/dati/` (Last-Modified only).
- **Cadence:** a new file every 30 min, about 30–45 min after the
  measurement.
- **Cost:** the integration asks every 10 min, so per station and day about 48
  downloads plus 96 `304` answers (~100 KB/day gzip).
- **Agreement:** equal to the api_realtime for every quantity (74/74 matching
  times on Pray), and to the website for level and temperature (77/77).

## Time and window

- **Time zone:** Italian time without offset; the parser converts it to UTC
  and handles the repeated hour at the end of summer time.
- **Window:** starts at 23:00 Italian time four calendar days back and grows
  through the day, from about 3 d 1 h to 4 d (147–194 slots of 30 min).
  - Fixture written at 03:00 local: 153 slots, 2026-11-13 22:00Z → 11-17
    02:00Z.
  - Live sample at 05:30 local: 158 slots.
  - **Unverified:** what happens at midnight.
- **Missing values:**
  - Null readings are dropped, so a gap is a step longer than 30 min.
  - An all-null quantity is left out.
  - The newest slot can be all null (station 133 at 05:30 local).

## Quantities in a station file

| Quantity (key) | Step | Points | Notes |
| --- | --- | --- | --- |
| LEVEL (`I`) | 30 min | 188: 153, no gaps | m |
| TEMPERATURE (`T`) | 30 min | 153–157 | °C |
| HUMIDITY (`RH`) | 30 min | 153–157 | % |
| RAIN_1H (`P_1H`) | 30 min | 153 | rolling 60-min total sampled every 30 min, so neighbouring samples overlap. The :00 readings are independent hourly totals: 3 of them sum to `P_3H` (149/149) and 24 to `P_24H` (107/107). Cumulative = running sum of the :00 readings. |
| RAIN_3H / RAIN_24H | 30 min | 153 | rolling totals; no rain since midnight, no 10-min rain |
| WIND_SPEED / WIND_DIRECTION (`VV`/`DD`) | 30 min with gaps | 001: 131 / 130 of 153 | km/h, ° |
| GUST_SPEED / GUST_DIRECTION (`VVR`/`DDR`) | 60 min, only at :00 | 001: 77 | the :30 slots are always null |
| SNOW_DEPTH (`HS`) | 30 min, many gaps | 001: 64/153; 133: 134/157 | negative values (−5.0) near zero; note "Dati neve annullati automaticamente nel periodo estivo" |
| DAILY_SNOW_DEPTH (`HS_V`) | 1 day, 08:00 local | 7 days | own times `DATA_ORA_HS_V` |

## Daily extremes

- **Contents:** `DATI_STAT` gives today's extremes (the Italian day, reset at
  midnight Rome time) for level, temperature, humidity, gust and snow depth,
  each with its time. There are none for rain or wind speed.
- **Example (Pray):** level max 0.88 (23:00Z), min 0.86 (00:30Z).
- **Not used yet** by the integration.

## Thresholds

- **Fields:** `SOGLIA_PRE`, `SOGLIA_GUARDIA` and `SOGLIA_PERICOLO`, in the
  registry and in the station file.
- **Coverage:** of 110 hydrometers, 84 have all three, 22 have some and 4 have
  none. The values agree with `pie_anag` for every station.
- **Pray:** 2.3 / 3.0 / 3.8 m, hydrometric zero 400.7 m.

## Registry facts (PIE)

- **Rivers:**
  - 110 stations have a river (exactly the 110 with `I`) and 264 have none
    (`CORSO_ACQUA` is `"-"`);
  - 62 distinct rivers and lakes, among them `LAGO MAGGIORE`, `LAGO D ORTA`,
    `LAGO DI CANDIA` and `LAGO DI VIVERONE`;
  - most common: PO 10, TANARO 9, then 3 each for SESIA, CERVO, STURA DI
    DEMONTE, DORA RIPARIA, STURA DI LANZO, VARAITA, MAIRA and TOCE;
  - no municipality has two hydrometers on the same river.
- **Municipalities:**
  - 278 distinct, none empty;
  - stations per municipality: {1: 214, 2: 42, 3: 17, 4: 3, 5: 1, 8: 1}
    (Torino 8, Bardonecchia 5, Vinadio, Sestriere and Oulx 4);
  - 134 stations are named as their municipality.
- **Provinces:** TO 122, CN 104, VB 43, AL 43, VC 19, AT 17, BI 14, NO 11,
  PV 1.
- **Text:**
  - no accented characters: an accent is written as an apostrophe (Mondovi',
    Carru', Viu', Pra' Catinat, Sauze D'Oulx, Castell'Alfero);
  - hyphens appear (Pont-Canavese, Ormea - Stanti);
  - names and municipalities are in title case, rivers in upper case.
- **Codes:** not all numeric (`S4062` Acceglio Collet).
- **Sensor letters (stations):** P 286, T 277, H 146, I 110, V 91, N 79,
  R 66, B 47, G 29, W 14, F 3, S 1.
  - **Unverified:** the meaning of G, W, F and S.
- **Unverified:** whether the files of stations with B (barometer) or R
  (radiometer) carry pressure or radiation series. They would land in
  `other_keys`; no fixture has such a station.

## Still unverified

- What the window of a station file does at midnight Italian time.
- Whether the files of stations with B (barometer) or R (radiometer) carry
  pressure or radiation series; they would land in `other_keys`. The Arpa
  website publishes them as the hourly files `baro` and `radd`.
- The meaning of the sensor letters G, W, F and S.
- How `HS_V` relates to the validated snow of the api_realtime (`pie_neve`)
  and to the website files `nivo_v`: all three are a daily snow depth.
