import re
import shutil
import tempfile
from collections import namedtuple
from glob import glob
from pathlib import Path
from typing import Optional, Union

from sec_downloader.requested_filings import RequestedFilings
from sec_downloader.types import Filing
from sec_edgar_downloader import Downloader as SecEdgarDownloader
from sec_edgar_downloader._orchestrator import get_ticker_to_cik_mapping
from sec_edgar_downloader._sec_gateway import download_filing

from .sec_edgar_downloader_fork import (
    FilingMetadata,
    get_filing_metadata,
    get_latest_filings_metadata,
)

FileContent = namedtuple("FileContent", ["path", "content"])
DEFAULT_FILTER_PATTERN = "**/*.*"
ACCESSION_NUMBER_PATTERN = re.compile(r"\b(\d{10}-?\d{2}-?\d{6})\b")


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

    def get_filing_metadata(self, *, accession_number: str) -> FilingMetadata:
        return get_filing_metadata(
            accession_number=accession_number, user_agent=self.user_agent
        )

    def get_latest_filings_metadata(
        self, *, requested: RequestedFilings
    ) -> list[FilingMetadata]:
        return get_latest_filings_metadata(
            requested=requested,
            user_agent=self.user_agent,
            ticker_to_cik_mapping=self._ticker_to_cik_mapping,
        )

    def get_filing_metadatas(
        self,
        requested_filings: list[Union[str, RequestedFilings]],
    ) -> list[FilingMetadata]:
        metadatas: list[FilingMetadata] = []
        for requested in requested_filings:
            if isinstance(requested, str) and (
                match := ACCESSION_NUMBER_PATTERN.search(requested)
            ):
                accession_number = match.group(1)
                metadata = self.get_filing_metadata(accession_number=accession_number)
                metadatas.append(metadata)
                continue

            if isinstance(requested, RequestedFilings):
                new_metadatas = self.get_latest_filings_metadata(requested=requested)
                metadatas.extend(new_metadatas)
                continue

            if isinstance(requested, str):
                requested = RequestedFilings.from_string(requested)
                new_metadatas = self.get_latest_filings_metadata(requested=requested)
                metadatas.extend(new_metadatas)
                continue

            raise ValueError(f"Invalid input: {requested}")

        return metadatas

    def download_filings(self, metadatas: list[FilingMetadata]) -> list[Filing]:
        filings: list[Filing] = []
        for metadata in metadatas:
            primary_doc = self.download_filing_from_sec_edgar_url(
                metadata.primary_doc_url
            )
            filings.append(Filing(metadata=metadata, primary_document=primary_doc))
        return filings

    def download_filing_from_sec_edgar_url(self, url: str) -> bytes:
        return download_filing(url, self.user_agent)
        return download_filing(url, self.user_agent)
