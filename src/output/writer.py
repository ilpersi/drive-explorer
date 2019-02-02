import multiprocessing
import sys

from time import sleep

import output.csv
import output.json
import output.gsheet
import output.sqlite
from common.exceptions import UnkwonOutputType, manage_generic_exception
from common.logging import get_logger

logger = get_logger(__name__)

supported_types = {'.csv', '.json', '.gs', '.gsheet', '.sqlite', '.sqlite3', '.tsv'}


class OutputWriter(multiprocessing.Process):
    def __init__(self, results_list, results_lock, restuls_finished, output_path, output_extension, log_level,
                 email, credential_file, chuck_size=1_000):
        self._results_list = results_list
        self.results_lock = results_lock
        self._chuck_size = chuck_size
        self._restuls_finished = restuls_finished
        self._output_path = output_path
        self._output_extension = output_extension
        self._log_level = log_level
        self._credential_file = credential_file
        self._email = email

        self._writer = None

        super().__init__(daemon=False)

    def _get_writer(self, file_type):
        if file_type not in supported_types:
            raise UnkwonOutputType("Output format not supported: {}. Use one of the following ones: {}."
                                   .format(file_type, ", ".join(supported_types)))
        else:
            if file_type in {'.csv', '.tsv'}:
                delimiter = ',' if file_type == '.csv' else '\t'
                csv_file = open(self._output_path, 'w', newline='', encoding='utf-8-sig')
                self._writer = output.csv.CsvOutput(csv_file, self._results_list[0].keys(), self._log_level,
                                                    delimiter=delimiter)
            elif file_type in {'.gsheet', '.gs'}:
                self._writer = output.gsheet.GSheetOutput(self._output_path, self._results_list[0].keys(),
                                                          self._credential_file, self._email, self._log_level)
            elif file_type in {'.json'}:
                json_file = open(self._output_path, 'w')
                self._writer = output.json.JsonOutput(json_file)
            elif file_type in {'.sqlite', '.sqlite3'}:
                self._writer = output.sqlite.SQLiteOutput(self._output_path, self._results_list[0].keys(),
                                                          self._log_level)
            else:
                raise UnkwonOutputType("Output format not supported: {}. Use one of the following ones: {}."
                                       .format(self._output_extension, ", ".join(supported_types)))

    def run(self):
        logger.setLevel(self._log_level)
        try:
            self._safe_run()
        except KeyboardInterrupt:
            logger.debug("KeyboardInterrupt in OutputWriter.run")
        except Exception as e:
            manage_generic_exception(e, sys.exc_info(), "OutputWriter.run process")

    def _safe_run(self):
        # to initialize the writer we need at least one result
        while len(self._results_list) == 0:
            sleep(0.1)

        self._get_writer(self._output_extension)
        self._writer.writeheader()
        buffer = []

        while True:
            if len(self._results_list) > 0:
                logger.debug("self._results_list size from writer: {}".format(len(self._results_list)))

                # we move the results from the multiprocessing list to our internal buffer
                with self.results_lock:
                    while len(self._results_list) > 0:
                        buffer.append(self._results_list.pop())

            # if we have too many rows we start to write them
            if len(buffer) > self._chuck_size:
                logger.debug("Dumping {} rows to output".format(len(buffer)))
                self._writer.writerows(buffer)
                buffer.clear()

            if self._restuls_finished.is_set():
                break

        if len(buffer) > 0:
            self._writer.writerows(buffer)
            buffer.clear()

        if len(self._results_list) > 0:
            with self.results_lock:
                self._writer.writerows(self._results_list)
                self._results_list = []

        self._writer.close()
