class DriveExplorerException(Exception):
    """Generic Drive Exploter Exception"""
    pass


class CredentialException(DriveExplorerException):
    """Generic Exception with Credentials"""
    pass


class InvalidIdentity(CredentialException):
    """Impossible to find a valid Credential"""
    pass


class InvalidFlow(CredentialException):
    """Impossible to get email from authflow"""
    pass


class AlreadyExistingIdentity(CredentialException):
    """The identity is already existing"""
    pass


class OutputException(DriveExplorerException):
    """Generic Exception with Output"""
    pass


class UnkwonOutputType(OutputException):
    """Unsupported Output type"""
    pass


class NoOuputhPath(OutputException):
    """No Output path specified"""
    pass


def manage_generic_exception(exception, info, sender='unspecified'):
    """This function is to save the details of an unmanaged exception in a pickle file for troubleshooting.
    :param exception: the exception triggered
    :param info: exception context obtained using .format(sender, type(exception).__name__, exception.args, file_name)
    :param sender: the name of the sender. Use this to make the output message more clear to read
    """

    from tblib import pickling_support
    pickling_support.install()
    import pickle
    import os

    exec_info = {'info': info, 'exception': exception}

    file_suffix = 0
    while True:
        try:
            file_name = 'error_details.dat' if file_suffix == 0 else "error_details ({}).dat".format(file_suffix)
            while os.path.isfile(file_name):
                file_suffix += 1
                file_name = 'error_details.dat' if file_suffix == 0 else "error_details ({}).dat".format(file_suffix)

            error_file = open(file_name, 'wb')

            error_file.write(pickle.dumps(exec_info))
            error_file.flush()

            template = "Unhandled exeption detected in {0} process of type {1} occurred.\n" \
                       "Arguments: {2!r}!\n" \
                       "Details of this errors have been saved in file {3}: please send it to the developer.\n"\

            print(template.format(sender, type(exception).__name__, exception.args, file_name))

            break
        except PermissionError:
            file_suffix += 1
