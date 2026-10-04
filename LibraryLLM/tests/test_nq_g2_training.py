"""G2 contract: the explicit hard negative survives collating and enters MNRL."""
from datasets import Dataset
import torch
from sentence_transformers import (
    SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments,
)
from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss
from sentence_transformers.sentence_transformer.training_args import BatchSamplers


def test_explicit_negative_reaches_loss(tmp_path):
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2",
                                device="cpu", local_files_only=True)
    data = Dataset.from_list([
        {"query": "where was alice born", "positive": "alice was born in london",
         "negative": "alice later moved to paris"},
        {"query": "where was bob born", "positive": "bob was born in boston",
         "negative": "bob later moved to seattle"},
    ])
    assert data.column_names == ["query", "positive", "negative"]
    args = SentenceTransformerTrainingArguments(
        output_dir=str(tmp_path), per_device_train_batch_size=2,
        batch_sampler=BatchSamplers.NO_DUPLICATES, report_to="none",
        dataloader_num_workers=0,
    )
    loss = MultipleNegativesRankingLoss(model)
    trainer = SentenceTransformerTrainer(model=model, args=args,
                                         train_dataset=data, loss=loss)
    batch = next(iter(trainer.get_train_dataloader()))
    assert {"query_input_ids", "positive_input_ids", "negative_input_ids"} <= set(batch)
    features, labels = trainer.collect_features(batch)
    assert len(features) == 3
    assert labels is None
    with torch.no_grad():
        embeddings = [model(f)["sentence_embedding"] for f in features]
        original = loss.compute_loss_from_embeddings(embeddings, labels)
        # Changing only the explicit negative must alter the softmax denominator.
        changed = loss.compute_loss_from_embeddings(
            [embeddings[0], embeddings[1], embeddings[1]], labels)
    assert torch.isfinite(original)
    assert torch.isfinite(changed)
    assert not torch.isclose(original, changed, atol=1e-5)
