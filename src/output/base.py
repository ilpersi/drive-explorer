import abc
import csv


class AbstractOutput(abc.ABC):

    @abc.abstractmethod
    def writeheader(self):
        pass

    @abc.abstractmethod
    def writerows(self, rowdicts):
        pass

    @abc.abstractmethod
    def close(self):
        pass


AbstractOutput.register(csv.DictWriter)
