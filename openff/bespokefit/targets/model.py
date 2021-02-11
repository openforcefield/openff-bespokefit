"""
The base target model.
"""

import abc
from typing import Any, Dict, List, Optional, Tuple, Union

import openforcefield.topology as off
from typing_extensions import Literal

from openff.bespokefit.common_structures import SchemaBase
from openff.bespokefit.schema import (
    HessianTask,
    OptimizationTask,
    TargetSchema,
    TorsionTask,
)
from openff.qcsubmit.common_structures import MoleculeAttributes, QCSpec


class Target(SchemaBase, abc.ABC):
    """
    The base target class used to create new targets.
    This acts as a factory which acts on each molecule passed producing fitting targets specific to the molecule.

    """

    name: Literal["Target"] = "Target"
    description: str
    collection_workflow: Literal["torsion1d", "optimization", "hessian"]
    target_conformers: int = 4
    keywords: Dict[str, Any] = {}
    weight: int = 1
    qc_spec: QCSpec = QCSpec()
    _extra_dependencies = []
    _enum_fields = []

    class Config:
        # define some fields that will be reused with new defaults
        fields = {
            "name": {
                "description": "The name of the target used for distinguishing between them."
            },
            "description": {
                "description": "A short description of how the target works."
            },
            "collection_workflow": {
                "description": "The collection workflow that should be used to generate the reference data"
            },
            "keywords": {"description": "Any extra keywords needed by the target."},
            "target_conformers": {
                "description": "The number of conformers that should be generated for this target."
            },
            "weight": {
                "description": "The weight of this target, currently only needed by forcebalance."
            },
            "qc_spec": {
                "description": "The QC specification that should be used to compute this data."
            },
        }

    # def dict(
    #     self,
    #     *,
    #     include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
    #     exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
    #     by_alias: bool = False,
    #     skip_defaults: bool = None,
    #     exclude_unset: bool = False,
    #     exclude_defaults: bool = False,
    #     exclude_none: bool = False,
    # ) -> "DictStrAny":
    #
    #     # correct the enum dict rep
    #     data = super().dict(
    #         include=include,
    #         exclude=exclude,
    #         by_alias=by_alias,
    #         skip_defaults=skip_defaults,
    #         exclude_unset=exclude_unset,
    #         exclude_defaults=exclude_defaults,
    #         exclude_none=exclude_none,
    #     )
    #     for field in self._enum_fields:
    #         data[field] = getattr(self, field).value
    #     return data

    def generate_target_schema(self) -> TargetSchema:
        """
        Generate the target schema for this target class, this captures details about the target which will be used for fitting.
        """
        schema = TargetSchema(
            target_name=self.name,
            provenance=self.provenance(),
            qc_spec=self.qc_spec,
            collection_workflow=self.collection_workflow,
            settings=self.dict(),
        )
        return schema

    def generate_fitting_task(
        self,
        molecule: off.Molecule,
        fragment: bool,
        attributes: MoleculeAttributes,
        fragment_parent_mapping: Optional[Dict[int, int]] = None,
        dihedrals: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> Union[TorsionTask, OptimizationTask, HessianTask]:
        """
        For the given collection workflow generate a task schema for the input molecule.
        """
        if molecule.n_conformers < self.target_conformers:
            molecule.generate_conformers(
                n_conformers=self.target_conformers, clear_existing=False
            )

        # build a dict of the data
        data = dict(
            name=self.collection_workflow,
            attributes=attributes,
            provenance=self.provenance(),
            fragment=fragment,
            fragment_parent_mapping=fragment_parent_mapping,
            molecule=molecule,
            dihedrals=dihedrals,
        )
        if self.collection_workflow == "torsion1d":
            task = TorsionTask(**data)
        elif self.collection_workflow == "optimization":
            task = OptimizationTask(**data)
        elif self.collection_workflow == "hessian":
            task = HessianTask(**data)
        else:
            raise NotImplementedError(
                f"The collection workflow {self.collection_workflow} is not supported."
            )
        return task

    def provenance(self) -> Dict[str, Any]:
        """
        Return the basic provenance of the target and any dependencies it may have.

        Note:
            New targets only need to add the name of the dependence to the _extra_dependencies list to have it included.
        """
        import importlib

        import openforcefield
        import openforcefields

        from openff import bespokefit, qcsubmit

        provenance = {
            "openforcefield": openforcefield.__version__,
            "openforcefields": openforcefields.__version__,
            "target": self.name,
            "bespokefit": bespokefit.__version__,
            "qcsubmit": qcsubmit.__version__,
        }
        # now loop over the extra dependencies
        for dependency in self._extra_dependencies:
            dep = importlib.import_module(dependency)
            provenance[dependency] = dep.__version__

        return provenance

    @abc.abstractmethod
    def prep_for_fitting(self, fitting_target: TargetSchema) -> None:
        """
        Some optimizers will need the general schema data to be adapted to suite the optimizer, this should be
        implemented here, and will be called before optimization on each target.
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def local_reference_collection(self, fitting_target: TargetSchema) -> TargetSchema:
        """
        If the collection method is type local then this method must be implemented and will be used to collect the data localy prvided the fitting schema.

        Note:
            Bespokefit will handle directory changes.
        """

        raise NotImplementedError()
