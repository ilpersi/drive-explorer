# standard imports
import pickle
import sqlite3

# third parties from imports
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# libraries import
from common.backoff import call_endpoint
from common.exceptions import InvalidFlow, InvalidIdentity, AlreadyExistingIdentity
from common.logging import get_logger

# sqlite connection configuration. We want to be sure that booleans are correctly converted
sqlite3.register_adapter(bool, int)
sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))
logger = get_logger(__name__)


class GoogleCredential:
    def __init__(self, client_secrets_file=None, user=None, scopes=None, log_level='INFO'):
        """
        This class is used to manage the Google authentication in the various commands.
        The intended way to use it is within a context manager using the "with" statement

        :param client_secrets_file: is the path to file holding the client secret
        :param user: email of the user that we'll use to perform operations
        :param scopes: the required scopes
        :param log_level: the desired log level
        """
        self._user = user
        if scopes is None:
            self._scopes = ['https://www.googleapis.com/auth/drive.readonly',    # to explore folders
                            'https://www.googleapis.com/auth/drive.file',        # to create gsheets if required
                            'https://www.googleapis.com/auth/userinfo.email',    # to read profile info
                            'https://www.googleapis.com/auth/userinfo.profile',  # to read profile info
                            ]
        else:
            self._scopes = [x for x in scopes]

        self._client_secrets_file = client_secrets_file

        self._credentials = None
        self._email_address = None

        logger.setLevel(log_level)

    def __enter__(self):
        self._conn = sqlite3.connect(r"./drive_explorer.sqlite3", detect_types=sqlite3.PARSE_DECLTYPES)
        self._cur = self._conn.cursor()

        # this table is used to store user credentials. We make sure it exists
        create_sql = """CREATE TABLE IF NOT EXISTS credentials (
                            email        TEXT PRIMARY KEY UNIQUE NOT NULL,
                            credentials  BLOB   NOT NULL,
                            default_cred BOOLEAN
                        );
                     """

        self._cur.execute(create_sql)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # we commit and close the connection
        self._conn.commit()
        self._cur.close()
        self._conn.close()

    def _do_flow(self):
        # where the authentication really takes place
        flow = InstalledAppFlow.from_client_secrets_file(self._client_secrets_file, self._scopes)
        self._credentials = flow.run_local_server()

        # to save the information in the sqlite database we use the email as a key, so we need to retrieve it
        self._people_sdk = build('people', 'v1', credentials=self._credentials)
        people_get_params = {
            'resourceName': 'people/me',
            'personFields': 'emailAddresses',
            'fields': 'emailAddresses(metadata/primary,value)',
        }
        user_details = call_endpoint(self._people_sdk.people().get, people_get_params)
        for email in user_details.get('emailAddresses', []):
            if email['metadata']['primary']:  # it is possible that more than one email is available, se use primary
                self._email_address = email['value']
                break
        else:
            raise InvalidFlow("Impossible to find email address from Google API: {}".format(user_details))

    def get_credentials(self):
        if not self._user:
            # if no user is present, we try to get the default credential
            sql_select = """SELECT email, credentials FROM credentials WHERE default_cred=?"""
            sql_results = self._cur.execute(sql_select, (True,))

            # we assume only one credential is the default one
            for row in sql_results:
                self._email_address, credentials_str = row
                self._credentials = pickle.loads(credentials_str)

                if self._credentials.expired:
                    # if the credential is expired, we update so that all the child processs can use it
                    self._credentials.refresh(Request())
                    credentials_str = pickle.dumps(self._credentials)

                    sql_update = """UPDATE credentials SET credentials = ? WHERE default_cred=?"""
                    self._cur.execute(sql_update, (credentials_str, True))

                logger.info("Using default credentials: {}".format(self._email_address))
                break
            else:
                # no results found, we trigger the auth flow
                logger.info("No default user found, please proceed with authentication...")
                self._do_flow()
                credentials_str = pickle.dumps(self._credentials)

                sql_insert = """INSERT into credentials (email, credentials, default_cred) VALUES (?,?,?)"""
                self._cur.execute(sql_insert, (self._email_address, credentials_str, True))
        else:
            sql_select = """SELECT credentials FROM credentials where email=?"""
            sql_results = self._cur.execute(sql_select, (self._user,))

            for row in sql_results:
                credentials_str = row[0]
                self._email_address = self._user
                self._credentials = pickle.loads(credentials_str)

                if self._credentials.expired:
                    self._credentials.refresh(Request())
                    credentials_str = pickle.dumps(self._credentials)

                    sql_update = """UPDATE credentials SET credentials = ? WHERE email=?"""
                    self._cur.execute(sql_update, (credentials_str, self._user))

                logger.debug("Found credentials: {}".format(self._email_address))
                break
            else:
                raise InvalidIdentity("No credentails are available for: {}. "
                                      "Use the credential command to generate them.".format(self._user))

        return self._email_address, self._credentials

    def add_credentials(self, default=False):
        self._do_flow()

        # we make sure that no credentials exist already for the found email address
        sql_select = """SELECT COUNT(credentials) FROM credentials where email=?"""
        self._cur.execute(sql_select, (self._email_address,))
        (number_of_rows,) = self._cur.fetchone()

        if number_of_rows > 0:
            raise AlreadyExistingIdentity("Credentials are already present for user {}.".format(self._email_address))

        # if the new credential is going to be the default one, we need to make sure that no other one is default
        if default:
            sql_update = """UPDATE credentials SET default_cred = ? WHERE default_cred=?"""
            self._cur.execute(sql_update, (False, True))

        sql_insert = """INSERT into credentials (email, credentials, default_cred) VALUES (?,?,?)"""
        self._cur.execute(sql_insert, (self._email_address, pickle.dumps(self._credentials), default))
        if default:
            logger.info("Added default credentials for email: {}".format(self._email_address))
        else:
            logger.info("Added credentials for email: {}".format(self._email_address))

    def del_credentials(self, email):
        sql_delete = """DELETE FROM credentials WHERE email=?"""
        self._cur.execute(sql_delete, (email,))

        number_of_rows = self._cur.rowcount

        if number_of_rows == 0:
            logger.info("Credentials for {} not present in the database.".format(email))
        elif number_of_rows == 1:
            logger.info("Credentials for {} deleted.".format(email))
        else:
            raise ValueError("More than one credential found for {}.".format(email))

    def list_credentials(self):
        sql_select = """SELECT email, default_cred FROM credentials ORDER BY email"""

        credentials = self._cur.execute(sql_select).fetchall()
        max_len = max(len(x[0]) for x in credentials)

        # we try to format the output list in a nice way
        print("+-{email:-<{width}}-+-{default:-<7}-+".format(email="", width=max_len, default=""))
        print("| {email: <{width}} | {default: <7} |".format(email="Email", width=max_len, default="Default"))
        print("+-{email:-<{width}}-+-{default:-<7}-+".format(email="", width=max_len, default=""))
        for cred in credentials:
            print("| {email: <{width}} | {default: >7} |".format(email=cred[0], width=max_len,
                                                                 default="Y" if cred[1] else "N"))
            print("+-{email:-<{width}}-+-{default:-<7}-+".format(email="", width=max_len, default=""))

    def make_default(self, email):
        # we make sure that no credentials exist already for the found email address
        sql_select = """SELECT COUNT(credentials) FROM credentials where email=?"""
        self._cur.execute(sql_select, (email,))
        (number_of_rows,) = self._cur.fetchone()

        if number_of_rows == 0:
            raise InvalidIdentity("No credentials found present for user {}.".format(email))
        elif number_of_rows == 1:
            # if the new credential is going to be the default one, we need to make sure that no other one is default
            sql_update = """UPDATE credentials SET default_cred = ? WHERE default_cred=?"""
            self._cur.execute(sql_update, (False, True))
            sql_update = """UPDATE credentials SET default_cred = ? WHERE email=?"""
            self._cur.execute(sql_update, (True, email))
            logger.info("Credentails for {} are now the default ones".format(email))
        else:
            raise ValueError("More than one credential found for {}.".format(email))
