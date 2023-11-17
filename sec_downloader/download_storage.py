import shutil
import tempfile
from glob import glob
from pathlib import Path
from typing import Optional

from sec_downloader.core import DEFAULT_FILTER_PATTERN, FileContent


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
