import abc
import os
from typing import Dict, Generic, List, Set, TypeVar

from jinja2 import Template
from openff.utilities import get_data_file_path

from openff.bespokefit.schema.optimizers import ForceBalanceSchema
from openff.bespokefit.schema.targets import (
    AbInitioTargetSchema,
    OptGeoTargetSchema,
    TargetSchema,
    TorsionProfileTargetSchema,
    VibrationTargetSchema,
)

T = TypeVar("T", bound=TargetSchema)


class BaseTargetTemplate(Generic[T]):
    @classmethod
    @abc.abstractmethod
    def template_name(cls) -> str:
        raise NotImplementedError()

    @classmethod
    def schema_exclusions(cls) -> Set[str]:
        return set()

    @classmethod
    def generate(cls, schema: T, target_names: List[str]) -> str:
        template_file_name = get_data_file_path(
            os.path.join("templates", "force-balance", cls.template_name()),
            "openff.bespokefit",
        )

        with open(template_file_name) as file:
            template = Template(file.read())

        rendered_template = "\n\n".join(
            template.render(
                name=target_name,
                **schema.dict(
                    exclude={"type", "reference_data", *cls.schema_exclusions()}
                ),
            )
            for target_name in target_names
        )
        return rendered_template


class AbInitioTargetTemplate(BaseTargetTemplate[AbInitioTargetSchema]):
    @classmethod
    def template_name(cls) -> str:
        return "ab-initio-target.txt"


class TorsionProfileTargetTemplate(BaseTargetTemplate[TorsionProfileTargetSchema]):
    @classmethod
    def template_name(cls) -> str:
        return "torsion-profile-target.txt"


class OptGeoTargetTemplate(BaseTargetTemplate[OptGeoTargetSchema]):
    @classmethod
    def template_name(cls) -> str:
        return "opt-geo-target.txt"


class VibrationTargetTemplate(BaseTargetTemplate[VibrationTargetSchema]):
    @classmethod
    def template_name(cls) -> str:
        return "vibration-target.txt"


class OptGeoOptionsTemplate:
    @classmethod
    def schema_exclusions(cls) -> Set[str]:
        return {
            "bond_denominator",
            "angle_denominator",
            "dihedral_denominator",
            "improper_denominator",
        }

    @classmethod
    def generate(cls, target: OptGeoTargetSchema, record_ids: List[str]) -> str:
        template_file_name = get_data_file_path(
            os.path.join("templates", "force-balance", "opt-geo-options.txt"),
            "openff.bespokefit",
        )

        with open(template_file_name) as file:
            template = Template(file.read())

        rendered_template = template.render(
            **target.dict(include=cls.schema_exclusions()), systems=record_ids
        )
        return rendered_template


class InputOptionsTemplate:
    @classmethod
    def generate(
        cls,
        settings: ForceBalanceSchema,
        priors: Dict[str, float],
        targets_section: str,
    ) -> str:
        template_file_name = get_data_file_path(
            os.path.join("templates", "force-balance", "optimize.txt"),
            "openff.bespokefit",
        )

        with open(template_file_name) as file:
            template = Template(file.read())

        rendered_template = template.render(
            **settings.dict(), priors=priors, targets_contents=targets_section
        )
        return rendered_template
