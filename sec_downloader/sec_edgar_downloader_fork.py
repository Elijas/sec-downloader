from __future__ import annotations

import re
import sys
from collections import deque
from typing import Optional, Union

from sec_downloader.types import FilingMetadata, RequestedFilings, Ticker
from sec_edgar_downloader._Downloader import Downloader
from sec_edgar_downloader._constants import (
    AMENDS_SUFFIX,
    CIK_LENGTH,
    SUBMISSION_FILE_FORMAT,
    SUPPORTED_FORMS,
    URL_SUBMISSIONS,
)
from sec_edgar_downloader._orchestrator import get_to_download
from sec_edgar_downloader._sec_gateway import get_list_of_available_filings
from sec_edgar_downloader._utils import validate_and_convert_ticker_or_cik

accession_number_re = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def get_filing_metadata(
    *,
    ticker_or_cik: str,
    accession_number: str,
    user_agent: str,
    ticker_to_cik_mapping: dict[str, str],
) -> FilingMetadata:
    if len(accession_number) == 18:
        accession_number = (
            f"{accession_number[:10]}-{accession_number[10:12]}-{accession_number[12:]}"
        )
    if not accession_number_re.match(accession_number):
        raise ValueError(f"Invalid Accession Number: {accession_number}")
    cik = validate_and_convert_ticker_or_cik(ticker_or_cik, ticker_to_cik_mapping)
    result = _get_metadatas(
        cik=cik,
        user_agent=user_agent,
        limit=1,
        accession_number=accession_number,
    )
    if len(result) == 0:
        raise ValueError(f"Could not find filing for {accession_number}")
    assert len(result) == 1
    return result[0]


def get_latest_filings_metadata(
    *,
    requested: RequestedFilings,
    user_agent: str,
    ticker_to_cik_mapping: dict[str, str],
) -> list[FilingMetadata]:
    cik = validate_and_convert_ticker_or_cik(
        requested.ticker_or_cik, ticker_to_cik_mapping
    )

    if requested.limit is None:
        # If amount is not specified, obtain all available filings.
        # We simply need a large number to denote this and the loop
        # responsible for fetching the URLs will break appropriately.
        limit = sys.maxsize
    else:
        limit = int(requested.limit)
        if limit < 1:
            raise ValueError("Invalid amount. Please enter a number greater than 1.")

    if requested.form_type not in SUPPORTED_FORMS:
        form_options = ", ".join(Downloader.supported_forms)
        raise ValueError(
            f"{requested.form_type!r} forms are not supported. "
            f"Please choose from the following: {form_options}."
        )

    return _get_metadatas(
        cik=cik,
        user_agent=user_agent,
        limit=limit,
        ticker_or_cik=requested.ticker_or_cik,
        form_type=requested.form_type,
    )


def _get_metadatas(
    *,
    cik: str,
    user_agent: str,
    limit: int,
    ticker_or_cik: Optional[str] = None,
    accession_number: Optional[str] = None,
    form_type: Optional[str] = None,
) -> list[FilingMetadata]:
    assert (
        ticker_or_cik and form_type
    ) or accession_number, (
        "Either ticker or CIK and form type or accession number must be provided"
    )

    submissions_uri = URL_SUBMISSIONS.format(
        submission=SUBMISSION_FILE_FORMAT.format(cik=cik)
    )

    additional_submissions = None
    found_metadatas: list[FilingMetadata] = []
    fetched_count = 0
    company_tickers = None
    company_cik = None
    company_name = None
    while fetched_count < limit:
        resp_json = get_list_of_available_filings(submissions_uri, user_agent)
        # First API response is different from further API responses
        if additional_submissions is None:
            filings_json = resp_json["filings"]["recent"]
            additional_submissions = deque(resp_json["filings"]["files"])
            company_tickers = [
                Ticker(symbol=ticker, exchange=exchange)
                for ticker, exchange in zip(
                    resp_json["tickers"], resp_json["exchanges"]
                )
            ]
            company_name = resp_json["name"]
            company_cik = str(resp_json["cik"]).zfill(CIK_LENGTH)
        # On second page or more of API response (for companies with >1000 filings)
        else:
            filings_json = resp_json
        assert company_tickers is not None
        assert company_name is not None
        assert company_cik is not None

        accession_numbers = filings_json["accessionNumber"]
        primary_document_urls = filings_json["primaryDocument"]
        filing_dates = filings_json["filingDate"]
        report_dates = filings_json["reportDate"]
        primary_doc_descriptions = filings_json["primaryDocDescription"]
        items_list = filings_json["items"]
        form_types = filings_json["form"]

        for (
            this_accession_number,
            primary_doc_filename,
            filing_date,
            report_date,
            primary_doc_description,
            this_form_type,
            items,
        ) in zip(
            accession_numbers,
            primary_document_urls,
            filing_dates,
            report_dates,
            primary_doc_descriptions,
            form_types,
            items_list,
        ):
            is_amend = this_form_type.endswith(AMENDS_SUFFIX)
            this_form_type = this_form_type[:-2] if is_amend else this_form_type
            if (
                (form_type and form_type != this_form_type)
                or (accession_number and accession_number != this_accession_number)
                or is_amend
            ):
                continue

            td = get_to_download(cik, this_accession_number, primary_doc_filename)
            found_metadata = FilingMetadata(
                primary_doc_url=td.primary_doc_uri,
                accession_number=this_accession_number,
                tickers=company_tickers,
                company_name=company_name,
                filing_date=filing_date,
                report_date=report_date,
                primary_doc_description=primary_doc_description,
                items=items,
                form_type=this_form_type,
                cik=company_cik,
            )
            found_metadatas.append(found_metadata)
            fetched_count += 1
            # We have reached the requested download limit, so break inner for loop
            # early and allow the outer while loop to break.
            if fetched_count == limit:
                break

        if len(additional_submissions) == 0:
            break

        next_page = additional_submissions.popleft()["name"]
        submissions_uri = URL_SUBMISSIONS.format(submission=next_page)

    requested_form = f" of type {form_type}" if form_type else ""
    error_context = f"{accession_number or ticker_or_cik}{requested_form}"
    if not found_metadatas:
        msg = f"Could not find any filings: {error_context}"
        raise ValueError(msg)
    if len(found_metadatas) > limit:
        msg = f"Found more than {limit} filings, actual count is {len(found_metadatas)}: {error_context}"
        raise OverflowError(msg)

    return found_metadatas
