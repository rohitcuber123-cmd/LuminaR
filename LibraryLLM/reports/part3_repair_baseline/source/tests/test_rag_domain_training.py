import torch
from sentence_transformers.sentence_transformer.data_collator import SentenceTransformerDataCollator
from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss


class IdentityEmbeddings(torch.nn.Module):
    def forward(self, features):
        return {"sentence_embedding": features["embedding"]}


def test_explicit_negative_survives_collation_and_changes_loss():
    def fake_preprocess(texts, **_):
        return {"input_ids": torch.tensor([[len(text)] for text in texts])}

    collator = SentenceTransformerDataCollator(preprocess_fn=fake_preprocess)
    batch = collator([
        {"query": "query one", "positive": "positive one", "hard_negative": "wrong one"},
        {"query": "query two", "positive": "positive two", "hard_negative": "wrong two"},
    ])
    assert "query_input_ids" in batch
    assert "positive_input_ids" in batch
    assert "hard_negative_input_ids" in batch
    assert batch["hard_negative_input_ids"].shape[0] == 2

    loss = MultipleNegativesRankingLoss(IdentityEmbeddings())
    q = {"embedding": torch.tensor([[1., 0.], [0., 1.]])}
    p = {"embedding": torch.tensor([[1., 0.], [0., 1.]])}
    n = {"embedding": torch.tensor([[1., 0.], [0., 1.]])}
    without = loss([q, p], None)
    with_negative = loss([q, p, n], None)
    assert torch.isfinite(with_negative)
    assert with_negative > without
