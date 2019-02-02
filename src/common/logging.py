import logging


class LevelFormatter(logging.Formatter):
    """
    This class allows to have different logging formats based on the level.
    """
    def __init__(self, formatters=None, fmt=None, datefmt=None, style='%'):
        """
        Initialize the Level Formatter specifying different formats based on the leve
        :param formatters: a dictionary using the logging level as key and the desired format string as value
        :param fmt: refer to the official logging.Formatter documentation for more details
        :param datefmt: refer to the official logging.Formatter documentation for more details
        :param style: refer to the official logging.Formatter documentation for more details
        """

        self._formatters = {}
        if formatters is None:
            # if no formatters are provided, we define the standard ones
            style = '%'
            self._formatters[logging.DEBUG] = logging.Formatter(
                fmt='[%(asctime)s][%(levelname)s]: %(name)s -> %(message)s')
            self._formatters[logging.INFO] = logging.Formatter(
                fmt='[%(asctime)s][%(levelname)s]: %(message)s')
        else:
            # when formatters are available we use them to build the internal dictionary
            for level, fmt in formatters.items():
                self._formatters[level] = logging.Formatter(fmt=fmt, datefmt=datefmt)

        super().__init__(fmt, datefmt, style)

    def format(self, record):
        if record.levelno in self._formatters:
            return self._formatters[record.levelno].format(record)
        else:
            return super().format(record)


def get_logger(name):
    # create logger
    logger = logging.getLogger(name)

    # create console handler and set level to debug
    ch = logging.StreamHandler()

    # create formatter
    formatter = LevelFormatter()

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    return logger
