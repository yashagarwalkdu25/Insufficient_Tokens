"""ISIN ↔ multi-exchange symbol mapper for Indian equities."""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class ISINMapping(BaseModel):
    isin: str
    nse_symbol: str
    bse_scrip_code: str
    yfinance_ticker: str
    alpha_vantage_ticker: str
    company_name: str
    sector: str


# Nifty 50 subset (20+ major stocks)
_NIFTY_50: list[dict[str, str]] = [
    {"isin": "INE002A01018", "nse": "RELIANCE",    "bse": "500325", "name": "Reliance Industries",        "sector": "Oil & Gas"},
    {"isin": "INE467B01029", "nse": "TCS",          "bse": "532540", "name": "Tata Consultancy Services",  "sector": "IT"},
    {"isin": "INE040A01034", "nse": "HDFCBANK",     "bse": "500180", "name": "HDFC Bank",                  "sector": "Banking"},
    {"isin": "INE009A01021", "nse": "INFY",         "bse": "500209", "name": "Infosys",                    "sector": "IT"},
    {"isin": "INE090A01021", "nse": "ICICIBANK",    "bse": "532174", "name": "ICICI Bank",                 "sector": "Banking"},
    {"isin": "INE030A01027", "nse": "HINDUNILVR",   "bse": "500696", "name": "Hindustan Unilever",         "sector": "FMCG"},
    {"isin": "INE154A01025", "nse": "ITC",          "bse": "500875", "name": "ITC",                        "sector": "FMCG"},
    {"isin": "INE062A01020", "nse": "SBIN",         "bse": "500112", "name": "State Bank of India",        "sector": "Banking"},
    {"isin": "INE397D01024", "nse": "BHARTIARTL",   "bse": "532454", "name": "Bharti Airtel",              "sector": "Telecom"},
    {"isin": "INE237A01028", "nse": "KOTAKBANK",    "bse": "500247", "name": "Kotak Mahindra Bank",        "sector": "Banking"},
    {"isin": "INE018A01030", "nse": "LT",           "bse": "500510", "name": "Larsen & Toubro",            "sector": "Infrastructure"},
    {"isin": "INE238A01034", "nse": "AXISBANK",     "bse": "532215", "name": "Axis Bank",                  "sector": "Banking"},
    {"isin": "INE296A01024", "nse": "BAJFINANCE",   "bse": "500034", "name": "Bajaj Finance",              "sector": "Finance"},
    {"isin": "INE585B01010", "nse": "MARUTI",       "bse": "532500", "name": "Maruti Suzuki",              "sector": "Automobile"},
    {"isin": "INE860A01027", "nse": "HCLTECH",      "bse": "532281", "name": "HCL Technologies",           "sector": "IT"},
    {"isin": "INE280A01028", "nse": "TITAN",        "bse": "500114", "name": "Titan Company",              "sector": "Consumer Goods"},
    {"isin": "INE044A01036", "nse": "SUNPHARMA",    "bse": "524715", "name": "Sun Pharmaceutical",         "sector": "Pharma"},
    {"isin": "INE155A01022", "nse": "TATAMOTORS",   "bse": "500570", "name": "Tata Motors",                "sector": "Automobile"},
    {"isin": "INE075A01022", "nse": "WIPRO",        "bse": "507685", "name": "Wipro",                      "sector": "IT"},
    {"isin": "INE239A01016", "nse": "NESTLEIND",    "bse": "500790", "name": "Nestle India",               "sector": "FMCG"},
    {"isin": "INE176A01028", "nse": "BAJAJFINSV",   "bse": "532978", "name": "Bajaj Finserv",              "sector": "Finance"},
    {"isin": "INE121A01024", "nse": "DRREDDY",      "bse": "500124", "name": "Dr Reddy's Laboratories",    "sector": "Pharma"},
    {"isin": "INE028A01039", "nse": "TECHM",        "bse": "532755", "name": "Tech Mahindra",              "sector": "IT"},
    {"isin": "INE256A01028", "nse": "ADANIENT",     "bse": "512599", "name": "Adani Enterprises",          "sector": "Diversified"},
]


def _build_mapping(entry: dict[str, str]) -> ISINMapping:
    nse = entry["nse"]
    return ISINMapping(
        isin=entry["isin"],
        nse_symbol=nse,
        bse_scrip_code=entry["bse"],
        yfinance_ticker=f"{nse}.NS",
        alpha_vantage_ticker=f"{nse}.BSE",
        company_name=entry["name"],
        sector=entry["sector"],
    )


class ISINMapper:
    """Resolve a symbol or ISIN to a multi-exchange mapping."""

    def __init__(self) -> None:
        self._by_nse: dict[str, ISINMapping] = {}
        self._by_isin: dict[str, ISINMapping] = {}
        self._by_bse: dict[str, ISINMapping] = {}

        for entry in _NIFTY_50:
            mapping = _build_mapping(entry)
            self._by_nse[mapping.nse_symbol.upper()] = mapping
            self._by_isin[mapping.isin] = mapping
            self._by_bse[mapping.bse_scrip_code] = mapping

    def resolve(self, symbol_or_isin: str) -> ISINMapping | None:
        key = symbol_or_isin.strip().upper()
        mapping = (
            self._by_nse.get(key)
            or self._by_isin.get(key)
            or self._by_bse.get(key)
        )
        if mapping is None:
            logger.debug("isin_mapper.miss", query=symbol_or_isin)
        return mapping

    async def load_from_db(self, pool: Any) -> None:
        """Load additional mappings from PostgreSQL at startup."""
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT isin, nse_symbol, bse_scrip_code, company_name, sector "
                    "FROM isin_mappings"
                )
                for row in rows:
                    nse = row["nse_symbol"]
                    mapping = ISINMapping(
                        isin=row["isin"],
                        nse_symbol=nse,
                        bse_scrip_code=str(row["bse_scrip_code"]),
                        yfinance_ticker=f"{nse}.NS",
                        alpha_vantage_ticker=f"{nse}.BSE",
                        company_name=row["company_name"],
                        sector=row["sector"],
                    )
                    self._by_nse[nse.upper()] = mapping
                    self._by_isin[mapping.isin] = mapping
                    self._by_bse[mapping.bse_scrip_code] = mapping
                logger.info("isin_mapper.loaded_from_db", count=len(rows))
        except Exception:
            logger.warning("isin_mapper.db_load_failed", exc_info=True)


isin_mapper = ISINMapper()
