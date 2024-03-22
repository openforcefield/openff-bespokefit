import json
from typing import Generic, List, Tuple, TypeVar, overload

import numpy as np
from openff.toolkit import Molecule
from qcelemental.models import AtomicResult, DriverEnum
from qcelemental.models.common_models import Model
from qcelemental.models.procedures import (
    OptimizationResult,
    OptimizationSpecification,
    QCInputSpecification,
    TorsionDriveResult,
)
from qcportal.optimization import OptimizationRecord
from qcportal.record_models import BaseRecord, RecordStatusEnum
from qcportal.torsiondrive import TorsiondriveRecord
from typing_extensions import Literal

from openff.bespokefit._pydantic import Field, GenericModel
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
        cls, record: BaseRecord, molecule: Molecule
    ) -> AtomicResult:
        raise NotImplementedError()

    @classmethod
    def _optimization_record_to_optimization_result(
        cls, record: OptimizationRecord, molecule: Molecule
    ) -> OptimizationResult:
        raise NotImplementedError()

    @classmethod
    def _torsion_drive_record_to_torsion_drive_result(
        cls, record: TorsiondriveRecord, molecule: Molecule
    ) -> TorsionDriveResult:
        assert record.status == RecordStatusEnum.complete
        # add the program to the model which we need for the cache
        extras = record.extras

        extras["program"] = record.specification.program
        opt_spec = record.specification.optimization_specification
        qc_spec = opt_spec.qc_specification

        return TorsionDriveResult(
            keywords=record.specification.keywords.dict(),
            extras=extras,
            input_specification=QCInputSpecification(
                driver=DriverEnum.gradient,  # qc_spec.driver,
                model=Model(
                    method=qc_spec.method,
                    basis=qc_spec.basis,
                ),
                extras=record.extras,
            ),
            initial_molecule=[molecule.to_qcschema()],
            optimization_spec=OptimizationSpecification(
                procedure=opt_spec.program,
                keywords=opt_spec.keywords,
                protocols=opt_spec.protocols,
            ),
            final_energies={
                json.dumps(key): value for key, value in record.final_energies.items()
            },
            final_molecules={
                str(grid_id): molecule.to_qcschema(conformer=i)
                for i, grid_id in enumerate(molecule.properties["grid_ids"])
            },
            optimization_history={},
            success=True,
            provenance=record.provenance,
        )

    @classmethod
    @overload
    def from_remote_records(
        cls, qc_records: List[Tuple[TorsiondriveRecord, Molecule]]
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
        cls, qc_records: List[Tuple[BaseRecord, Molecule]]
    ) -> "LocalQCData[AtomicResult]":
        ...

    @classmethod
    def from_remote_records(cls, qc_records):
        record_types = list({type(qc_record) for qc_record, _ in qc_records})
        assert len(record_types) == 1, "records must be the same type"

        conversion_functions = {
            BaseRecord: cls._result_record_to_atomic_result,  # maybe should be SinglepointRecord?
            OptimizationRecord: cls._optimization_record_to_optimization_result,
            TorsiondriveRecord: cls._torsion_drive_record_to_torsion_drive_result,
        }

        return cls(
            qc_records=[
                conversion_functions[record_types[0]](qc_record, molecule)
                for qc_record, molecule in qc_records
            ]
        )
