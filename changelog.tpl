{% set labels = {"feat": "Features", "fix": "Bug Fixes", "perf": "Performance", "refactor": "Refactoring"} %}
{% set wanted = ["feat", "fix", "perf", "refactor"] %}
{% for t in wanted %}
{% set group = commits | filter(attribute="type", value=t) %}
{% if group | length > 0 %}
#### {{ labels[t] }}

{% for commit in group %}
- ({{ commit.id }}) {{ commit.summary }} - {{ commit.signature }}
{% endfor %}
{% endif %}
{% endfor %}
