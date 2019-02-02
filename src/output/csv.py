import csv
from itertools import chain

import output.base
from common.drive_utils import permissions_to_string
from common.logging import get_logger

logger = get_logger(__name__)


class CsvOutput(csv.DictWriter, output.base.AbstractOutput):
    """Generic CSV Output Class, mainly a wrapper around the standar csv.DictWritert"""

    def __init__(self, f, fieldnames, log_level, *args, **kwds):
        """
        CsvOutput initializer

        :param f: file pointer used to write the CSV file
        :param fieldnames: the names of the columns in the CSV
        :param args: positional args for the wrapped csv.DictWriter
        :param kwds: named args for the wrapped csv.DictWriter
        """
        self._f = f
        self._log_level = log_level

        sorted_fieldnames = ['id', 'name']
        self._ignore_fields = {'permissions', 'internal_folder'}
        self._file_cache = set()

        sorted_fieldnames.extend(key for
                                 key in sorted(chain(fieldnames, ('owners', 'can_edit', 'can_comment', 'can_view')))
                                 if key not in sorted_fieldnames and key not in self._ignore_fields)

        logger.setLevel(self._log_level)

        super().__init__(self._f, sorted_fieldnames, extrasaction="ignore", *args, **kwds)

    def writerows(self, rowdicts):

        etl_rows = []
        for row in rowdicts:
            # as folders can have more than one parent and are processed in parallel, this is the only possible way
            # to avoid duplicate file IDs
            if row['id'] in self._file_cache:
                continue

            self._file_cache.add(row['id'])

            permissions = permissions_to_string(row['id'], row['permissions'])

            # we merge the dictionaries and we remove useless keys
            etl_row = {**row, **permissions}
            etl_row.pop('permissions')

            # we concatenate the parents
            etl_row['parents'] = ", ".join(row['parents'])

            etl_rows.append(etl_row)

        super().writerows(etl_rows)

    def close(self):
        """
        Simply closes the underlying file object to make sure no further modifications are made to it

        """
        self._f.close()
