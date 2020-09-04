import traceback


class BespokeFitException(Exception):
    """
    Base BespokeFit exception, should always use the appropriate subclass of this exception.
    """

    error_type = "base_error"
    header = "BespokeFit Base Error"

    def __init__(self, message: str):

        super().__init__(message)

        self.raw_message = message
        self.traceback = traceback.format_exc()

    @property
    def error_message(self) -> str:
        return f"{self.header}: {self.raw_message}"


class TargetRegisterError(BespokeFitException):
    """
    The registering the target raised an error.
    """

    error_type = "target_register_error"
    header = "BespokeFit Target Register Error"


class FragmenterError(BespokeFitException):
    """
    The molecule could not be fragmented correctly.
    """

    error_type = "fragmeneter_error"
    header = "BespokeFit Fragmenter Error"


class DihedralSelectionError(BespokeFitException):
    """
    The dihedrals selected are not valid in some way.
    """

    error_type = "dihedral_selection_error"
    header = "BespokeFit Dihedral Selection Error"


class MissingReferenceError(BespokeFitException):
    """
    Raised when the target is attempted to be fit before all of the reference data has been assigned.
    """

    error_type = "missing_reference_error"
    header = "BespokeFit Missing Reference Error"


class OptimizerError(BespokeFitException):
    """
    Raised when the Optimizer can not be found.
    """

    error_type = "optimizer_error"
    header = "BespokeFit Optimizer Error"
