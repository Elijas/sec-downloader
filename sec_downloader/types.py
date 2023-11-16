from dataclasses import dataclass


@dataclass
class Ticker:
    symbol: str
    exchange: str


@dataclass
class FilingMetadata:
    accession_number: str
    form_type: str
    primary_doc_url: str
    items: str
    primary_doc_description: str
    filing_date: str
    report_date: str
    company_name: str
    tickers: list[Ticker]


@dataclass
class Filing:
    metadata: FilingMetadata
    primary_document: bytes
    primary_document: bytes
