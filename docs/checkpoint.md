# Verified model selection

The application defaults to Qwen3.5-4B **base** inference. Training saves a candidate; it never changes `.env`, activates an adapter, or claims an improvement. Human semantic review and outdoor usefulness are separate gates.

To deliberately select a completed candidate, configure `ONELAP_MODEL_TARGET=adapter`, `ONELAP_CHECKPOINT_APPROVED=true`, a server-private `ONELAP_CHECKPOINT_RECEIPT` path and the exact SHA-256 of that file in `ONELAP_CHECKPOINT_RECEIPT_SHA256`. Keep the receipt outside Git and frontend assets. Normal model/data/budget gates still apply. Restart the backend after selecting or changing a receipt.

Startup rejects malformed, incomplete, tampered, wrong-model, wrong-corpus or stale-method receipts. The completed pilot must have the frozen parameters and all 30 updates; the checked-in corpus manifest binds both corpus and supervised-training hashes. Sampling verifies the actual base model before encoding. An expired or unavailable Tinker sampler fails rather than silently falling back to the base model.

The status reports `base` or `adapter`. Adapter-generated missions include receipt/training SHA-256 identities, never the private sampler path. Older base missions retain their exact four-field identity and remain readable. Importing a mission does not authenticate its provenance or activate a model. Backend policy/validation edits invalidate method-bound receipts and evaluations; do not alter them between matched runs.

The final sampler has a seven-day TTL. Expiry requires a separately approved future training/checkpoint plan, not an automatic paid retrain. No adapter is enabled in the saved configuration by this feature.
