# SRE 87 Advisory AI Risk Scoring

This milestone adds a machine-learning advisory layer to the deterministic SRE 87 control cycle.
The model predicts the probability that an eligible claim will remain outside status `300` after
recovery. It also produces a bounded operational priority score and a human-readable explanation.

## Safety boundary

The model is advisory-only. It cannot select an endpoint, change a claim status, skip prior-run
validation, bypass the two-hour threshold, or trigger an unapproved retry. Status routing remains
fully deterministic:

- `655`, `660`, `665` → CDR Persistence
- `800` → State Manager
- `850` → CBO Reprocessor

If the AI artifact cannot be loaded, the cycle fails open to deterministic automation and reports
`ai_scoring_status: unavailable` in the audit output.

## Model inputs

The synthetic model uses operational features that can later be mapped to approved enterprise
sources:

- Current process status
- Claim age in hours
- Claim amount
- Retry count
- Queue depth
- Endpoint latency
- Previous failure count
- Source system
- Provider type

No production claim data or internal endpoint information is included.

## Training

Quick local training without MLflow:

```bash
uv run python -m claimguard.sre87.ai --rows 12000 --no-mlflow
```

Tracked training through the configured MLflow server:

```bash
MLFLOW_TRACKING_URI=http://127.0.0.1:5000 \
uv run python -m claimguard.sre87.ai --rows 12000
```

Tracked runs use:

- Experiment: `ClaimGuard SRE87 Risk`
- Registered model: `ClaimGuardSRE87RiskModel`
- Aliases: `candidate`, `champion`, and `rollback`

Candidate selection favors recall, then F1 and ROC-AUC. The objective is to reduce false negatives
for claims likely to remain unresolved.

## Preview scores without recovery calls

```bash
uv run claimguard-sre87 seed --scenario happy
uv run claimguard-sre87 risk-preview
```

## Run the AI-assisted control cycle

```bash
uv run claimguard-sre87 run
```

The JSON audit contains:

```text
ai_scoring_status
risk_assessments[].probability
risk_assessments[].risk_level
risk_assessments[].priority_score
risk_assessments[].likely_failure_layer
risk_assessments[].recommended_action
risk_assessments[].explanation
risk_assessments[].advisory_only
risk_assessments[].routing_authority
```

The CSV audit includes the same risk probability, level, priority, failure layer, and advisory-only
indicator alongside the authoritative recovery route and response.
