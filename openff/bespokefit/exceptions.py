"""Custom exceptions for BespokeFit."""
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
        """Format this error as a message."""
        return f"{self.header}: {self.raw_message}"


class TargetRegisterError(BespokeFitException):
    """
    Registering the target raised an error.
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
    Raised when the optimizer can not be found.
    """

    error_type = "optimizer_error"
    header = "BespokeFit Optimizer Error"


class WorkflowUpdateError(BespokeFitException):
    """
    Raised when the optimization workflow can not be updated.
    """

    error_type = "workflow_update_error"
    header = "Workflow Update Error"


class TargetNotSetError(BespokeFitException):
    """
    Raised when the target is referenced but not set.
    """

    error_type = "target_not_set_error"
    header = "Target Not Set Error"


class ForceFieldError(BespokeFitException):
    """
    Raised if the forcefield has an incorrect format or can not be loaded.
    """

    error_type = "force_field_error"
    header = "Force Field Error"


class SMIRKSTypeError(BespokeFitException):
    """
    Raised when an incorrect smirks pattern is used to make a SMIRKS schema, eg tagged one atom in a bond smirks.
    """

    error_type = "smirks_type_error"
    header = "SMIRKS Type Error"


class MissingWorkflowError(BespokeFitException):
    """
    Raised when we try and complete a fitting entry that has no workflow set.
    """

    error_type = "missing_workflow_error"
    header = "Missing Workflow Error"


class MoleculeMissMatchError(BespokeFitException):
    """
    Raised when two molecules do not match in a results update.
    """

    error_type = "molecule_miss_match_error"
    header = "Molecule Miss Match Error"


class TaskMissMatchError(BespokeFitException):
    """
    Raised when a task type and collection workflow do not match.
    """

    error_type = "task_miss_match_error"
    header = "Task Miss Match Error"


class QCRecordMissMatchError(BespokeFitException):
    """
    Raised when a QC record does not contain the expected information, such as gradient or hessian values.
    """

    error_type = "qc_record_miss_match_error"
    header = "QC Record Miss Match Error"


class MissingTorsionTargetSMARTS(BespokeFitException):
    """
    Raised when a workflow is fitting torsions but has no way to determine which ones.
    """

    error_type = "missing_torsion_target_smarts"
    header = "Missing Torsion Target SMARTS"
