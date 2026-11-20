"""Kurzfristige Staatsanleihe-Renditen (2 Jahre) direkt von Notenbanken und Ministerien.

Quelle je Währung (FRED führt außer den USA keine aktuellen kurzen Renditen mehr):
  EUR  EZB-Zinsstrukturkurve Euroraum, 2 Jahre          (data-api.ecb.europa.eu)
  CAD  Bank of Canada, Benchmark-Anleihe 2 Jahre         (www.bankofcanada.ca, Valet)
  AUD  Reserve Bank of Australia, Tabelle F2, 2 Jahre    (www.rba.gov.au; vor 2013 Excel-Historie)
  JPY  Finanzministerium Japan, JGB 2 Jahre              (www.mof.go.jp; Historie + laufender Monat)
  GBP  Bank of England, nominale Par-Rendite 5 Jahre     (www.bankofengland.co.uk; 2 Jahre gibt es dort nicht)
  USD  FRED DGS2 (bereits vorhanden)
Nicht verfügbar: CHF (SNB-Reihen enden 07/2025), NZD (RBNZ sperrt automatische Abrufe).
"""

from __future__ import annotations

import io
import time

import pandas as pd

import urllib.error

from forex_nexus.ingestion.http import fetch_bytes, fetch_text

UA = "worlddriver-research/1.0"     # ehrliche Kennung; Zusätze wie „python“ blockt die Bank of England
ECB = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y?format=csvdata&startPeriod=2004-01-01"
BOC = "https://www.bankofcanada.ca/valet/observations/BD.CDN.2YR.DQ.YLD/csv?start_date=1995-01-01"
RBA_NOW = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
RBA_HIST = "https://www.rba.gov.au/statistics/tables/xls-hist/f02dhist.xls"
MOF_ALL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
MOF_NOW = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
BOE = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={start}"
       "&Dateto={end}&SeriesCodes=IUDSNPY&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
BOE_PAUSE = 300            # die Bank of England sperrt Folgeanfragen einige Minuten (HTML-Seite statt Daten)


def _series(dates, values) -> pd.Series:
    s = pd.Series(pd.to_numeric(pd.Series(values).values, errors="coerce"), index=pd.to_datetime(pd.Series(dates).astype(str).values, errors="coerce", format="mixed"))
    s = s[s.index.notna()].dropna()
    s.index = s.index.date
    return s[~pd.Index(s.index).duplicated(keep="last")].sort_index()


def parse_boc(text: str) -> pd.Series:
    body = text.split('"OBSERVATIONS"', 1)[1]
    df = pd.read_csv(io.StringIO(body.strip()))
    return _series(df.iloc[:, 0], df.iloc[:, 1])


def parse_rba_csv(text: str) -> pd.Series:
    rows = [r.split(",") for r in text.splitlines()]
    data = [r for r in rows if len(r) > 1 and r[0][:2].isdigit()]
    return _series([r[0] for r in data], [r[1] for r in data])


def parse_rba_xls(content: bytes) -> pd.Series:
    x = pd.read_excel(io.BytesIO(content), header=None)
    x = x[pd.to_datetime(x[0], errors="coerce", format="mixed").notna()]
    return _series(x[0], x[1])


def parse_mof(text: str) -> pd.Series:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Date"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    return _series(df["Date"], df["2Y"])


def parse_boe(text: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text))
    return _series(df.iloc[:, 0], df.iloc[:, 1])


def fetch(code: str, sleep=time.sleep) -> pd.Series:
    if code == "ECB_2Y":
        df = pd.read_csv(io.StringIO(fetch_text(ECB)), usecols=["TIME_PERIOD", "OBS_VALUE"])
        return _series(df["TIME_PERIOD"], df["OBS_VALUE"])
    if code == "BOC_2Y":
        return parse_boc(fetch_text(BOC, user_agent=UA))
    if code == "RBA_2Y":
        hist = parse_rba_xls(fetch_bytes(RBA_HIST))
        now = parse_rba_csv(fetch_text(RBA_NOW, user_agent=UA))
        return pd.concat([hist[hist.index < now.index.min()], now])
    if code == "MOF_2Y":
        hist = parse_mof(fetch_bytes(MOF_ALL).decode("utf-8", "replace"))
        now = parse_mof(fetch_bytes(MOF_NOW).decode("utf-8", "replace"))
        s = pd.concat([hist, now])
        return s[~pd.Index(s.index).duplicated(keep="last")].sort_index()
    if code == "BOE_5Y":                     # eine einzige Anfrage: Folgeanfragen sperrt die BoE für Minuten
        for attempt in range(3):
            if attempt:
                sleep(BOE_PAUSE)
            try:
                text = fetch_text(BOE.format(start="01/Jan/1995", end="now"), user_agent=UA)
            except urllib.error.HTTPError as exc:          # 403 = vorübergehende Sperre -> warten
                if exc.code != 403:
                    raise
                continue
            if text.startswith("DATE"):
                return parse_boe(text)
        raise RuntimeError("Bank of England lieferte keine Daten")
    raise ValueError(code)
