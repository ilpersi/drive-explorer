import json

import output.base


class JsonOutput(output.base.AbstractOutput):
    """
    This class will output the input data in JSON format
    """
    def __init__(self, f):
        """

        :param f: file pointer to the file to be used to write JSON
        """
        self._f = f
        # is it the first time we write to the json output file?
        self._frist_write = True

        self._file_cache = set()

    def writeheader(self):
        """
        This method will start writing to the JSON output file manually creating the outer JSON structure. This
        is done so we don't have to keep in memory a possible big JSON.
        :return:
        """
        self._f.write("{\"files\": [\n  ")

    def writerow(self, rowdict):
        """
        Wrapper around rowdiicts

        :param rowdict: the line that we want to write
        """
        self.writerows((rowdict,))

    def writerows(self, rowdicts):
        """
        Where all the data is written to JSON output.

        :param rowdicts: a list of rows. Each row is a dictionary of data to be written in the output
        """
        json_rows = []
        for row in rowdicts:

            if row['id'] in self._file_cache:
                continue

            json_rows.append(json.dumps(row))
            self._file_cache.add(row['id'])

        # not the first time we write to the output file? Let's be sure that rowdicts are concatenated correctly...
        if not self._frist_write:
            self._f.write(",\n  ")
        else:
            self._frist_write = False

        self._f.write(",\n  ".join(json_rows))

    def close(self):
        """
        Simply closes the underlying file object to make sure no further modifications are made to it

        """
        self._f.write("\n]}")
        self._f.close()
