(schemas_chapter)=
# Schemas in BespokeFit

BespokeFit uses [Pydantic] to validate input provided by users. Pydantic helps
BespokeFit provide clear error messages when it is configured improperly, and
also provides inspection and documentation tools that BespokeFit uses
extensively.

## Models and fields

Not every class in BespokeFit uses Pydantic; those that do are found mostly in
the [`schema`] module and can be identified in documentation as a `model`,
which appears in green before their path and name.

Models are characterized by their fields, which are like attributes in Python
data classes. Fields can be validated at runtime, both according to their type
annotations and via custom validator functions. Attempting to set a field to 
an invalid value will immediately raise a clear error, rather than causing a 
failure later on when the value is used.

A model's fields, validation machinery, and other Pydantic configuration forms
its schema. A schema describes every possible configuration of a model and is
useful for investigating what can be done with a class. Schemas are included in
a model's API reference documentation, and can be accessed programmatically
with the [`schema()`] method.

For example, [`BespokeWorkflowFactory`] is a model. Its schema is available
on its API page, but can also be accessed on the class itself or any instance:

```python
from openff.bespokefit.workflows.bespoke import BespokeWorkflowFactory

BespokeWorkflowFactory.schema()

factory = BespokeWorkflowFactory()
factory.schema()
```

## Introspection

Models provide a number of methods that are useful for inspecting objects in an
interactive environment, such as a Jupyter notebook. These methods are implemented
on [`pydantic.BaseModel`], documented below. Models in BespokeFit inherit these methods,
though they are not explicitly documented in order to reduce clutter.


:::{eval-rst} 

.. autoclass:: pydantic.BaseModel
    :no-show-inheritance:
    :no-members:

    Base class for Pydantic Models.

    Provides introspection methods and validation for fields.

    .. automethod:: dict
    
    .. automethod:: copy
    
    .. automethod:: json

    .. automethod:: parse_raw

        Read a ``str`` or ``bytes`` object encoding an instance of a model in JSON.
    
    .. automethod:: schema

        Display the schema satisfied by instances of the model.

        This method is useful for inspecting the options available in 
        a schema in an interactive environment.

:::


[Pydantic]: https://pydantic-docs.helpmanual.io/
[`schema`]: openff.bespokefit.schema
[`BespokeWorkflowFactory`]: openff.bespokefit.workflows.bespoke.BespokeWorkflowFactory
[`pydantic.BaseModel`]: pydantic.BaseModel
[`schema()`]: pydantic.BaseModel.schema
