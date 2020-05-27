import os

import requests


VALIDATION_API_URL = "https://selectiontool.buildingsync.net/api/validate"
DEFAULT_SCHEMA_VERSION = '2.0.0'
DEFAULT_USE_CASE = 'L000 OpenStudio Simulation'


class ValidationClientException(Exception):
    pass


def _validation_api_post(file_, schema_version, use_case_name):
    payload = {'schema_version': schema_version}
    files = [
        ('file', file_)
    ]

    return requests.request(
        "POST",
        VALIDATION_API_URL,
        data=payload,
        files=files,
        timeout=60 * 2,  # timeout after two minutes (it can take a long time for zips)
    )


def validate_use_case(file_, schema_version=DEFAULT_SCHEMA_VERSION, use_case_name=DEFAULT_USE_CASE):
    """calls Selection Tool's validation API

    :param file_: File, the file to validate; can be single xml or zip
    :param schema_version: string
    :param use_case_name: string
    :return: tuple, (bool, list), bool indicates if the file passes validation,
             the list is a collection of files and their errors, warnings, and infos
    """

    try:
        response = _validation_api_post(file_, schema_version, use_case_name)
    except requests.exceptions.Timeout:
        raise ValidationClientException(
            f"Request to Selection Tool timed out. SEED may need to increase the timeout",
        )
    except Exception as e:
        raise ValidationClientException(
            f"Failed to make request to selection tool: {e}",
        )

    if response.status_code != 200:
        raise ValidationClientException(
            f"Received bad response from Selection Tool: {response.text}",
        )

    try:
        response_body = response.json()
    except ValueError:
        raise ValidationClientException(
            f"Expected JSON response from Selection Tool: {response.text}",
        )

    if response_body.get('success', False) is not True:
        ValidationClientException(
            f"Selection Tool request was not successful: {response.text}",
        )

    response_schema_version = response_body.get('schema_version')
    if response_schema_version != schema_version:
        ValidationClientException(
            f"Expected schema_version to be '{schema_version}' but it was '{response_schema_version}'",
        )

    _, file_extension = os.path.splitext(file_.name)
    validation_results = response_body.get('validation_results')
    # check the returned type and make validation_results a list if it's not already
    if file_extension == '.zip':
        if type(validation_results) is not list:
            raise ValidationClientException(
                f"Expected response validation_results to be list for zip file: {response.text}",
            )
    else:
        if type(validation_results) is not dict:
            raise ValidationClientException(
                f"Expected response validation_results to be dict for single xml file: {response.text}",
            )
        # turn the single file result into the same structure as zip file result
        validation_results = [{
            'file': os.path.basename(file_.name),
            'results': validation_results,
        }]

    # check that the schema and use case is valid for every file
    file_summaries = []
    all_files_valid = True
    for validation_result in validation_results:
        results = validation_result['results']
        filename = validation_result['file']

        # it's possible there's no use_cases key - occurs when schema validation fails
        if results['schema']['valid'] is False:
            use_case_result = {}
        else:
            if use_case_name not in results.get('use_cases', []):
                raise ValidationClientException(
                    f'Expected use case "{use_case_name}" to exist in result\'s uses cases.',
                )
            use_case_result = results['use_cases'][use_case_name]

        file_summary = {
            'file': filename,
            'schema_errors': results['schema'].get('errors', []),
            'use_case_errors': use_case_result.get('errors', []),
            'use_case_warnings': use_case_result.get('warnings', []),
        }

        file_has_errors = (
            len(file_summary['schema_errors']) > 0
            or len(file_summary['use_case_errors']) > 0
        )
        if file_has_errors:
            all_files_valid = False

        file_has_errors_or_warnings = (
            file_has_errors
            or len(file_summary['use_case_warnings']) > 0
        )
        if file_has_errors_or_warnings:
            file_summaries.append(file_summary)

    return all_files_valid, file_summaries
