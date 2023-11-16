import re
from collections import deque

from sec_edgar_downloader._constants import SUBMISSION_FILE_FORMAT, URL_SUBMISSIONS
from sec_edgar_downloader._orchestrator import get_to_download
from sec_edgar_downloader._sec_gateway import get_list_of_available_filings

accession_number_re = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def get_primary_doc_url(*, accession_number: str, user_agent: str) -> str:
    if not accession_number_re.match(accession_number):
        raise ValueError(f"Invalid Accession Number: {accession_number}")
    cik = accession_number[:10]

    submissions_uri = URL_SUBMISSIONS.format(
        submission=SUBMISSION_FILE_FORMAT.format(cik=cik)
    )

    additional_submissions = None
    found_filename = ""
    while True:
        resp_json = get_list_of_available_filings(submissions_uri, user_agent)
        # First API response is different from further API responses
        if additional_submissions is None:
            filings_json = resp_json["filings"]["recent"]
            additional_submissions = deque(resp_json["filings"]["files"])
        # On second page or more of API response (for companies with >1000 filings)
        else:
            filings_json = resp_json

        accession_numbers = filings_json["accessionNumber"]
        primary_document_urls = filings_json["primaryDocument"]

        for doc_accession_number, primary_doc_filename in zip(
            accession_numbers, primary_document_urls
        ):
            if doc_accession_number != accession_number:
                continue
            found_filename = primary_doc_filename
            break

        if found_filename:
            break

        if len(additional_submissions) == 0:
            break

        next_page = additional_submissions.popleft()["name"]
        submissions_uri = URL_SUBMISSIONS.format(submission=next_page)

    assert found_filename, f"Could not find document for {accession_number}"

    td = get_to_download(cik, accession_number, found_filename)
    return td.primary_doc_uri
