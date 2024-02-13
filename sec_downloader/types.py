# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_types.ipynb.

# %% auto 0
__all__ = ['Ticker', 'FilingMetadata', 'RequestedFilings', 'CompanyAndAccessionNumber']

# %% ../nbs/00_types.ipynb 1
import re
from dataclasses import dataclass
from typing import Optional

# %% ../nbs/00_types.ipynb 3
@dataclass
class Ticker:
    symbol: str
    exchange: str

# %% ../nbs/00_types.ipynb 4
@dataclass
class FilingMetadata:
    accession_number: str
    form_type: str
    primary_doc_url: str
    items: str
    primary_doc_description: str
    filing_date: str
    report_date: str
    cik: str
    company_name: str
    tickers: list[Ticker]

# %% ../nbs/00_types.ipynb 5
@dataclass
class RequestedFilings:
    ticker_or_cik: str
    form_type: str = "10-Q"
    limit: int = 1

    _REGEX_PATTERN = r"^(?:(\d+)/)?([^/]+)(?:/([^/]+))?$"

    @classmethod
    def from_string(cls, s: str):
        match = re.match(cls._REGEX_PATTERN, s.strip())
        if not match:
            raise ValueError(f"Invalid RequestedFilings string: {s}")
        limit_str, ticker_or_cik, form_type = match.groups()
        limit = int(limit_str) if limit_str else cls.limit
        form_type = form_type if form_type else cls.form_type
        form_type = form_type.upper()
        return cls(
            limit=limit,
            ticker_or_cik=ticker_or_cik,
            form_type=form_type,
        )

# %% ../nbs/00_types.ipynb 7
@dataclass
class CompanyAndAccessionNumber:
    ticker_or_cik: str
    accession_number: str

    _REGEX_PATTERN = re.compile(r"\b([A-Za-z0-9.]+)/(\d{10}-?\d{2}-?\d{6})\b")

    @classmethod
    def from_string(
        cls, s: str, *, must_match=False
    ) -> Optional["CompanyAndAccessionNumber"]:
        match = re.search(cls._REGEX_PATTERN, s.strip())
        if not match:
            if must_match:
                raise ValueError(f"Invalid RequestedFilings string: {s}")
            else:
                return None
        ticker_or_cik, accession_number = match.groups()
        return cls(
            ticker_or_cik=ticker_or_cik,
            accession_number=accession_number,
        )
