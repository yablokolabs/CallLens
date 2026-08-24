# Custom Rubrics

Rubrics are **declarative, versioned YAML** documents. The scoring engine is generic — it evaluates whatever dimensions you define, with no sales assumptions baked into the engine.

## Authoring

```yaml
name: customer_success
version: "1.0"
description: >
  Evaluates customer success check-ins: value reinforcement,
  adoption, and expansion signals.

dimensions:
  value_reinforcement:
    label: Value Reinforcement
    weight: 0.35
    description: >
      Whether the CSM ties product usage back to the customer's goals.
  adoption:
    label: Adoption Review
    weight: 0.30
    description: >
      Whether usage metrics and feature adoption are reviewed explicitly.
  expansion:
    label: Expansion Signal
    weight: 0.20
    description: >
      Whether growth or upsell opportunities are surfaced naturally.
  health:
    label: Relationship Health
    weight: 0.15
    description: >
      Whether risks and churn signals are addressed proactively.
```

Rules:

- `name` and `version` are required.
- Dimension keys: lowercase `[a-z0-9_]`.
- `weight` must be in `(0, 1]` and **all weights must sum to `1.0`**.
- `description` is what the scoring LLM uses to judge the behavior — make it specific.

## Validate & use

```bash
# Validate locally
calllens rubric validate ./customer_success.yaml

# Register via the API
curl -X POST http://localhost:8000/api/v1/rubrics \
  -H 'Content-Type: application/json' \
  -d @customer_success.json

# Analyze with it
calllens analyze call.mp3 --rubric customer_success
curl -X POST http://localhost:8000/api/v1/calls -F file=@call.mp3 -F rubric=customer_success
```

Bundled rubrics live in `rubrics/` (consultative_sales, customer_support, recruitment). Drop a new YAML file there and restart the server to bundle it.
