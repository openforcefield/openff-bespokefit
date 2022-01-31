{{ objname | escape | underline(line="=")}}

.. automodule:: {{ fullname }}
   :no-members:

.. currentmodule:: {{ fullname }}

{% block modules %}
{% if modules %}
{{ _('Modules') | escape | underline(line="-") }}

.. autosummary::
   :toctree: {{objname}}
   :recursive:
{% for item in modules if item not in exclude_modules %}
   {{ item.removeprefix(fullname ~ ".") }}
{%- endfor %}
{% endif %}
{% endblock %}

{% block classes -%}

{%- set types = [] -%}
{%- for item in members -%}
   {%- if not item.startswith('_') and not (item in functions or item in attributes or item in exceptions) -%}
      {%- set _ = types.append(item) -%}
   {%- endif -%}
{%- endfor %}

{% if types %}
{{ _('Classes') | escape | underline(line="-") }}

   .. autosummary::
      :toctree: {{objname}}
      :nosignatures:
   {% for item in types %}
      {{ item.removeprefix(fullname ~ ".").partition('[')[0] }}
   {%- endfor %}

{% endif %}
{% endblock %}

{% block functions %}
{% if functions %}
{{ _('Functions') | escape | underline(line="-") }}

   .. autosummary::
      :toctree: {{objname}}
      :nosignatures:
   {% for item in functions %}
      {{ item.removeprefix(fullname ~ ".") }}
   {%- endfor %}

{% endif %}
{% endblock %}

{% block exceptions %}
{% if exceptions %}
{{ _('Exceptions') | escape | underline(line="-") }}

   .. autosummary::
      :toctree: {{objname}}
      :nosignatures:
   {% for item in exceptions %}
      {{ item.removeprefix(fullname ~ ".") }}
   {%- endfor %}

{% endif %}
{% endblock %}

{% block attributes %}
{% if attributes %}
{{ _('Module Attributes') | escape | underline(line="-") }}

   {% for item in attributes %}
   .. autoattribute:: {{ item.removeprefix(fullname ~ ".") }}
   {%- endfor %}

{% endif %}
{% endblock %}
