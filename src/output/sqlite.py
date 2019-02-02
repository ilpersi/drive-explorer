import sqlite3
from datetime import datetime
from io import StringIO
from itertools import islice

import output.base
from common.logging import get_logger

logger = get_logger(__name__)


def chunk(it, size=100):
    # https://stackoverflow.com/a/22045226/1280443
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())


class SQLiteOutput(output.base.AbstractOutput):
    def __init__(self, f, fieldnames, log_level):
        self._fieldnames = fieldnames
        self._log_level = log_level

        self._table_prefix = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')

        # table names
        self._files_table_name = "{}_files".format(self._table_prefix)
        self._permissions_table_name = "{}_permissions".format(self._table_prefix)
        self._parents_table_name = "{}_parents".format(self._table_prefix)
        self._editors_table_name = "{}_editors".format(self._table_prefix)

        # sqlite connection
        self._con = sqlite3.connect(f, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self._cur = self._con.cursor()

        self._ignore_files = set()
        self._ignore_fields = set()
        self._permissions_cache = {}

        logger.setLevel(self._log_level)

        self._file_cache = set()

    def writeheader(self):
        # headers with a format different from TEXT
        header_type = {
            'id': 'TEXT PRIMARY KEY UNIQUE NOT NULL',
            'size': 'INTEGER',
            'trashed': 'BOOLEAN',
            'createdTime': 'TIMESTAMP',
            'modifiedTime': 'TIMESTAMP'
        }

        # permissions and parents are managed with dedicated associative tables
        self._ignore_fields = {'permissions', 'parents', 'internal_folder'}

        # this table will contain the different permission sets
        permission_create_sql = """CREATE TABLE '{}' (
            id                 INTEGER    PRIMARY KEY,
            type               TEXT       NOT NULL,
            email              TEXT       DEFAULT '',
            domain             TEXT       DEFAULT '',
            role               TEXT       NOT NULL,
            allow_discovery    BOOLEAN,
            UNIQUE (type, email, domain, role, allow_discovery)
        );""".format(self._permissions_table_name)

        # this table is an association of the permissions with the files
        editors_create_sql = """CREATE TABLE '{}' (
            file_id          TEXT       NOT NULL ,
            permission_id    INTEGER    NOT NULL ,
            PRIMARY KEY (file_id, permission_id)
        );""".format(self._editors_table_name)

        # this table is an association between drive folders and drive files
        parents_create_sql = """CREATE TABLE '{}' (
            parent_id    TEXT   NOT NULL ,
            file_id      TEXT   NOT NULL ,
            PRIMARY KEY (parent_id, file_id)
        );""".format(self._parents_table_name)

        # files table, fields are added dynamically unless a specific type is present in the header_type dict
        files_create_sql = "CREATE TABLE '{}' (\n".format(self._files_table_name)
        for field_cnt, field_name in enumerate(self._fieldnames):

            if field_name in self._ignore_fields:
                continue

            sql_type = header_type.get(field_name, "TEXT")

            if field_cnt > 0:
                files_create_sql += ",\n"

            files_create_sql += "  {}  {}".format(field_name, sql_type)

        files_create_sql += "\n);"

        self._cur.execute(editors_create_sql)
        self._cur.execute(permission_create_sql)
        self._cur.execute(parents_create_sql)
        self._cur.execute(files_create_sql)
        self._con.commit()

    def writerows(self, rowdicts):

        field_transform = {
            'size': lambda x: int(x) if x is not None else 0,
            'trashed': lambda x: bool(x) if x is not None else False,
            # RFC 3339 timestamps '2018-04-30T05:16:22.797Z'
            'createdTime': lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S.%fZ"),
            'modifiedTime': lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S.%fZ"),
        }

        # files table management
        files_fields = tuple(x for x in rowdicts[0].keys() if x not in self._ignore_fields)

        # There seems to be a limit with the number of ? in instert statements, this is why rows are inserted in chunks
        self._cur.execute('BEGIN TRANSACTION')
        for row_set in chunk(rowdicts):

            # files INSERT statement preparation
            files_value_list = []
            files_insert_sql = StringIO()

            files_insert_sql.write("INSERT INTO '{}' \n".format(self._files_table_name))
            files_insert_sql.write("({})\n".format(", ".join(files_fields)))
            files_insert_sql.write("VALUES ")

            # parents INSERT statement preparation
            parents_value_list = []
            parents_insert_sql = StringIO()
            parents_insert_sql.write("INSERT INTO '{}' \n".format(self._parents_table_name))
            parents_insert_sql.write("(parent_id, file_id)\n")
            parents_insert_sql.write("VALUES ")

            for cnt, row in enumerate(row_set):
                # as folders can have more than one parent and are processed in parallel, this is the only possible way
                # to avoid duplicate file IDs
                if row['id'] in self._file_cache:
                    continue

                self._file_cache.add(row['id'])

                # permissions and parents are managed differently, so we pop them from the row
                permissions = row.pop('permissions')
                parents = row.pop('parents')

                # if it is not the first row, we might need a comma in the files INSERT statement(s)
                if cnt > 0:
                    # to append the comma we need to check if any previous value is already present
                    if files_value_list:
                        files_insert_sql.write(", ")  # FILES

                    if parents_value_list:
                        parents_insert_sql.write(", ")  # PARENTS

                for permission in permissions:
                    permission_type = permission.get("type", None)
                    permission_email = permission.get("emailAddress", "")
                    permission_domain = permission.get("domain", "")
                    permission_role = permission.get("role", None)
                    permission_allow_discovery = permission.get('allowFileDiscovery', False)
                    permission_key = "{}-{}-{}-{}-{}" \
                        .format(permission_type, permission_email, permission_domain, permission.get("role", None),
                                permission.get('allowFileDiscovery', False))

                    # sometimes you have stub user permissions that will break the UNIQUE constraints
                    # user permissions with no email are not shown in the UI, so skipping them
                    if permission_type == "user" and len(permission_email) == 0:
                        continue

                    if permission_key in self._permissions_cache:
                        permission_id = self._permissions_cache[permission_key]
                    else:
                        permission_select_sql = StringIO()
                        permission_select_sql.write("SELECT id FROM '{}'\n".format(self._permissions_table_name))
                        permission_select_sql.write("WHERE type=? AND email =? AND domain =? AND role=? "
                                                    "AND allow_discovery =?")
                        permission_select_values = (permission_type, permission_email, permission_domain,
                                                    permission_role, permission_allow_discovery)
                        self._cur.execute(permission_select_sql.getvalue(), permission_select_values)
                        permission_result = self._cur.fetchall()
                        if len(permission_result) == 0:
                            permission_insert_sql = StringIO()
                            permission_insert_sql.write(
                                "INSERT INTO '{}'\n".format(self._permissions_table_name))
                            permission_insert_sql.write("(type, email, domain, role, allow_discovery)\n")
                            permission_insert_sql.write("VALUES (?, ?, ?, ?, ?)\n")
                            permission_insert_values = (permission_type, permission_email, permission_domain,
                                                        permission_role, permission_allow_discovery)
                            self._cur.execute(permission_insert_sql.getvalue(), permission_insert_values)
                            permission_id = self._cur.lastrowid
                        elif len(permission_result) == 1:
                            permission_id = permission_result[0][0]
                        else:
                            raise ValueError("Unexpected number of results for query: {}".
                                             format(permission_select_sql.getvalue()))

                        self._permissions_cache[permission_key] = permission_id

                    editors_insert_sql = StringIO()
                    editors_insert_sql.write("INSERT INTO '{}'\n".format(self._editors_table_name))
                    editors_insert_sql.write("(file_id, permission_id)\n")
                    editors_insert_sql.write("VALUES (?, ?)")
                    editors_insert_values = (row['id'], permission_id)

                    self._cur.execute(editors_insert_sql.getvalue(), editors_insert_values)

                # PARENTS
                parents_value_str = StringIO()
                parents_value_str_len = 0
                for file_parent in parents:
                    if parents_value_str_len > 0:
                        parents_value_str_len += parents_value_str.write(",")

                    parents_value_str_len += parents_value_str.write("(?, ?)")
                    parents_value_list.extend((file_parent, row['id']))

                # FILES
                files_values_str = StringIO()
                files_values_str_len = 0
                files_values_str_len += files_values_str.write("(")  # files_values_str_len is now == 1
                for files_field in files_fields:

                    # we are appending a new field, so we must insert a comma before
                    if files_values_str_len > 1:
                        files_values_str_len += files_values_str.write(", ")

                    files_values_str_len += files_values_str.write("?")

                    # we transform the values before inserting them
                    etl_func = field_transform.get(files_field, lambda x: str(x) if x is not None else '')
                    files_value_list.append(etl_func(row[files_field]))

                # we finalize the files VALUES string
                files_values_str_len += files_values_str.write(")")

                # we append the VALUES part to the INSERT statement(s)
                files_insert_sql.write(files_values_str.getvalue())
                parents_insert_sql.write(parents_value_str.getvalue())

            # try:
            #     # it may be possible that all the rows are skipped as they are already in the case, in this case
            #     # we skip the INSERT operation
            if files_value_list:
                self._cur.execute(files_insert_sql.getvalue(), files_value_list)
            # except sqlite3.OperationalError as oe:
            #     pass
            # except sqlite3.IntegrityError as ie:
            #     pass

            # if no file has been processed, parents are also empty and so we skip them
            if parents_value_list:
                self._cur.execute(parents_insert_sql.getvalue(), parents_value_list)
            # except sqlite3.IntegrityError as ie:
            #     if 'UNIQUE constraint failed: ' + self._files_table_name + '.id' in str(ie):
            #         logger.error('UNIQUE constraint failed: ' + self._files_table_name + '.id' in str(ie))
            #     elif 'UNIQUE constraint failed: ' + self._editors_table_name + '.id' in str(ie):
            #         print("Editors Error Details File ID: {} permissions: {}".format(row['id'], permissions))

        self._cur.execute('COMMIT')
        self._con.commit()

    def close(self):
        self._con.close()
