from typing import Generic, List, Tuple, TypeVar, overload

import numpy as np
from openff.toolkit.topology import Molecule
from pydantic import Field
from pydantic.generics import GenericModel
from qcelemental.models import AtomicResult
from qcelemental.models.common_models import Model
from qcelemental.models.procedures import (
    OptimizationResult,
    OptimizationSpecification,
    QCInputSpecification,
    TorsionDriveResult,
)
from qcportal.models import TorsionDriveRecord
from qcportal.models.records import OptimizationRecord, RecordStatusEnum, ResultRecord
from typing_extensions import Literal

from openff.bespokefit.schema.tasks import (
    HessianTaskSpec,
    OptimizationTaskSpec,
    Torsion1DTaskSpec,
)

QCDataType = TypeVar("QCDataType")
QCTaskSpec = TypeVar(
    "QCTaskSpec", HessianTaskSpec, OptimizationTaskSpec, Torsion1DTaskSpec
)


class BespokeQCData(GenericModel, Generic[QCTaskSpec]):

    type: Literal["bespoke"] = "bespoke"

    spec: QCTaskSpec = Field(
        ...,
        description="The specification that should be used to generate the reference "
        "data.",
    )


class LocalQCData(GenericModel, Generic[QCDataType]):
    class Config:
        json_encoders = {np.ndarray: lambda v: v.flatten().tolist()}

    type: Literal["local"] = "local"

    qc_records: List[QCDataType] = Field(..., description="A list of local QC results.")

    @classmethod
    def _result_record_to_atomic_result(
        cls, record: ResultRecord, molecule: Molecule
    ) -> AtomicResult:
        raise NotImplementedError()

    @classmethod
    def _optimization_record_to_optimization_result(
        cls, record: OptimizationRecord, molecule: Molecule
    ) -> OptimizationResult:

        raise NotImplementedError()

    @classmethod
    def _torsion_drive_record_to_torsion_drive_result(
        cls, record: TorsionDriveRecord, molecule: Molecule
    ) -> TorsionDriveResult:

        assert record.status == RecordStatusEnum.complete

        return TorsionDriveResult(
            keywords=record.keywords,
            extras=record.extras,
            input_specification=QCInputSpecification(
                driver=record.qc_spec.driver,
                model=Model(method=record.qc_spec.method, basis=record.qc_spec.basis),
                extras=record.extras,
            ),
            initial_molecule=[molecule.to_qcschema()],
            optimization_spec=OptimizationSpecification(
                procedure=record.optimization_spec.program,
                keywords=record.optimization_spec.keywords,
                protocols=record.optimization_spec.protocols,
            ),
            final_energies=record.final_energy_dict,
            final_molecules={
                grid_id: molecule.to_qcschema(conformer=i)
                for i, grid_id in enumerate(molecule.properties["grid_ids"])
            },
            optimization_history={},
            success=True,
            provenance=record.provenance,
        )

    @classmethod
    @overload
    def from_remote_records(
        cls, qc_records: List[Tuple[TorsionDriveRecord, Molecule]]
    ) -> "LocalQCData[TorsionDriveResult]":
        ...

    @classmethod
    @overload
    def from_remote_records(
        cls, qc_records: List[Tuple[OptimizationRecord, Molecule]]
    ) -> "LocalQCData[OptimizationResult]":
        ...

    @classmethod
    @overload
    def from_remote_records(
        cls, qc_records: List[Tuple[ResultRecord, Molecule]]
    ) -> "LocalQCData[AtomicResult]":
        ...

    @classmethod
    def from_remote_records(cls, qc_records):

        record_types = list({type(qc_record) for qc_record, _ in qc_records})
        assert len(record_types) == 1, "records must be the same type"

        conversion_functions = {
            ResultRecord: cls._result_record_to_atomic_result,
            OptimizationRecord: cls._optimization_record_to_optimization_result,
            TorsionDriveRecord: cls._torsion_drive_record_to_torsion_drive_result,
        }

        return cls(
            qc_records=[
                conversion_functions[record_types[0]](qc_record, molecule)
                for qc_record, molecule in qc_records
            ]
        )
