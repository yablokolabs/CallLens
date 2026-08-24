#!/usr/bin/env bash
# CallLens CLI quickstart — runs fully offline with mock providers.
set -euo pipefail

# 1. List bundled rubrics
calllens rubric list

# 2. Validate a rubric document
calllens rubric validate rubrics/consultative_sales.yaml

# 3. Analyze a text transcript, write the JSON report
calllens analyze examples/sample_call.txt --rubric consultative_sales --output /tmp/calllens-report.json

# 4. Run the evaluation harness over the synthetic dataset
calllens eval run

# 5. Serve the API
# calllens server
