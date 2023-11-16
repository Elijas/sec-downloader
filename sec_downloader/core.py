# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_core.ipynb.

# %% auto 0
__all__ = ['FileContent', 'DEFAULT_FILTER_PATTERN', 'ONLY_HTML', 'DownloadStorage', 'Downloader']

# %% ../nbs/00_core.ipynb 3
import tempfile
import shutil
from pathlib import Path
from glob import glob
from typing import Optional
from collections import namedtuple
from sec_edgar_downloader import Downloader as SecEdgarDownloader
from .sec_edgar_downloader_fork import get_primary_doc_url
from sec_edgar_downloader._sec_gateway import download_filing

# %% ../nbs/00_core.ipynb 5
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

# %% ../nbs/00_core.ipynb 6
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

    def get_primary_doc_url(self, *, accession_number: str):
        return get_primary_doc_url(
            accession_number=accession_number, user_agent=self.user_agent
        )

    def get_primary_doc_html(
        self, *, accession_number: str, encoding: str | None = DEFAULT_ENCODING
    ):
        primary_doc_url = self.get_primary_doc_url(accession_number=accession_number)
        html = download_filing(primary_doc_url, self.user_agent)
        if encoding is not None:
            html = html.decode(encoding)
        return html
