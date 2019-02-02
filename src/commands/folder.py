# standard imports
import multiprocessing
import os.path
import re

# standard from imports
from datetime import datetime

# third parties libraries
import googleapiclient.errors

# third parties from imports
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# libraries import
import output.writer
from common.drive_utils import FolderConsumer
from common.backoff import call_endpoint
from commands.credential import GoogleCredential
from common.logging import get_logger
from common.exceptions import UnkwonOutputType, NoOuputhPath
from output.writer import OutputWriter

logger = get_logger(__name__)


class FolderExplorer:
    def __init__(self, args, recursive=True):
        """
        This class is used to explore Google Drive folders. If the recursive flag is set to True, all the the tree
        of folders will be explored. The args argument contains the command line parameters passed by the user
        """
        self._args = args
        self._recursive = recursive

        # is the file search pattern case sensitive?
        if args.case_sensitive:
            self._file_re = re.compile(args.file_match, re.DOTALL)
        else:
            self._file_re = re.compile(args.file_match, re.IGNORECASE | re.DOTALL)

        # sanity check on the output format. It has to be declared and it has to be supported
        if args.output is None:
            raise NoOuputhPath("No output path specified. Please refer to the -o/--output parameter")
        else:
            _, self._output_extension = os.path.splitext(args.output)
            if self._output_extension not in output.writer.supported_types:
                raise UnkwonOutputType("Output format not supported: {}. Use one of the following ones: {}."
                                       .format(self._output_extension, ", ".join(output.writer.supported_types)))

        # file type search pattern
        self._type_re = re.compile(args.type_match, re.DOTALL)

        # queue used to manage folders to be explored between processes
        self._unsearched = multiprocessing.JoinableQueue()

        # to manage the results of the exploration process we use a shared list
        manager = multiprocessing.Manager()
        self._results = manager.list()
        self._results_lock = manager.Lock()
        self._child_errors = manager.Value('B', 0)
        # used to signal to the output writing process that all the workers are done with exploring folders
        self._results_finished = multiprocessing.Event()

        # list used hold all the child workers
        self._workers = []
        self._writer = None

        logger.setLevel(args.log_level)

        with GoogleCredential(args.credential_file, self._args.user, log_level=args.log_level) as google_cred:
            self._email, self._credentials = google_cred.get_credentials()

        # we renew the credentials in the main process so that the childs do not need to do it
        if self._credentials.expired:
            self._credentials.refresh(Request())

        self._drive_sdk = build('drive', 'v3', credentials=self._credentials)

    def __call__(self):

        # folder list command olny requires one worker
        num_workers = self._args.num_workers if self._recursive else 1

        dt_start = datetime.now()
        logger.debug("Starting {} processes...".format(num_workers))
        # child processes that will explore the folder tree
        self._workers = [
            FolderConsumer(self._unsearched, self._results, self._results_lock, self._email,
                           self._args.credential_file, self._file_re, self._type_re, self._args.log_level,
                           self._args.folder_separator, self._args.include_trashed, self._recursive)
            for _ in range(num_workers)]

        # one more child process that will take care of writing the output to the desired targed while the exploring
        # workers are traversing the folders
        self._writer = OutputWriter(self._results, self._results_lock, self._results_finished, self._args.output,
                                    self._output_extension, self._args.log_level, self._email,
                                    self._args.credential_file)

        # for all the folders to explore, we get info
        for drive_folder in self._args.folder_id:
            drive_get_params = {
                'fileId': drive_folder,
                'supportsTeamDrives': True,
                'fields': 'id,name',
            }

            # we make sure that all the folders can be browsed
            try:
                root_folder_details = call_endpoint(self._drive_sdk.files().get, drive_get_params)
                self._unsearched.put(root_folder_details)
            except googleapiclient.errors.HttpError as httpe:
                httpe_str = str(httpe)
                # we manage the file not found error and rise the others
                if "File not found:" in httpe_str:
                    logger.error("Folder not found: {}".format(drive_folder))
                    continue
                else:
                    raise httpe

        # we start the output writer and then the child processes
        self._writer.start()
        for worker in self._workers:
            worker.start()

        # we wait for all the folders to be explored
        self._unsearched.join()

        # poison pill to make the child processes break
        # sometime one or more childs may chrash, so we only create poison pills for alive processes
        for worker in self._workers:
            if worker.is_alive():
                self._unsearched.put(None)

        # we wair for all the child processes to actually break
        self._unsearched.join()
        for worker in self._workers:
            worker.join()

        # we send the signal to the writer proces
        self._results_finished.set()
        self._writer.join()

        logger.info("Elapsed time: {}".format(datetime.now() - dt_start))

    def clean(self):
        """Used to clean pending processes."""
        for worker in self._workers:
            if worker is not None:
                try:
                    worker.terminate()
                except (OSError, AttributeError):
                    pass
                finally:
                    worker.join()

        if self._writer is not None:
            try:
                self._writer.terminate()
            except (OSError, AttributeError):
                pass
            finally:
                self._writer.join()
