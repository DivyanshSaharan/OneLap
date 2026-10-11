# Bounded synthetic evaluation

`scripts/run_experiment.py preview` counts exact application prompts with a cached Qwen tokenizer and never creates a hosted client. The new supervised corpus is assistant-authored and agent-reviewed; human semantic review and real outdoor evidence remain pending.

The explicitly admitted pilot uses a separate persistent `.data/experiments/experiment-budget.sqlite3` ledger shared with training: at most USD 0.75 in token reservations and 150 chargeable logical operations. The existing application inference ledger is not reset or reused. Reservations include maximum output tokens and are never refunded. SDK transport retries and checkpoint storage mean these estimates are not a guaranteed invoice cap.

From the repository root:

```powershell
.venv/Scripts/python.exe scripts/run_experiment.py preview
.venv/Scripts/python.exe scripts/run_experiment.py capture --live --ack-agent-reviewed-synthetic --ack-sdk-retries --target base --split dev --run-id baseline-dev --output .data/experiments/baseline-dev.json
```

Repeat only for the separately admitted held-out arm, then one adapter arm per split after the training receipt exists. No automatic retries, second candidate, personal journals, Atlas reads, Sentry export or public posting occur. Inputs/outputs remain in ignored `.data/experiments`; secrets are loaded only for explicitly live execution and error messages are sanitized. Failed requests retain their reservation and stop the capture. Every case retains a raw response or explicit failure, including not-run cases. Existing output files and admitted run fingerprints cannot be replayed.

`compare-checks` reports matched held-out JSON validity, selection constraints, keyword policy and exact-repeat checks. It does not circumvent `evaluate.py compare`, which still requires complete human semantic reviews. Application acceptance is not semantic accuracy, a safety guarantee, evidence of behavior change, or permission to automatically activate the adapter. Record latency/cost measurements and failures with denominators and the fixed decoding parameters.
