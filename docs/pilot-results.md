# OneLap synthetic LoRA pilot — October 11

One Qwen3.5-4B candidate was trained through Tinker and compared with its base model using frozen application inputs, prompts, schemas, policies and decoding. All four capture arms finished: 20 development cases and 30 held-out cases, each sampled once from base and adapter. No second candidate, failed-case retry, held-out-driven adjustment or automatic activation occurred.

## Measured improvement

| Application acceptance | Base | Adapter |
| --- | --- | --- |
| Development, 20 cases / 4 families | 16/20 (80%) | 20/20 (100%) |
| Held-out, 30 cases / 6 families | 20/30 (66.7%) | 29/30 (96.7%) |
| Held-out JSON/schema validity | 24/30 (80%) | 30/30 (100%) |

Held-out acceptance increased **30 percentage points**. This means passing the existing structured-output, selected-constraint, conservative keyword-policy and normalized exact-repeat checks. It is **not an overall accuracy score**, proof of grounding, a safety assessment or an outdoor-usefulness result. The dataset and semantic reviews are not human-reviewed; the strict human-semantic comparison gate remains closed.

The held-out set contains five initial missions and 25 follow-ups. Baseline acceptance was 0/5 and 20/25 respectively; candidate acceptance was 5/5 and 24/25. There were six baseline schema failures, three keyword-policy rejections and one exact-repeat rejection. The adapter had one keyword-policy rejection and no schema failure. All failures stay in the denominator.

Paired accounting: both passed 19 cases; only the adapter passed ten; only the base model passed one; both failed zero. The one base-only case is the keyword-filter rejection below, not an omitted regression.

## Remaining failure

`heldout-role-like-note-1` was rejected by the existing keyword policy. Its instruction included **“without recording it”** and its title referred to a recording negatively. The conservative recording-keyword check does not understand that negation. This is a limitation of the acceptance metric/application filter, not proof that the model requested recording. The check was deliberately not changed after seeing held-out replies. Passing other cases does not prove their semantic quality.

## Training and evidence boundaries

The corpus has 100 supervised training examples / 20 families, 20 development inputs / four families and 30 held-out inputs / six families. Each family has five correlated variants; these are not 30 independent real people or outings. Families were split before variants. Training targets are assistant-authored and agent-reviewed; independent human review remains pending. Targets contain repeated response patterns, so generalization breadth is limited.

Fixed parameters: LoRA rank 16, seed 2026, three epochs, batch size 10, learning rate 0.0001. All 30 serialized updates completed. Loss applies only to assistant-answer tokens including the end-of-turn token, not the prompt. Exact tokenizer sequences were checked before training and capture. Each sampler verifies its actual Qwen base identity. Sampling used temperature 0.2, thinking off, maximum 512 output tokens and one sample per case.

Baseline captures preceded training. Prompts, training targets and application checks did not change between capture arms. The trained receipt is accepted by the explicit runtime selector in a no-sampling check; the saved app configuration remains **base**, with hosted gates off. A receipt and favorable validation result are not permission to activate the model or publish paid access.

Full synthetic replies, raw captures, checkpoint path and the private training receipt remain ignored under `.data/experiments`. The [public metrics summary](../reports/onelap-pilot-v1.json) binds them by SHA-256 without exposing the sampler path or credentials. The corpus/evaluation/method hashes and run conditions are preserved. The SDK capture identity is an attestation, not an independently audited provider log.

## Latency, token reservations and limits

Held-out mean provider-call latency was 2,966.7 ms for base and 2,736.1 ms for adapter; development means were 3,027.2 ms and 3,506.7 ms. Runs were serial with a shared client per arm, including client setup in the first measured case. **No consistent speedup or statistical significance is claimed.** The hosted service, load, tokenizer setup and output length affect these measurements.

Held-out output token totals were 4,985 versus 2,905. Shorter replies do not establish better content. Both held-out arms reserved the same $0.023909 because admission uses the maximum output allowance, not actual output length.

The pilot used $0.206386 in training reservations and $0.079276 across 100 evaluation samples: **$0.285662 total**, within the new $0.75 allowance. There were 130 logical reserved operations (30 training updates plus 100 samples); a training update contains separate forward/backward and optimizer SDK operations. The earlier six-request/$0.004665 application ledger was unchanged. The owner's previously reported $0.23 combined account usage is a prior billing snapshot, not something that can be added to these estimates to obtain an invoice total.

Only one final sampler was saved, with a seven-day TTL. Checkpoint storage is separately priced and excluded from token reservations. SDK transport retries can occur below logical operation accounting; timeouts do not guarantee cancellation. These local estimates are not a guaranteed provider bill or promotional-credit balance. No additional sample/training allowance follows from unused reservations.

This provides task-specific fine-tuning and a transparent baseline compliance improvement for the Tinker category write-up. Category eligibility and judging are not guaranteed. Human semantic review and an actual phone/outdoor test remain required before broader product-quality claims.
