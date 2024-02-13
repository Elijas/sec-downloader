from collections import namedtuple
from typing import Optional, Union

from sec_edgar_downloader._Downloader import Downloader as SecEdgarDownloader
from sec_edgar_downloader._orchestrator import get_ticker_to_cik_mapping
from sec_edgar_downloader._sec_gateway import download_filing

from sec_downloader.sec_edgar_downloader_fork import (
    FilingMetadata,
    get_filing_metadata,
    get_latest_filings_metadata,
)
from sec_downloader.types import CompanyAndAccessionNumber, RequestedFilings

FileContent = namedtuple("FileContent", ["path", "content"])
DEFAULT_FILTER_PATTERN = "**/*.*"


class Downloader:
    def __init__(
        self,
        company_name: str,
        email_address: str,
    ):
        self.company_name = company_name
        self.email_address = email_address
        self._ticker_to_cik_mapping = get_ticker_to_cik_mapping(self.user_agent)

    @property
    def user_agent(self):
        return f"{self.company_name} {self.email_address}"

    def get_filing_metadatas(
        self,
        query: Union[str, RequestedFilings, CompanyAndAccessionNumber],
    ) -> list[FilingMetadata]:
        if isinstance(query, (CompanyAndAccessionNumber, str)):
            if isinstance(query, str):
                new_query = CompanyAndAccessionNumber.from_string(
                    query, must_match=False
                )
                if new_query is not None:
                    query = new_query
            if isinstance(query, CompanyAndAccessionNumber):
                return [
                    get_filing_metadata(
                        ticker_or_cik=query.ticker_or_cik,
                        accession_number=query.accession_number,
                        user_agent=self.user_agent,
                        ticker_to_cik_mapping=self._ticker_to_cik_mapping,
                    )
                ]

        if isinstance(query, (RequestedFilings, str)):
            if isinstance(query, str):
                query = RequestedFilings.from_string(query)

            new_metadatas = get_latest_filings_metadata(
                requested=query,
                user_agent=self.user_agent,
                ticker_to_cik_mapping=self._ticker_to_cik_mapping,
            )
            return new_metadatas

        raise ValueError(f"Invalid input: {query}")

    def download_filing(self, *, url: str) -> bytes:
        return download_filing(url, self.user_agent)

    def get_filing_html(
        self,
        *,
        query: Optional[Union[str, RequestedFilings, CompanyAndAccessionNumber]] = None,
        # Syntactic Sugar
        ticker: Optional[str] = None,
        form: Optional[str] = None,
    ) -> bytes:
        """
        Simplified interface to download a single filing.
        To download multiple filings, save metadata, and have more control,
        use `get_filing_metadatas()` and `download_filing()`.
        """
        # Syntactic Sugar
        if query:
            msg = (
                "Error: Ticker or form should not be provided when query is specified."
            )
            assert not ticker and not form, msg
        if ticker or form:
            msg = (
                "Error: Query should not be provided when ticker or form is specified."
            )
            assert not query, msg
            query = f"{ticker}/{form}"
        assert query, "Error: Either query or ticker and form must be specified."

        result = []
        for metadata in self.get_filing_metadatas(query):
            html = self.download_filing(url=metadata.primary_doc_url)
            result.append(html)

        if len(result) == 0:
            raise ValueError(f"Could not find filing for {query}")
        if len(result) > 1:
            raise ValueError(
                f"Found multiple filings for {query}. Use `get_filing_metadatas()` and `download_filing() instead."
            )
        return result[0]
