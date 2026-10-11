# One capped synthetic LoRA pilot

Use `scripts/train_onelap.py` without flags for an offline token estimate. The sole admitted live candidate uses 100 assistant-authored, agent-reviewed synthetic training examples, rank 16, seed 2026, three epochs, batches of 10, learning rate 0.0001 and disabled Qwen thinking. There are no genuine outings or independently human-reviewed targets. Family splits and exact inputs are frozen in `datasets/onelap-sft-v1.manifest.json`.

The assistant answer alone receives loss weights, including its end-of-turn token. Shifted targets predict each next token; prompt positions have zero loss. The script checks that the hosted tokenizer produces exactly the preflight sequences before any update. Thirty serialized forward/backward + optimizer updates reserve their full sequence tokens through the shared experiment ledger. No automatic candidate retry or second search occurs after failure.

```powershell
.venv/Scripts/python.exe scripts/train_onelap.py
.venv/Scripts/python.exe scripts/train_onelap.py --live --ack-agent-reviewed-synthetic --ack-sdk-retries
```

The full combined training/evaluation token-reservation allowance is $0.75. This is not an invoice guarantee: SDK transport retries may occur beneath logical operations, and storage is separate. Only one final sampler is saved, with a seven-day TTL; no intermediate or optimizer checkpoint is saved. Interrupted/failed operations retain their reservations. Preview does not load credentials or create a hosted client; raw receipts, metrics and checkpoint identifiers remain ignored under `.data/experiments`.

Capture both baseline splits before training, then both candidate splits with unchanged prompts, schemas, policies and decoding. Report all cases and failures; never iterate on held-out replies. The deterministic comparison is application acceptance, not an overall accuracy score. Human semantic review, real outing evidence and model promotion remain pending even after a successful training job.
