# sec-downloader

<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->

<a href="https://github.com/elijas/sec-downloader/actions/workflows/test.yaml"><img alt="GitHub Workflow Status" src="https://img.shields.io/github/actions/workflow/status/elijas/sec-downloader/test.yaml?label=build"></a>
<a href="https://pypi.org/project/sec-downloader/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/sec-downloader"></a>
<a href="https://badge.fury.io/py/sec-downloader"><img src="https://badge.fury.io/py/sec-downloader.svg" alt="PyPI version" /></a>
<a href="LICENSE"><img src="https://img.shields.io/github/license/elijas/sec-downloader.svg" alt="Licence"></a>

Useful extensions for sec-edgar-downloader.

## Install

``` sh
pip install sec_downloader
```

## Features

- Instead of being saved to disk, files are directly downloaded into
  memory.
- Use “glob” pattern to select which files are read to memory.

## How to use

Downloading multiple documents:

``` python
from sec_edgar_downloader import Downloader
from sec_downloader import DownloadStorage

storage = DownloadStorage()
with storage as path:
    dl = Downloader("MyCompanyName", "email@example.com", path)
    dl.get("10-K", "GOOG", limit=2)
# all files are now deleted and only stored in memory

for path, content in storage.get_file_contents():
    print(f"Path: {path}\nContent [len={len(content)}]: {content[:30]}...\n")
```

    Path: sec-edgar-filings/GOOG/10-K/0001652044-22-000019/full-submission.txt
    Content [len=15044932]: <SEC-DOCUMENT>0001652044-22-00...

    Path: sec-edgar-filings/GOOG/10-K/0001652044-23-000016/full-submission.txt
    Content [len=15264470]: <SEC-DOCUMENT>0001652044-23-00...

Let’s demonstrate how to download a single file (latest 10-Q filing
details in HTML format) to memory.

``` python
ONLY_HTML = "**/*.htm*"

storage = DownloadStorage(filter_pattern=ONLY_HTML)
with storage as path:
    dl = Downloader("MyCompanyName", "email@example.com", path)
    dl.get("10-Q", "AAPL", limit=1, download_details=True)
# all files are now deleted and only stored in memory

content = storage.get_file_contents()[0].content
print(f"{content[:50]}...")
```

    <?xml version="1.0" ?><!--XBRL Document Created wi...
