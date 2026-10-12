"""SDPA compatibility for CUDA builds without fused grouped-query attention.

Expand grouped K/V heads before dispatch so PyTorch can select its existing
memory-efficient kernel. Masks, scaling, cached decoding and causal semantics
remain handled by the installed Transformers SDPA implementation.
"""
from transformers.integrations.sdpa_attention import repeat_kv, sdpa_attention_forward
from transformers.masking_utils import AttentionMaskInterface, ALL_MASK_ATTENTION_FUNCTIONS
from transformers.modeling_utils import AttentionInterface


class _ExpandedHeads:
    num_key_value_groups = 1

    def __init__(self, module):
        self.module = module

    def __getattr__(self, key):
        return getattr(self.module, key)


def compatible_sdpa(module, query, key, value, attention_mask, **kwargs):
    groups = getattr(module, 'num_key_value_groups', 1)
    if groups > 1:
        key = repeat_kv(key, groups)
        value = repeat_kv(value, groups)
        module = _ExpandedHeads(module)
    return sdpa_attention_forward(module, query, key, value, attention_mask, **kwargs)


def install_compatible_sdpa(model):
    AttentionInterface.register('luminar_sdpa', compatible_sdpa)
    AttentionMaskInterface.register('luminar_sdpa', ALL_MASK_ATTENTION_FUNCTIONS['sdpa'])
    model.set_attn_implementation('luminar_sdpa')
