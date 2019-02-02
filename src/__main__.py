# standard imports
import argparse
import sys

# standard from imports
from multiprocessing import cpu_count, freeze_support

# third parties libraries
import googleapiclient.errors

# libraries import
from commands.folder import FolderExplorer
from commands.credential import GoogleCredential
from common.exceptions import manage_generic_exception
from common.logging import get_logger
from output.writer import supported_types
import common.exceptions


def folder_explorer(explore_args):
    fe = None
    try:
        fe = FolderExplorer(explore_args)
        fe()
    except KeyboardInterrupt:
        logger.warning("Detected Interruption by the user. Cleaning the queue...")
        try:
            fe.clean()
        except AttributeError:
            pass
    except UnboundLocalError:
        pass


def folder_lister(explore_args):
    fl = FolderExplorer(explore_args, False)
    try:
        fl()
    except KeyboardInterrupt:
        logger.warning("Detected Interruption by the user. Cleaning the queue...")
        fl.clean()
    except common.exceptions.OutputException as oe:
        print(oe)


def credential_add_func(explore_args):
    with GoogleCredential(explore_args.credential_file, log_level=explore_args.log_level) as google_cred:
        google_cred.add_credentials(explore_args.make_default)


def credential_list_func(explore_args):
    with GoogleCredential(log_level=explore_args.log_level) as google_cred:
        google_cred.list_credentials()


def credential_del_func(explore_args):
    with GoogleCredential(log_level=explore_args.log_level) as google_cred:
        google_cred.del_credentials(explore_args.user)


def credential_default_func(explore_args):
    with GoogleCredential(log_level=explore_args.log_level) as google_cred:
        google_cred.make_default(explore_args.user)


if __name__ == '__main__':
    freeze_support()

    # TODO Write better documentation for the code
    logger = get_logger(__name__)
    parser = argparse.ArgumentParser(description='Explore Google Drive folders, the easy way.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    defaul_log_lvl = 'INFO'

    subparsers = parser.add_subparsers(title='drive explorer commands', help='available commands help',
                                       dest='command')

    # we add the sub commands to the main parser
    parser_folder = subparsers.add_parser('folder', help='work with folders')
    parser_credential = subparsers.add_parser('credential', help='manage user credentials')

    # sub parsers for the folder command
    subparsers_folder = parser_folder.add_subparsers(help='folder commands help', dest='sub_command')
    folders_explore = subparsers_folder.add_parser('explore', help='recursively explore a folder',
                                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    folders_list = subparsers_folder.add_parser('list', help='list items inside a folder',
                                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # folder explore arguments
    folders_explore.add_argument('-id', '--folder-id', type=str, nargs='*', default=['root'],
                                 help='The id of the folder(s) you want to explore. "My Drive" by default')
    folders_explore.add_argument('-it', '--include-trashed', action='store_true', default=False,
                                 help='Do we want to include trashed files?')
    folders_explore.add_argument('-fm', '--file-match', type=str, default='.*',
                                 help='Python regex to filter the file names. Does not work on folders.')
    folders_explore.add_argument('-cs', '--case-sensitive', action='store_true', default=False,
                                 help='Is the python file match regex case sensitive?')
    folders_explore.add_argument('-tm', '--type-match', type=str, default='.*',
                                 help='Python regex to filter the file types. Does not work on folders.')
    folders_explore.add_argument('-fs', '--folder-separator', type=str, default='\\',
                                 help='folder separator for output file')
    folders_explore.add_argument('-nw', '--num-workers', type=int, default=cpu_count()*2,
                                 help='number of parallel processes')
    folders_explore.add_argument('-u', '--user', type=str, default='',
                                 help='email address to be used')
    folders_explore.add_argument('-o', '--output', type=str, default=None,
                                 help='Path to the output file. Supported formats: {}'
                                 .format(", ".join(sorted(supported_types))))
    folders_explore.add_argument('-cf', '--credential-file', type=str, default='client_id.json',
                                 help='Path to the JSON file containing the configuration in the Google client '
                                      'secrets format')
    folders_explore.add_argument("-l", "--log", dest="log_level", help="Set the logging level", default=defaul_log_lvl,
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    folders_explore.set_defaults(func=folder_explorer)

    # folder list arguments
    folders_list.add_argument('-id', '--folder-id', type=str, nargs='*', default=['root'],
                              help='The id of the folder(s) you want to explore. "My Drive" by default')
    folders_list.add_argument('-it', '--include-trashed', action='store_true', default=False,
                              help='Do we want to include trashed files?')
    folders_list.add_argument('-fm', '--file-match', type=str, default='.*',
                              help='Python regex to filter the file names. Does not work on folders.')
    folders_list.add_argument('-cs', '--case-sensitive', action='store_true', default=False,
                              help='Is the python file match regex case sensitive?')
    folders_list.add_argument('-tm', '--type-match', type=str, default='.*',
                              help='Python regex to filter the file types. Does not work on folders.')
    folders_list.add_argument('-fs', '--folder-separator', type=str, default='\\',
                              help='folder separator for output file')
    folders_list.add_argument('-u', '--user', type=str, default='',
                              help='email address to be used')
    folders_list.add_argument('-o', '--output', type=str, default=None,
                                 help='Path to the output file. Supported formats: {}'
                                 .format(", ".join(sorted(supported_types))))
    folders_list.add_argument('-cf', '--credential-file', type=str, default='client_id.json',
                              help='Path to the JSON file containing the configuration in the Google client '
                                   'secrets format')
    folders_list.add_argument("-l", "--log", dest="log_level", help="Set the logging level", default=defaul_log_lvl,
                              choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    folders_list.set_defaults(func=folder_lister)

    # sub parsers for the credential command
    subparsers_crendential = parser_credential.add_subparsers(help='credential commands help', dest='sub_command')
    credential_add = subparsers_crendential.add_parser('add', help='add a new credential',
                                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    credential_delete = subparsers_crendential.add_parser('delete', help='delete a credential',
                                                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    credential_list = subparsers_crendential.add_parser('list', help='credential list help',
                                                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    credential_default = subparsers_crendential.add_parser('default', help='credential default help',
                                                           formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # credential add arguments
    credential_add.add_argument('-md', '--make-default', action='store_true', default=False,
                                help='Is this going to be the default credential?')
    credential_add.add_argument('-cf', '--credential-file', type=str, default='client_id.json',
                                help='Path to the JSON file containing the configuration in the Google client '
                                     'secrets format')
    credential_add.add_argument("-l", "--log", dest="log_level", help="Set the logging level", default=defaul_log_lvl,
                                choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    credential_add.set_defaults(func=credential_add_func)

    # credential delete arguments
    credential_delete.add_argument('-u', '--user', type=str, required=True, help='email address to be used')
    credential_delete.add_argument("-l", "--log", dest="log_level", help="Set the logging level",
                                   default=defaul_log_lvl,
                                   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    credential_delete.set_defaults(func=credential_del_func)

    # credential list arguments
    credential_list.add_argument("-l", "--log", dest="log_level", help="Set the logging level", default=defaul_log_lvl,
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    credential_list.set_defaults(func=credential_list_func)

    # credential default arguments
    credential_default.add_argument('-u', '--user', type=str, required=True, help='email address to be used')
    credential_default.add_argument("-l", "--log", dest="log_level", help="Set the logging level",
                                    default=defaul_log_lvl,
                                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    credential_default.set_defaults(func=credential_default_func)

    args = parser.parse_args()

    if hasattr(args, 'func'):
        try:
            args.func(args)
        except googleapiclient.errors.HttpError as httpe:
            logger.error("Impossible to run command. APIs ended with the following error: {}".format(str(httpe)))
        except common.exceptions.InvalidIdentity as ie:
            logger.warning(ie)
        except common.exceptions.AlreadyExistingIdentity as ae:
            logger.warning(ae)
        except KeyboardInterrupt:
            logger.warning("Detected Keboard interrupt by the user...")
        except common.exceptions.OutputException as oe:
            logger.warning(oe)
        except Exception as e:
            manage_generic_exception(e, sys.exc_info(), "drive_explorer")
    else:
        # we should print the right help info
        if args.command is None:
            parser.print_help()
        elif args.command == 'folder':
            if args.sub_command is None:
                parser_folder.print_help()
            elif args.sub_command == 'explore':
                folders_explore.print_help()
        elif args.sub_command == 'list':
                folders_list.print_help()
        elif args.command == 'credential':
            if args.sub_command is None:
                parser_credential.print_help()
            elif args.sub_command == 'add':
                credential_add.print_help()
            elif args.sub_command == 'delete':
                credential_delete.print_help()
            elif args.sub_command == 'list':
                credential_list.print_help()
            elif args.sub_command == 'default':
                credential_default.print_help()
