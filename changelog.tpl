{% set wanted = ["feat", "fix", "perf", "refactor"] %}
{% for t in wanted %}
{% set group = commits | filter(attribute="type", value=t) %}
{% if group | length > 0 %}
#### {% if t == "feat" %}Features{% elif t == "fix" %}Bug Fixes{% elif t == "perf" %}Performance{% elif t == "refactor" %}Refactoring{% endif %}

{% for commit in group %}
- ({{ commit.id }}) {{ commit.summary }} - {{ commit.signature }}
{% endfor %}
{% endif %}
{% endfor %}
