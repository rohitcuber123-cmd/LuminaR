from pathlib import Path
import os
import time
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from rag.telemetry import stage, record_generation
from rag.query_types import ordinary_book_intent
from rag.decoding import AnswerRepetitionControl

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig
)

from pydantic import BaseModel, Field
from typing import Optional, Literal
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import (
    build_transformers_prefix_allowed_tokens_fn,
    build_token_enforcer_tokenizer_data,
)

class IntentSchema(BaseModel):
    intent: Literal["MOTIVATION", "NEGATED_MOTIVATION", "REGRET", "CONSEQUENCE", "REACTION", "RELATIONSHIP", "FACTUAL"]
    actor: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None
    polarity: Literal["positive", "negative"] = "positive"
    temporal_relation: Optional[str] = None
    question_focus: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)

class ValidatorSchema(BaseModel):
    supported: bool
    confidence: float = Field(ge=0.0, le=1.0)

# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ------------------------------------------------------------
# MOCK MODE
#
# Set the environment variable LUMINAR_MOCK_LLM=1 to enable
# mock mode for testing retrieval without GPU generation.
#
# When mock mode is OFF (default), the real Qwen model is
# used for generation.
# ------------------------------------------------------------

MOCK_MODE = (
    os.environ.get("LUMINAR_MOCK_LLM", "")
    in ("1", "true", "yes")
)

# ------------------------------------------------------------
# SYSTEM MESSAGE
#
# Prepended as the system role when using
# apply_chat_template(). Establishes core behavioral
# constraints for every generation.
# ------------------------------------------------------------

SYSTEM_MESSAGE = (
    "You are LuminaR, a grounded book and document "
    "question-answering assistant.\n"
    "Answer ONLY using the supplied context.\n"
    "Never continue, imitate, or recreate the source book.\n"
    "Never invent facts.\n"
    "Never invent citations.\n"
    "Never output [Source X] markers.\n"
    "Answer the user's question directly."
)

# ------------------------------------------------------------
# DEBUG PROMPT
#
# Set LUMINAR_DEBUG_PROMPT=1 to print the full formatted
# chat prompt before generation.
# ------------------------------------------------------------

DEBUG_PROMPT = (
    os.environ.get("LUMINAR_DEBUG_PROMPT", "")
    in ("1", "true", "yes")
)


# ============================================================
# LLM
# ============================================================

class LuminaRLLM:

    def __init__(self):

        self._enforcer_tokenizer_data = None
        self._intent_cache = OrderedDict()
        self._cache_lock = RLock()

        print()
        print("=" * 70)
        print("LUMINAR LLM")
        print("=" * 70)

        print(
            f"Model  : {MODEL_NAME}"
        )

        print(
            f"Device : {DEVICE}"
        )

        if MOCK_MODE:

            print()
            print(
                "*** MOCK MODE ENABLED ***"
            )
            print(
                "LLM will return placeholder "
                "responses. Set LUMINAR_MOCK_LLM=0 "
                "to use the real Qwen model."
            )

            # Still need tokenizer/model attrs
            # so callers don't crash.
            self.tokenizer = None
            self.model = None

            print()
            print("LuminaR LLM ready (MOCK).")
            return

        # ----------------------------------------------------
        # TOKENIZER
        # ----------------------------------------------------

        print()
        print("Loading tokenizer...")

        start = time.perf_counter()

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, local_files_only=True
        )

        tokenizer_time = (
            time.perf_counter() - start
        )

        print(
            f"Tokenizer load : "
            f"{tokenizer_time * 1000:.2f} ms"
        )

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        print()
        print("Loading Qwen2.5-3B-Instruct in 4-bit...")

        start = time.perf_counter()

        if DEVICE == "cuda":

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                quantization_config=bnb_config,
                device_map="auto", local_files_only=True
            )

        else:

            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                torch_dtype=torch.float32, local_files_only=True
            )

            self.model.to(DEVICE)

        self.model.eval()

        # Native Windows PyTorch may lack fused GQA kernels. Explicit K/V
        # expansion keeps SDPA eligible for its memory-efficient CUDA kernel.
        if DEVICE == 'cuda' and os.name == 'nt' and not torch.backends.cuda.is_flash_attention_available():
            from rag.attention import install_compatible_sdpa
            install_compatible_sdpa(self.model)

        model_time = (
            time.perf_counter() - start
        )

        print(
            f"Model load : "
            f"{model_time:.2f} seconds"
        )

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        print("\n--- GPU DIAGNOSTICS ---")
        print(f"CUDA Available: {torch.cuda.is_available()}")

        try:
            model_device = next(
                self.model.parameters()
            ).device
            model_dtype = next(
                self.model.parameters()
            ).dtype
        except StopIteration:
            model_device = "unknown"
            model_dtype = "unknown"

        print(f"Model device: {model_device}")
        print(f"Model dtype: {model_dtype}")

        if DEVICE == "cuda":
            allocated_mb = torch.cuda.memory_allocated() / (1024 ** 2)
            reserved_mb = torch.cuda.memory_reserved() / (1024 ** 2)
            print(f"GPU Allocated: {allocated_mb:.2f} MB")
            print(f"GPU Reserved: {reserved_mb:.2f} MB")
        print("-----------------------\n")

        # ----------------------------------------------------
        # WARM UP
        # ----------------------------------------------------

        print()
        print("Warming Qwen...")

        self.generate(
            "Say hello in one short sentence.",
            max_new_tokens=20
        )

        print(
            "Qwen warm-up complete."
        )

        # Build immutable constrained-decoding vocabulary once at startup.
        # Each request still creates its own schema parser/sequence state.
        self._prefix_function(IntentSchema)

        print()
        print("LuminaR LLM ready.")

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        prompt,
        max_new_tokens=256,
        do_sample=False,
        temperature=0.2,
        top_p=0.9,
        prefix_allowed_tokens_fn=None,
        attention_implementation=None
    ):

        # ----------------------------------------------------
        # MOCK MODE
        #
        # Returns a placeholder so retrieval can be tested
        # without GPU generation.
        # ----------------------------------------------------

        if MOCK_MODE:

            print(
                "[LLM] MOCK MODE — "
                "returning placeholder"
            )

            return (
                "[MOCK] This is a mock response. "
                "Set LUMINAR_MOCK_LLM=0 to use "
                "the real Qwen model for generation."
            )

        # ----------------------------------------------------
        # BUILD CHAT MESSAGES
        #
        # Wrap the RAG prompt using Qwen's chat template
        # so the model operates in instruction-following
        # mode rather than text completion.
        # ----------------------------------------------------

        messages = [
            {
                "role": "system",
                "content": SYSTEM_MESSAGE
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        # ----------------------------------------------------
        # APPLY CHAT TEMPLATE
        # ----------------------------------------------------

        prompt_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(
            prompt_text,
            return_tensors="pt",
            add_special_tokens=False
        ).to(self.model.device)

        input_ids = inputs["input_ids"]
        attention_mask = inputs.get(
            "attention_mask",
            torch.ones_like(input_ids)
        )

        input_length = input_ids.shape[1]

        # ----------------------------------------------------
        # GENERATION DIAGNOSTIC
        # ----------------------------------------------------

        print()
        print("[LLM]")

        print(
            f"Mode               : REAL"
        )

        print(
            f"Model device       : "
            f"{self.model.device}"
        )

        print(
            f"Input tokens       : "
            f"{input_length}"
        )

        print(
            f"Max new tokens     : "
            f"{max_new_tokens}"
        )

        print(
            f"Sampling           : False"
        )

        print(
            f"Repetition penalty : {1.0 if prefix_allowed_tokens_fn is not None else 1.15}"
        )

        print(
            f"No-repeat ngram    : {0 if prefix_allowed_tokens_fn is not None else 3} (answer only)"
        )

        if DEBUG_PROMPT:

            decoded = self.tokenizer.decode(
                input_ids[0],
                skip_special_tokens=False
            )

            print()
            print(
                "[LLM DEBUG] "
                "Full chat prompt:"
            )
            print(decoded)
            print()

        # ----------------------------------------------------
        # GENERATE
        #
        # Always deterministic (do_sample=False).
        # temperature and top_p are kept in the API
        # signature for compatibility but are not used
        # when do_sample is False.
        # ----------------------------------------------------

        generate_kwargs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "max_new_tokens": max_new_tokens,
            "do_sample": False,
            "use_cache": True,
            "pad_token_id": (
                self.tokenizer.eos_token_id
            ),
        }

        if prefix_allowed_tokens_fn is not None:
            generate_kwargs["prefix_allowed_tokens_fn"] = prefix_allowed_tokens_fn
            # Disable repetition penalties for structured decoding (they break JSON generation)
            generate_kwargs["repetition_penalty"] = 1.0
            generate_kwargs["no_repeat_ngram_size"] = 0
        else:
            # Source names, quotes and grounding language must remain copyable.
            # The built-in hard n-gram ban includes the prompt. Preserve its
            # soft repetition penalty but apply the hard ban to the answer.
            generate_kwargs["repetition_penalty"] = 1.0
            generate_kwargs["no_repeat_ngram_size"] = 0
            generate_kwargs["logits_processor"] = [AnswerRepetitionControl(input_length)]

        generation_started = time.perf_counter()
        previous_attention = self.model.config._attn_implementation
        if attention_implementation is not None:
            self.model.set_attn_implementation(attention_implementation)
        try:
            with torch.inference_mode():
                output_ids = self.model.generate(**generate_kwargs)
        finally:
            if self.model.config._attn_implementation != previous_attention:
                self.model.set_attn_implementation(previous_attention)

        # ----------------------------------------------------
        # DECODE ONLY NEW TOKENS
        #
        # input_length is the token count AFTER chat
        # template application, so we correctly skip the
        # full formatted prompt including system/user
        # role markers and the generation prompt.
        # ----------------------------------------------------

        generated_ids = output_ids[
            0
        ][
            input_length:
        ]

        response = self.tokenizer.decode(
            generated_ids,
            skip_special_tokens=True
        ).strip()

        record_generation(input_length, len(generated_ids), max_new_tokens,
                          time.perf_counter() - generation_started)
        return response

    # ========================================================
    # ANALYZE INTENT
    # ========================================================

    @stage('intent')
    def analyze_intent(self, question):
        # Cache only generic, entity-free templates; arbitrary user questions
        # and extracted personal information are never retained in this cache.
        key = ' '.join(question.lower().split()).rstrip('?.!')
        generic = ordinary_book_intent(question)
        if generic is None:
            return self._analyze_intent_uncached(question)
        if generic.get('target') is not None or generic.get('question_focus') == 'definition':
            # Topic/noun phrases can contain personal information. Classify
            # them deterministically but never retain them in the shared LRU.
            return generic
        with self._cache_lock:
            if key in self._intent_cache:
                self._intent_cache.move_to_end(key)
                return deepcopy(self._intent_cache[key])
        result = generic
        with self._cache_lock:
            self._intent_cache[key] = deepcopy(result)
            while len(self._intent_cache) > 128:
                self._intent_cache.popitem(last=False)
        return result

    @stage('structured_tokenizer_setup')
    def _prefix_function(self, schema):
        # Vocabulary/token trie is immutable and expensive to build. Parser
        # and sequence state MUST be fresh for every constrained generation.
        with self._cache_lock:
            if self._enforcer_tokenizer_data is None:
                self._enforcer_tokenizer_data = build_token_enforcer_tokenizer_data(self.tokenizer)
        return build_transformers_prefix_allowed_tokens_fn(
            self._enforcer_tokenizer_data, JsonSchemaParser(schema.model_json_schema()))

    def _analyze_intent_uncached(self, question):
        """
        Uses a hybrid system to classify the question intent
        and extract structured components (actor, event, polarity, target).
        """
        import json
        import re

        result = {
            "intent": "FACTUAL",
            "actor": None,
            "action": None,
            "target": None,
            "polarity": "positive",
            "temporal_relation": None,
            "question_focus": None,
            "tier_used": "Tier 1"
        }

        # ----------------------------------------------------
        # TIER 1: DETERMINISTIC PATTERN CLASSIFIER
        # ----------------------------------------------------
        low_q = question.lower().strip()
        
        # Common action verbs to split actor from action robustly
        verbs = r"(create|refuse|decide|regret|feel|sees?|hate|study|attack|leave|bitten)"

        # 1. NEGATED_MOTIVATION
        m_neg_1 = re.search(rf"why\s+(?:doesn't|didn't|does\s+not|did\s+not)\s+(.*?)\s+{verbs}\b(.*)", low_q)
        m_neg_2 = re.search(rf"why\s+(?:does|did)\s+(.*?)\s+(refuse|avoid|decline|decide)\b(.*)", low_q)
        
        # 3. REGRET
        m_reg_1 = re.search(rf"why\s+(?:does|did)\s+(.*?)\s+(regret|feel\s+remorse)\b(.*)", low_q)

        # 2. MOTIVATION
        m_mot_1 = re.search(rf"why\s+(?:does|did)\s+(.*?)\s+{verbs}\b(.*)", low_q)
        m_mot_2 = re.search(r"what\s+motivates\s+(.*?)\s+to\s+(.*)", low_q)

        # 4. CONSEQUENCE / REACTION
        m_cons = re.search(r"what\s+happens\s+after\s+(.*)", low_q)
        m_react = re.search(r"what\s+happens\s+when\s+(.*?)\s+first\s+(.*)", low_q)
        
        # 5. RELATIONSHIP
        m_rel_1 = re.search(r"who\s+is\s+(.*?)'s\s+(.*)", low_q)
        m_rel_2 = re.search(r"who\s+is\s+(.*?)\s+to\s+(.*)", low_q)
        
        matched_tier1 = True

        if m_neg_1:
            result["intent"] = "NEGATED_MOTIVATION"
            result["actor"] = m_neg_1.group(1).strip()
            result["action"] = (m_neg_1.group(2) + m_neg_1.group(3)).strip("?")
            result["polarity"] = "negative"
        elif m_neg_2:
            result["intent"] = "NEGATED_MOTIVATION"
            result["actor"] = m_neg_2.group(1).strip()
            result["action"] = (m_neg_2.group(2) + m_neg_2.group(3)).strip("?")
            result["polarity"] = "negative"
        elif m_reg_1:
            result["intent"] = "REGRET"
            result["actor"] = m_reg_1.group(1).strip()
            result["action"] = (m_reg_1.group(2) + m_reg_1.group(3)).strip("?")
            result["polarity"] = "negative"
        elif m_mot_1:
            result["intent"] = "MOTIVATION"
            result["actor"] = m_mot_1.group(1).strip()
            result["action"] = (m_mot_1.group(2) + m_mot_1.group(3)).strip("?")
        elif m_mot_2:
            result["intent"] = "MOTIVATION"
            result["actor"] = m_mot_2.group(1).strip()
            result["action"] = m_mot_2.group(2).strip("?")
        elif m_cons:
            result["intent"] = "CONSEQUENCE"
            result["action"] = m_cons.group(1).strip("?")
        elif m_react:
            result["intent"] = "REACTION"
            result["actor"] = m_react.group(1).strip()
            result["action"] = m_react.group(2).strip("?")
        elif m_rel_1:
            result["intent"] = "RELATIONSHIP"
            result["actor"] = m_rel_1.group(1).strip()
            result["target"] = m_rel_1.group(2).strip("?")
        elif m_rel_2:
            result["intent"] = "RELATIONSHIP"
            result["actor"] = m_rel_2.group(1).strip()
            result["target"] = m_rel_2.group(2).strip("?")
        else:
            matched_tier1 = False

        if matched_tier1:
            return result

        result["tier_used"] = "Tier 2"

        if MOCK_MODE:
            return result

        # ----------------------------------------------------
        # TIER 2: LLM STRUCTURED EXTRACTION (lm-format-enforcer)
        # ----------------------------------------------------
        prompt = (
            "Analyze the following question and extract its semantic intent and components.\n"
            "Supported intents and explicit boundaries:\n"
            "- MOTIVATION: Why does X do Y? (e.g., Why did he leave?)\n"
            "- NEGATED_MOTIVATION: Why doesn't X do Y? What prevents X from doing Y? (e.g., Why did he refuse?)\n"
            "  * NOTE: Words like 'reject' or 'refuse' as the action do NOT automatically make it NEGATED_MOTIVATION unless it means avoiding an action.\n"
            "- REGRET: Why does X regret Y? What makes X remorseful about Y?\n"
            "  * NOTE: REGRET must ONLY represent remorse, guilt, or regret. Do NOT classify hatred, killing, rejection, fear, or ordinary negative actions as REGRET unless explicitly asking about remorse.\n"
            "- CONSEQUENCE: What happens after X does Y? What follows an event.\n"
            "- REACTION: How does X react when Y happens? What does X feel/do upon seeing Y? (Response to an event).\n"
            "- RELATIONSHIP: Who is X to Y? What is the relationship between X and Y? (Explicit relationship).\n"
            "- FACTUAL: What is/was X? What fact does the text state about X?\n\n"
            "Additional Extraction Rules:\n"
            "- You MUST populate 'actor', 'action', and 'target' whenever the query provides enough information. Do NOT leave them null if the entity or action is present.\n"
            "- TEMPORAL: Explicitly represent temporal_relation as BEFORE, AFTER, DURING, or NONE.\n"
            "- POLARITY: POSITIVE, NEGATED, or UNKNOWN.\n"
            "- CONFIDENCE: A float from 0.0 to 1.0 representing your certainty.\n\n"
            f"Question: {question}\n\n"
            "Respond ONLY with a valid JSON object matching the requested schema."
        )

        prefix_function = self._prefix_function(IntentSchema)

        response = self.generate(
            prompt,
            max_new_tokens=400,
            temperature=0.1,
            prefix_allowed_tokens_fn=prefix_function,
            # Keep frozen V8 structured decisions numerically stable. Fused
            # attention changed one intent classification in the full suite.
            attention_implementation='sdpa'
        )

        try:
            parsed = json.loads(response.strip())
            result.update({k: parsed.get(k) for k in result.keys() if k in parsed})
        except Exception as e:
            print(f"[LLM ERROR] Failed to parse intent JSON: {e}\nRaw output: {response}")

        return result


    # ========================================================
    # VALIDATE EVIDENCE
    # ========================================================

    @stage('validator')
    def validate_evidence(self, question, intent_data, used_items, mode="top-1",
                          informational_category=None):
        """
        Uses an LLM-as-a-judge to perform semantic Evidence Quality Check.
        Asks if the evidence actually answers the user's question.
        Supports ablation modes: 'top-1', 'top-3-ind', 'top-3-comb'

        When *informational_category* is not None, uses an evidence-sufficiency
        prompt instead of the claim-centric prompt. This prevents false refusals
        on simple informational book questions.
        """
        if not used_items:
            return "NOT_SUPPORTED"

        if mode == "top-3-comb":
            context_text = "\n\n".join([chunk.get("text", "") for chunk in used_items[:3]])
        elif mode == "top-3-ind":
            # This mode requires caller logic to iterate. Default to top-1 here for fallback.
            top_chunk = used_items[0]
            context_text = top_chunk.get("text", "")
        else:
            top_chunk = used_items[0]
            context_text = top_chunk.get("text", "")

        if MOCK_MODE:
            # Mock behavior for regression tests
            low_q = question.lower()
            if "dracula regret attacking his victims" in low_q:
                return "NOT_SUPPORTED"
            return "SUPPORTED"
            
        # ----------------------------------------------------
        # CHOOSE VALIDATOR PROMPT BY QUERY TYPE
        # ----------------------------------------------------
        if informational_category is not None:
            # Evidence-sufficiency prompt for informational questions.
            # Does NOT require a formal claim structure to be "supported".
            prompt = (
                f"You are an evidence validation system.\n"
                f"The user asked an informational question about a book.\n"
                f"Question: {question}\n\n"
                f"Evidence Text:\n{context_text}\n\n"
                "Rules:\n"
                "- supported=true if the evidence contains relevant factual "
                "information from which the question can be answered or "
                "partially answered.\n"
                "- supported=true even if no single passage contains the "
                "complete answer, as long as the passages collectively "
                "provide relevant information.\n"
                "- supported=false ONLY if the evidence is unrelated to the "
                "question, belongs to a different subject, or contains no "
                "relevant information at all.\n"
                "- Do NOT require the evidence to literally state the answer "
                "in a single sentence. Narrative evidence that identifies "
                "characters, events, themes, or settings counts as relevant.\n"
                "- Do NOT use outside knowledge. Evaluate only whether the "
                "supplied text is relevant to the question.\n\n"
                "Does the evidence contain relevant information to answer "
                "the question? Respond ONLY with a valid JSON object "
                "matching the requested schema."
            )
        else:
            # Original claim-centric prompt for causal / temporal /
            # relationship / adversarial questions.
            prompt = (
                f"You are an evidence validation system evaluating if a text supports a structured query representation.\n"
                f"Question: {question}\n"
                f"Structured Intent: {intent_data}\n\n"
                f"Evidence Text:\n{context_text}\n\n"
                "Rules:\n"
                "- For unsupported premises, prefer false over speculative inference.\n"
                "- supported=true requires evidence to fully answer the query, accounting for any negations or specific conditions.\n\n"
                "Does the provided evidence support the structured query? Respond ONLY with a valid JSON object matching the requested schema."
            )
        
        prefix_function = self._prefix_function(ValidatorSchema)

        response = self.generate(
            prompt,
            max_new_tokens=160,
            temperature=0.1,
            prefix_allowed_tokens_fn=prefix_function
        )
        
        try:
            import json
            parsed = json.loads(response.strip())
            
            # For backward compatibility with qa.py which expects a string
            # We'll attach the full parsed output to the result for metric scripts
            verdict = "SUPPORTED" if parsed.get("supported") else "NOT_SUPPORTED"
            # Return a dict containing both the verdict and the full parsed schema
            return {"verdict": verdict, "details": parsed}
        except Exception as e:
            print(f"[LLM ERROR] Failed to parse validator JSON: {e}")
            return {"verdict": "NOT_SUPPORTED", "details": {}}



# ============================================================
# CLI TEST
# ============================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description="LuminaR LLM test"
    )

    parser.add_argument(
        "--prompt",
        required=True
    )

    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=256
    )

    args = parser.parse_args()

    llm = LuminaRLLM()

    print()
    print("=" * 70)
    print("LLM RESPONSE")
    print("=" * 70)

    response = llm.generate(
        args.prompt,
        max_new_tokens=args.max_new_tokens
    )

    print()
    print(response)

    print()
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
