"""Templates for ForceBalance targets and options."""
import abc
import os
from typing import Generic, TypeVar

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
    """Base class for target templates."""

    @classmethod
    @abc.abstractmethod
    def template_name(cls) -> str:
        """Return the name of this template."""
        raise NotImplementedError()

    @classmethod
    def schema_exclusions(cls) -> set[str]:
        """Return the schema to exclude from this template."""
        return set()

    @classmethod
    def generate(cls, schema: T, target_names: list[str]) -> str:
        """Generate a template for this target."""
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
                    exclude={"type", "reference_data", *cls.schema_exclusions()},
                ),
            )
            for target_name in target_names
        )
        return rendered_template


class AbInitioTargetTemplate(BaseTargetTemplate[AbInitioTargetSchema]):
    """Template for ab initio targets."""

    @classmethod
    def template_name(cls) -> str:
        """Return the name of this template."""
        return "ab-initio-target.txt"


class TorsionProfileTargetTemplate(BaseTargetTemplate[TorsionProfileTargetSchema]):
    """Template for torsion profile targets."""

    @classmethod
    def template_name(cls) -> str:
        """Return the name of this template."""
        return "torsion-profile-target.txt"


class OptGeoTargetTemplate(BaseTargetTemplate[OptGeoTargetSchema]):
    """Template for geometry optimizaiton targets."""

    @classmethod
    def template_name(cls) -> str:
        """Return the name of this template."""
        return "opt-geo-target.txt"


class VibrationTargetTemplate(BaseTargetTemplate[VibrationTargetSchema]):
    """Template for vibrational frequency targets."""

    @classmethod
    def template_name(cls) -> str:
        """Return the name of this template."""
        return "vibration-target.txt"


class OptGeoOptionsTemplate:
    """Template for geometry optimization options."""

    @classmethod
    def schema_exclusions(cls) -> set[str]:
        """Return the schema to exclude from this template."""
        return {
            "bond_denominator",
            "angle_denominator",
            "dihedral_denominator",
            "improper_denominator",
        }

    @classmethod
    def generate(cls, target: OptGeoTargetSchema, record_ids: list[str]) -> str:
        """Generate an geometry optimization options template."""
        template_file_name = get_data_file_path(
            os.path.join("templates", "force-balance", "opt-geo-options.txt"),
            "openff.bespokefit",
        )

        with open(template_file_name) as file:
            template = Template(file.read())

        rendered_template = template.render(
            **target.dict(include=cls.schema_exclusions()),
            systems=record_ids,
        )
        return rendered_template


class InputOptionsTemplate:
    """Template for input ForceBalance input options."""

    @classmethod
    def generate(
        cls,
        settings: ForceBalanceSchema,
        priors: dict[str, float],
        targets_section: str,
    ) -> str:
        """Generate this template."""
        template_file_name = get_data_file_path(
            os.path.join("templates", "force-balance", "optimize.txt"),
            "openff.bespokefit",
        )

        with open(template_file_name) as file:
            template = Template(file.read())

        rendered_template = template.render(
            **settings.dict(),
            priors=priors,
            targets_contents=targets_section,
        )
        return rendered_template
