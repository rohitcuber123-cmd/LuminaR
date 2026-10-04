# G1 MS MARCO bi-encoder training

The frozen LuminaR DEV baseline A was reproduced before training: MRR 0.165266, Hit@20 0.482759, Hit@50 0.655172, Recall@20 0.465517, Recall@50 0.620690. All saved Top-50 chunk IDs matched the historical baseline exactly. Source/evaluation hashes and the 64-file production snapshot matched.

The installed `sentence-transformers` 5.6.0 implementation of `MultipleNegativesRankingLoss` accepts anchor, positive, and explicit negative embeddings. Its candidate matrix concatenates positives and negatives. The focused test passed: the trainer retained `negative_input_ids`, supplied three feature groups, and changing the negative changed the computed loss. `NO_DUPLICATES` was used for the per-device batch sampler.

Ordinary MNRL was selected because a physical batch of 16 triplets fit with substantial GPU headroom. Cached MNRL was inspected but not needed for this bounded pilot. The effective contrastive batch is 16, with one explicit hard negative per row and in-batch positives/negatives; gradient accumulation is 1. No claim is made that accumulation enlarged the negative pool.

Configuration: seed 42; one epoch; learning rate 2e-5; weight decay 0.01; linear schedule; 0.05 warmup ratio; BF16 on, FP16 off; original MiniLM architecture, 256-token window, 384-dimensional embeddings. The tokenizer and model window were not changed.

Smoke run: 1,024 triplets, 64 steps, finite final loss 1.458337, model saved and reloaded, peak reserved VRAM 1,203,765,248 bytes, minimum global free VRAM 6,139,412,480 bytes.

Full run: 45,000 triplets, 2,813 steps, 364.02 seconds, final training loss 0.916193. Peak reserved VRAM 1,344,274,432 bytes; peak allocated VRAM 1,205,663,744 bytes; minimum global free VRAM 5,996,806,144 bytes; peak process RAM 2,277,363,712 bytes. Training remained finite and the final saved model passed an encode/reload check.

Full model weights SHA-256: `18b51b15c248916dce4e99532796edbbb0de0322827ad9fe1bb1b7ec90d1ec1f`.

Machine-readable smoke and full manifests are in `datasets/training/manifests/`. The final G1 model is isolated under `datasets/training/models/minilm_g1_msmarco_50k_full/`.
