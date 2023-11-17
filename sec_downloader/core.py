import re
import shutil
import tempfile
from collections import namedtuple
from glob import glob
from pathlib import Path
from typing import Optional, Union

from sec_downloader.sec_edgar_downloader_fork import (
    FilingMetadata,
    get_filing_metadata,
    get_latest_filings_metadata,
)
from sec_downloader.types import CompanyAndAccessionNumber, RequestedFilings
from sec_edgar_downloader import Downloader as SecEdgarDownloader
from sec_edgar_downloader._orchestrator import get_ticker_to_cik_mapping
from sec_edgar_downloader._sec_gateway import download_filing

FileContent = namedtuple("FileContent", ["path", "content"])
DEFAULT_FILTER_PATTERN = "**/*.*"


class DownloadStorage:
    def __init__(self, *, filter_pattern: Optional[str] = None):
        self.glob_pattern = filter_pattern or DEFAULT_FILTER_PATTERN
        self.temp_dir = None
        self.file_contents = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        return self.temp_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._read_files()
        if self.temp_dir:
            shutil.rmtree(self.temp_dir)

    def _read_files(self):
        self.file_contents = []
        assert self.temp_dir is not None, "Temp dir should be set"
        glob_path = Path(self.temp_dir) / self.glob_pattern
        for filepath in glob(str(glob_path), recursive=True):
            path = Path(filepath)
            relative_path = path.relative_to(self.temp_dir)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.file_contents.append(FileContent(relative_path, content))

    def get_file_contents(self):
        if self.file_contents is None:
            raise RuntimeError(
                "File contents are not available until the context is exited."
            )
        return self.file_contents


ONLY_HTML = "**/*.htm*"


class Downloader:
    DEFAULT_ENCODING = "utf-8"

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

    def get_latest_html(self, doc_type: str, ticker: str):
        storage = DownloadStorage(filter_pattern=ONLY_HTML)
        with storage as path:
            dl = SecEdgarDownloader(self.company_name, self.email_address, path)
            dl.get(doc_type, ticker, limit=1, download_details=True)
        return storage.get_file_contents()[0].content

    def get_latest_n_html(self, doc_type: str, ticker: str, n: int):
        storage = DownloadStorage(filter_pattern=ONLY_HTML)
        with storage as path:
            dl = SecEdgarDownloader(self.company_name, self.email_address, path)
            dl.get(doc_type, ticker, limit=n, download_details=True)
        return [k.content for k in storage.get_file_contents()]

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
        assert url.startswith("https://www.sec.gov/")
        return download_filing(url, self.user_agent)
