from collections import namedtuple
from typing import Optional, Union

from sec_edgar_downloader._Downloader import Downloader as SecEdgarDownloader
from sec_edgar_downloader._orchestrator import get_ticker_to_cik_mapping
from sec_edgar_downloader._sec_gateway import download_filing

from sec_downloader.sec_edgar_downloader_fork import (
    FilingMetadata,
    get_filing_metadata,
    get_latest_filings_metadata,
    _get_metadatas_batch,
    accession_number_re,
)
from sec_downloader.types import CompanyAndAccessionNumber, RequestedFilings
from sec_edgar_downloader._utils import validate_and_convert_ticker_or_cik
from collections import defaultdict

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
        *,
        include_amends: bool = False,
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
                        include_amends=include_amends,
                    )
                ]

        if isinstance(query, (RequestedFilings, str)):
            if isinstance(query, str):
                query = RequestedFilings.from_string(query)

            new_metadatas = get_latest_filings_metadata(
                requested=query,
                user_agent=self.user_agent,
                ticker_to_cik_mapping=self._ticker_to_cik_mapping,
                include_amends=include_amends,
            )
            return new_metadatas

        raise ValueError(f"Invalid input: {query}")

    def get_filing_metadatas_batch(
        self,
        queries: list[Union[str, CompanyAndAccessionNumber]],
        *,
        include_amends: bool = False,
    ) -> list[FilingMetadata]:
        """
        Efficiently fetch metadata for multiple accession numbers.

        Groups accession numbers by CIK and makes one API call per company,
        significantly reducing the number of requests compared to fetching
        one by one.

        Args:
            queries: List of accession number queries in format:
                - "TICKER/ACCESSION_NUMBER" (e.g., "AAPL/0000320193-23-000077")
                - "CIK/ACCESSION_NUMBER" (e.g., "320193/0000320193-23-000077")
                - CompanyAndAccessionNumber objects
            include_amends: Include amended filings (e.g., 8-K/A)

        Returns:
            List of FilingMetadata objects for all requested filings

        Example:
            >>> metadatas = dl.get_filing_metadatas_batch([
            ...     "AAPL/0000320193-23-000077",
            ...     "AAPL/0000320193-23-000078",
            ...     "MSFT/0000950170-24-087843",
            ... ])
            # Makes only 2 API calls (one for AAPL, one for MSFT)
        """
        if not queries:
            return []

        # Parse all queries to extract ticker_or_cik and accession_number
        parsed_queries = []
        for query in queries:
            if isinstance(query, str):
                parsed = CompanyAndAccessionNumber.from_string(query, must_match=True)
                parsed_queries.append(parsed)
            elif isinstance(query, CompanyAndAccessionNumber):
                parsed_queries.append(query)
            else:
                raise ValueError(f"Invalid query type: {type(query)}. Expected str or CompanyAndAccessionNumber")

        # Validate and normalize accession numbers, convert tickers to CIKs
        cik_to_accession_numbers = defaultdict(set)
        for parsed in parsed_queries:
            # Normalize accession number format
            accession_number = parsed.accession_number
            if len(accession_number) == 18:
                accession_number = (
                    f"{accession_number[:10]}-{accession_number[10:12]}-{accession_number[12:]}"
                )
            if not accession_number_re.match(accession_number):
                raise ValueError(f"Invalid Accession Number: {accession_number}")

            # Convert ticker to CIK
            cik = validate_and_convert_ticker_or_cik(
                parsed.ticker_or_cik, self._ticker_to_cik_mapping
            )
            cik_to_accession_numbers[cik].add(accession_number)

        # Fetch metadata for each CIK
        all_metadatas = []
        for cik, accession_numbers in cik_to_accession_numbers.items():
            metadatas = _get_metadatas_batch(
                cik=cik,
                user_agent=self.user_agent,
                accession_numbers=accession_numbers,
                include_amends=include_amends,
            )
            all_metadatas.extend(metadatas)

        return all_metadatas

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
