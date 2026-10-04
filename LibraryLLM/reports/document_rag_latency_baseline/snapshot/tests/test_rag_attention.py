"""Check grouped-head expansion preserves masks and cached-token attention."""
from types import SimpleNamespace
import pytest
import torch
from transformers.integrations.sdpa_attention import sdpa_attention_forward
from rag.attention import compatible_sdpa


@pytest.mark.parametrize('query_length,masked', [(7, False), (7, True), (1, False), (1, True)])
def test_expanded_attention_matches_grouped_math(query_length, masked):
    generator = torch.Generator().manual_seed(42)
    query = torch.randn(2, 8, query_length, 16, generator=generator)
    key = torch.randn(2, 2, 7, 16, generator=generator)
    value = torch.randn(2, 2, 7, 16, generator=generator)
    module = SimpleNamespace(num_key_value_groups=4, is_causal=True)
    mask = None
    if masked:
        mask = torch.ones(2, 1, query_length, 7, dtype=torch.bool)
        mask[..., -2:] = False
        if query_length > 1:
            mask &= torch.ones(query_length, 7, dtype=torch.bool).tril()
    expected, _ = sdpa_attention_forward(module, query, key, value, mask, scaling=.25)
    actual, _ = compatible_sdpa(module, query, key, value, mask, scaling=.25)
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)
