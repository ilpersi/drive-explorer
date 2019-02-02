from datetime import datetime
from itertools import chain

# third parties from imports
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# libraries import
import output.base
from common.backoff import execute_request
from commands.credential import GoogleCredential
from common.drive_utils import permissions_to_string
from common.logging import get_logger

logger = get_logger(__name__)


class GSheetOutput(output.base.AbstractOutput):
    """This class takes care of writing the provided input in a Google Spreadsheet."""

    def __init__(self, sheet_name, fieldnames, credential_file, user, log_level):
        """

        :param sheet_name: the desired name for the output spreadsheet
        :param fieldnames: the names of the columns to write in the spreadsheet
        :param credential_file: path to the file with the Google credentials
        :param user: the email address of the user that will create the output spreadsheet
        :param log_level: log level, obtained as parameter from the CLI
        """
        # id and name should always be at the beginning of the sheet
        self._fieldnames = ['id', 'name']
        self._ignore_fields = {'permissions', 'internal_folder'}
        self._file_cache = set()

        self._fieldnames.extend(key for
                                key in sorted(chain(fieldnames, ('owners', 'can_edit', 'can_comment', 'can_view')))
                                if key not in self._fieldnames and key not in self._ignore_fields)

        self._sheet_name = sheet_name
        self._credential_file = credential_file
        self._user = user
        self._log_level = log_level

        with GoogleCredential(self._credential_file, self._user, log_level=self._log_level) as google_cred:
            self._email, self._credentials = google_cred.get_credentials()

        if self._credentials.expired:
            self._credentials.refresh(Request())

        self._sheet_sdk = build('sheets', 'v4', credentials=self._credentials)
        self._sheet_title = 'drive-explorer-{}'.format(datetime.now().strftime("%Y%m%d"))
        self._total_cells = 0
        # sheets currently have a limit of 2M cells
        self._cell_limit = 1_900_000
        self._sheet = None
        self._sheets_info = []
        self._drive_sdk = None

        logger.setLevel(self._log_level)

    def writeheader(self):
        """
        This function will take care of creating the spreadsheet and the first sheet in it. This function will also
        be used when the Google Sheet cell limit is near and the output needs to be split in two different sheets
        """

        # body for the spreadsheets.create() method of the API
        # https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/create
        create_body = {
            'properties': {
                'title': '{}'.format(self._sheet_name.replace(".gs", "").replace(".gsheet", "")),
            },
            'sheets': [{
                'properties': {
                    'sheetId': 0,
                    'title': self._sheet_title,
                    'index': 0,
                    'sheetType': 'GRID',
                    'gridProperties': {
                        'rowCount': 1,  # two rows: the header itself and an empty line used as buffer
                        'columnCount': len(self._fieldnames),
                    },
                },
                'data': [{
                    'startRow': 0,
                    'startColumn': 0,
                    'rowData': [{  # one per row
                        'values': [  # one per column
                        ]
                    }, ],
                }],
            }]
        }

        # we populate the header and we make sure it is bold
        for header in self._fieldnames:
            header_data = {
                'userEnteredValue': {
                    'stringValue': header
                },
            }
            create_body['sheets'][0]['data'][0]['rowData'][0]['values'].append(header_data)

        # call the Google APIs
        # https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/create
        self._sheet = execute_request(self._sheet_sdk.spreadsheets().create(body=create_body))
        # we save info about the latest created sheet
        self._sheets_info.append(self._sheet)

        # we make sure that if a new header is written the counter are reinitialized
        self._total_cells = len(self._fieldnames)

    def writerow(self, rowdict):
        """
        Wrapper around rowdiicts
        :param rowdict: the line that we want to write
        """
        self.writerows((rowdict,))

    def writerows(self, rowdicts):
        """
        Where all the data is written to the Google Spreadsheets
        :param rowdicts: a list of rows. Each row is a dictionary of data to be written in the output
        """

        # we need to normalize data before we append it to the Google Spreadsheet
        # the APIs are expecting a list of values, not a dictionary
        etl_data = []

        for row in rowdicts:
            # as folders can have more than one parent and are processed in parallel, this is the only possible way
            # to avoid duplicate file IDs
            if row['id'] in self._file_cache:
                continue

            self._file_cache.add(row['id'])

            etl_line = []
            permissions = permissions_to_string(row['id'], row['permissions'])
            # we merge row with explained permissions
            row = {**row, **permissions}

            # we concatenate the parents
            row['parents'] = ", ".join(row['parents'])

            # we make sure that the values are in same order as the header
            for field in self._fieldnames:
                etl_line.append(row[field])
            etl_data.append(etl_line)

        # if we have too many cells we split to the next sheet
        if (self._total_cells + (len(self._fieldnames) * len(etl_data))) > self._cell_limit:
            self.writeheader()

        # body for the spreadsheets.values.update() method
        # https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/append
        update_body = {
            'values': etl_data,
        }

        update_body_params = {
            'spreadsheetId': self._sheet['spreadsheetId'],
            'range': '{}'.format(self._sheet_title),
            'body': update_body,
            'valueInputOption': 'RAW',
            'insertDataOption': 'INSERT_ROWS',
        }

        execute_request(self._sheet_sdk.spreadsheets().values().append(**update_body_params))

        # we make sure to update the counters
        self._total_cells += len(self._fieldnames) * len(etl_data)

    def close(self):
        """
        Where we clean the created files and make sure that the name is correct.
        """
        if len(self._sheets_info) > 1:
            self._drive_sdk = build('drive', 'v3', credentials=self._credentials)

            for sheet_i, details in enumerate(self._sheets_info):
                title = "{} {} of {}".format(details['properties']['title'], sheet_i + 1, len(self._sheets_info))

                update_body = {
                    'fileId': details['spreadsheetId'],
                    'body': {
                        'name': title
                    }
                }

                execute_request(self._drive_sdk.files().update(**update_body))
                self._sheets_info[sheet_i]['properties']['title'] = title

            print("Data did not fit in one spreadsheet, so it has been split in {}".format(len(self._sheets_info)))

        for details in self._sheets_info:
            header_update_req = {
                'spreadsheetId': details['spreadsheetId'],
                'body': {
                    'requests': [
                        {
                            'updateSheetProperties': {  # freeze first row
                                'properties': {
                                    'gridProperties': {
                                        'frozenRowCount': 1
                                    }
                                },
                                'fields': 'gridProperties.frozenRowCount'
                            }
                        },
                        {
                            'repeatCell': {  # make the first row bold
                                'range': {
                                    'endRowIndex': 1
                                },
                                'cell': {
                                    'userEnteredFormat': {
                                        'textFormat': {
                                            'bold': True
                                        }
                                    }
                                },
                                'fields': 'userEnteredFormat.textFormat.bold'
                            }
                        },
                        {
                            'setBasicFilter': {  # add the filter
                                'filter': {
                                    'range': {
                                        'sheetId': 0
                                    }
                                }
                            }
                        }
                    ]
                }
            }
            # batchUpdate request
            # https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
            execute_request(self._sheet_sdk.spreadsheets().batchUpdate(**header_update_req))
            print("Saved data in sheet {} at URL {}".format(details['properties']['title'], details['spreadsheetUrl']))
