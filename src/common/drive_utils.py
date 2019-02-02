# standard imports
import multiprocessing
import os
import sys

# third parties from imports
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# libraries import
from common.backoff import execute_request
from common.exceptions import manage_generic_exception
from commands.credential import GoogleCredential
from common.logging import get_logger

logger = get_logger(__name__)


def permissions_to_string(file_id, drive_permissions):
    """
    Takes care of transforming the standard permission JSON in a human readable format.

    :param file_id: the Google Drive file of the ID to which the permissions are referring
    :param drive_permissions: the standard permission JSON
    :return: a dictionary with the key representing the role
    """
    result = {
        'owners': '',
        'can_edit': '',
        'can_comment': '',
        'can_view': '',
    }

    for permission in drive_permissions:
        permission_type = permission.get('type', None)

        if permission_type == 'user' or permission_type == 'group':
            permission_email = permission.get('emailAddress', False)
        elif permission_type == 'domain':
            permission_domain = permission.get('domain', 'error')
            permission_discovery = permission.get('allowFileDiscovery', None)
            permission_with_link = ' with the link' if not permission_discovery else ''
            permission_email = 'Anyone in {}{}'.format(permission_domain, permission_with_link)
        elif permission_type == 'anyone':
            permission_domain = 'Anyone on the web'
            permission_discovery = permission.get('allowFileDiscovery', None)
            permission_with_link = ' with the link' if not permission_discovery else ''
            permission_email = '{}{}'.format(permission_domain, permission_with_link)
        else:
            permission_email = 'ERROR'
            logger.error('Unknown type {}'.format(permission_type, file_id))

        permission_role = permission.get('role', None)

        if permission_role == 'owner':
            result['owners'] += ', {}'.format(permission_email) if result['owners'] else permission_email
        elif permission_role == 'writer':
            result['can_edit'] += ', {}'.format(permission_email) if result['can_edit'] else permission_email
        elif permission_role == 'commenter':
            result['can_comment'] += ', {}'.format(permission_email) if result['can_comment'] else permission_email
        elif permission_role == 'reader':
            result['can_view'] += ', {}'.format(permission_email) if result['can_view'] else permission_email
        else:
            logger.error('Unknown role {} for email {} on file {}'
                         .format(permission_role, permission_email, file_id))

    return result


class FolderConsumer(multiprocessing.Process):
    def __init__(self, task_queue, results_list, results_lock, email, credential_file, file_match,
                 type_match, log_level, folder_separator=os.sep, include_trashed=False, recursive=True):
        """
        This is the class used by the child processes to explore the Google Drive folders

        :param task_queue: the queue from which the processes take the folders to be explored
        :param results_list: once the exploration is over, the data to be extracted is saved in this list
        :param results_lock: lock used to access the result_list
        :param email: the email address of the current credeltials
        :param credential_file: the credential file of the project
        :param file_match: the regex to look for files
        :param type_match: the regex to look for file types
        :param log_level: the logging level (see the standar python logging module)
        :param folder_separator: the character used as folder separator (defaults to os.sep)
        :param include_trashed: should trashed items be included in the research?
        :param recursive: should the explore work recursevly on folders?
        """

        super().__init__(daemon=False)

        self._task_queue = task_queue
        self._result_list = results_list
        self._result_lock = results_lock
        self._user = email
        self._credential_file = credential_file
        self._file_match = file_match
        self._type_match = type_match
        self._log_level = log_level
        self._folder_separator = folder_separator
        self._include_trashed = include_trashed
        self._recursive = recursive

        self._credentials = None

    def run(self):
        """
        This is a wrapper around the real run to better catch any possible exception in the child processes

        :return: None
        """
        logger.setLevel(self._log_level)
        try:
            self._safe_run()
        except KeyboardInterrupt as ke:
            logger.debug("KeyboardInterrupt in FolderConsumer.run".format(ke))
        except Exception as e:
            manage_generic_exception(e, sys.exc_info(), "FolderConsume.run")

    def _safe_run(self):
        """
        This is the real run method

        :return: None
        """

        # we get the credentials
        with GoogleCredential(self._credential_file, self._user, log_level=self._log_level) as google_cred:
            email, self._credentials = google_cred.get_credentials()

        # we renew the credentials if required
        if self._credentials.expired:
            self._credentials.refresh(Request())

        # used to hold results before synching them to the result shared list()
        result_buffer = []

        while True:

            next_task = self._task_queue.get()
            logger.debug("Next task is: {}".format(next_task))

            if next_task is None:
                # Poison pill means shutdown
                logger.debug('{}: Exiting'.format(self.name))

                self._task_queue.task_done()
                if len(result_buffer) > 0:
                    with self._result_lock:
                        self._result_list.extend(result_buffer)
                    result_buffer.clear()
                break

            if len(result_buffer) > 1_000:
                # we dump everything to the sared results
                with self._result_lock:
                    self._result_list.extend(result_buffer)
                logger.debug("self._result_list size from drive_utils: {}".format(len(self._result_list)))
                result_buffer.clear()

            # we explore the folder
            drive_worker = DriveWorker(next_task, self._credentials, self._file_match, self._type_match,
                                       self._folder_separator, self._include_trashed, self._recursive)
            files_and_folders = drive_worker()

            # files are appended to the results
            for file in files_and_folders.get('files', []):
                result_buffer.append(file)

            # folders are queued to be explored
            for folder in files_and_folders.get('folders', []):
                logger.debug("Process {} Added child folder {} form task: {}".format(self, folder, next_task))
                self._task_queue.put(folder)

            self._task_queue.task_done()


class DriveWorker:
    def __init__(self, next_task, credentials, file_match, type_match, folder_separator=os.sep, include_trashed=False,
                 recursive=True):
        """
        This class will call the Google APIs and get the files in the folders

        :param next_task: the folder to explore
        :param credentials: the credentials to be used to call Google APIs
        :param file_match: the regex to match file names
        :param type_match: the regex to match the file type
        :param folder_separator: the folder separator character, defaults to os.sep
        :param include_trashed: should trashed items be scanned?
        :param recursive: are we going to traverse folders recursively?
        """

        self._next_task = next_task
        self._credentials = credentials
        self._file_match = file_match
        self._type_match = type_match
        self._folder_separator = folder_separator
        self._include_trashed = include_trashed
        self._recursive = recursive

        if self._credentials.expired:
            self._credentials.refresh(Request())

        # Properties used outside the init
        self._drive_sdk = build('drive', 'v3', credentials=self._credentials)

    def _list_files(self, root_folder_id, trashed=False):
        """
        Internal method used to call the Google API

        :param root_folder_id: the folder to explore
        :param trashed: should trashed items be explored?
        :return: a list containing all the results from the Google APIs
        """
        trashed_str = 'true' if trashed else 'false'

        # https://developers.google.com/drive/api/v3/reference/files/list
        # https://developers.google.com/drive/api/v3/performance#partial
        # https://developers.google.com/apis-explorer/#p/drive/v3/drive.files.list
        page_size = 1000
        drive_list_params = {
            'pageSize': page_size,
            'q': "'{}' in parents and trashed = {}".format(root_folder_id, trashed_str),
            'orderBy': 'name',
            'fields': 'files(id,mimeType,name,size,trashed,teamDriveId,'
                      'createdTime,modifiedTime,parents,webViewLink,'
                      'permissions(allowFileDiscovery,domain,emailAddress,role,type)),'
                      'nextPageToken',
            'supportsTeamDrives': True,
            'includeTeamDriveItems': True,
        }

        g_drive_files = self._drive_sdk.files()
        list_request = g_drive_files.list(**drive_list_params)

        folder_files = []
        while list_request is not None:
            # all the paginated results are queued in one single list
            folder_items = execute_request(list_request)
            folder_files.extend(folder_items.get('files', []))
            list_request = g_drive_files.list_next(list_request, folder_items)

        return folder_files

    def __call__(self):
        """
        This method calls the Google API and transform the results to feed the writer process. Any filter specified by
        the user (on file name and/or type) is applied here

        :return: a dictionary with two keys: files and folders. The first for drive files and the second for drive
        folders. The distinction is made using the mimeType
        """
        folder_id = self._next_task.get('id')
        folder_full_name = self._next_task.get('name')

        logger.debug('[{}] Exploring folder {} -> {}'.format(self, folder_id, folder_full_name))
        folder_files = []

        # we get the list of files
        folder_files.extend(self._list_files(folder_id))

        # we also take care of trashed items
        if self._include_trashed:
            logger.info('{}: Including trashed files for folder '.format(folder_id))
            folder_files.extend(self._list_files(folder_id, True))

        #
        results = {'files': [], 'folders': []}
        for gdrive_file in folder_files:
            gdrive_file_id = gdrive_file.get('id', '')

            new_file = {
                'id': gdrive_file_id,
                'mimeType': gdrive_file.get('mimeType'),
                'name': "{}{}{}".format(folder_full_name, self._folder_separator, gdrive_file.get('name')),
                'size': gdrive_file.get('size'),
                'trashed': gdrive_file.get('trashed'),
                'teamDriveId': gdrive_file.get('teamDriveId'),
                'createdTime': gdrive_file.get('createdTime'),
                'modifiedTime': gdrive_file.get('modifiedTime'),
                'parents': gdrive_file.get('parents'),
                'url': gdrive_file.get('webViewLink'),
                'permissions': gdrive_file.get('permissions', {}),
            }

            # we check the the file names matches the user settings
            if self._file_match.search(gdrive_file.get('name')) \
                    and self._type_match.search(gdrive_file.get('mimeType')):
                results['files'].append(new_file)

            # if the file is a folder and the explore process is recursive, we add the folder to the results
            if gdrive_file.get('mimeType') == 'application/vnd.google-apps.folder' and self._recursive:
                new_folder = {
                    'id': gdrive_file_id,
                    'name': "{}{}{}".format(folder_full_name, self._folder_separator, gdrive_file.get('name')),
                }
                results['folders'].append(new_folder)
                logger.debug("New folder added to the results: {}".format(new_folder))

        return results

    # def __repr__(self):
    #     return "DriveWorker for {}".format(self._next_task)
