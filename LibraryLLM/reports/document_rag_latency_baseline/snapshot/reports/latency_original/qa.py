from pathlib import Path
import time

from rag.reranker import RAGReranker
from rag.llm import LuminaRLLM
from rag.fast_filter import run_fast_filter


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ------------------------------------------------------------
# UNIFIED DEPTH CONFIG
#
# Each depth level controls ALL three dimensions:
#
#   candidates     — how many FAISS vectors to retrieve
#                    before reranking
#
#   context_chunks — how many reranked chunks are included
#                    in the Qwen prompt
#
#   max_tokens     — maximum tokens Qwen may generate
#
# This ensures depth affects both retrieval breadth
# AND generation length.
# ------------------------------------------------------------

DEPTH_CONFIG = {

    "concise": {
        "candidates": 10,
        "context_chunks": 4,
        "max_tokens": 300
    },

    "normal": {
        "candidates": 15,
        "context_chunks": 7,
        "max_tokens": 600
    },

    "detailed": {
        "candidates": 20,
        "context_chunks": 10,
        "max_tokens": 1000
    },

    "comprehensive": {
        "candidates": 20,
        "context_chunks": 15,
        "max_tokens": 1500
    }

}


# Maximum approximate context characters.
#
# This is a safety limit to prevent sending more text
# to Qwen than its context window can handle.

MAX_CONTEXT_CHARS = 24000


# ============================================================
# RAG QA ENGINE
# ============================================================

class LuminaRAG:

    def __init__(self):

        print()
        print("=" * 70)
        print("LUMINAR RAG QA ENGINE")
        print("=" * 70)

        # ----------------------------------------------------
        # LOAD RETRIEVER + RERANKER
        # ----------------------------------------------------

        print()
        print(
            "Loading RAG retriever + reranker..."
        )

        self.reranker = RAGReranker()

        # ----------------------------------------------------
        # LOAD LLM
        # ----------------------------------------------------

        print()
        print(
            "Loading LuminaR LLM..."
        )

        self.llm = LuminaRLLM()

        print()
        print("=" * 70)
        print("LUMINAR RAG QA ENGINE READY")
        print("=" * 70)

    # ========================================================
    # GET DEPTH CONFIG
    # ========================================================

    def get_depth_config(
        self,
        depth
    ):

        depth = str(
            depth
        ).lower().strip()

        if depth not in DEPTH_CONFIG:

            depth = "normal"

        return depth, DEPTH_CONFIG[
            depth
        ]

    # ========================================================
    # BUILD CONTEXT
    # ========================================================

    def select_diverse_context(
        self,
        results,
        max_chunks
    ):
        if not results:
            return []
            
        import re
        def get_terms(text):
            return set(re.findall(r"\b[a-zA-Z]{3,}\b", text.lower()))
            
        unselected = list(results)
        for item in unselected:
            if "terms" not in item:
                item["terms"] = get_terms(item.get("text", ""))
                
        selected = []
        
        while len(selected) < max_chunks and unselected:
            best_idx = -1
            best_score = -float('inf')
            best_redundancy = 0.0
            
            for i, item in enumerate(unselected):
                redundancy = 0.0
                if selected:
                    max_sim = 0.0
                    for s in selected:
                        intersection = len(item["terms"] & s["terms"])
                        union = len(item["terms"] | s["terms"])
                        sim = intersection / union if union > 0 else 0
                        if sim > max_sim:
                            max_sim = sim
                    redundancy = max_sim
                    
                penalty = 0.3 * redundancy
                context_score = item.get("final_score", 0.0) - penalty
                
                if context_score > best_score:
                    best_score = context_score
                    best_idx = i
                    best_redundancy = redundancy
                    
            chosen = unselected.pop(best_idx)
            chosen["redundancy_penalty"] = 0.3 * best_redundancy
            chosen["final_context_score"] = chosen.get("final_score", 0.0) - chosen["redundancy_penalty"]
            selected.append(chosen)
            
        # Clean up terms
        for item in selected:
            if "terms" in item:
                del item["terms"]
                
        return selected

    def build_context(
        self,
        results,
        max_chunks
    ):

        selected_results = self.select_diverse_context(results, max_chunks)

        context_parts = []
        used_items = []
        total_chars = 0
        context_count = 0

        for item in selected_results:

            title = item.get("title", "")
            author = item.get("author", "")
            chapter = item.get("chapter", "Unknown")
            filename = item.get("filename", "Unknown document")
            page = item.get("page")
            text = item.get("text", "").strip()

            if not text:
                continue

            # ------------------------------------------------
            # BOOK-CENTRIC SOURCE INFORMATION
            # ------------------------------------------------

            source_header = ""
            if title:
                source_header += f"Book: {title}\n"
            if author:
                source_header += f"Author: {author}\n"
            if chapter:
                source_header += f"Chapter: {chapter}\n"
            if page is not None:
                source_header += f"Page: {page}\n"

            context_count += 1

            source_text = (
                f"[Source {context_count}]\n"
                f"{source_header}"
                f"File: {filename}\n\n"
                f"{text}\n"
            )

            # ------------------------------------------------
            # CONTEXT SIZE LIMIT
            # ------------------------------------------------

            if total_chars + len(source_text) > MAX_CONTEXT_CHARS:
                break

            context_parts.append(source_text)
            used_items.append(item)
            total_chars += len(source_text)

        return (
            "\n".join(context_parts),
            used_items,
            total_chars
        )

    # ========================================================
    # BUILD PROMPT
    # ========================================================

    def build_prompt(
        self,
        question,
        context,
        depth
    ):

        if depth == "concise":

            style = """
Give a short and direct answer.
Focus only on the most important information.
Do not add unnecessary explanation.
"""

        elif depth == "detailed":

            style = """
Give a detailed explanation.

Cover the important concepts, events,
characters, themes, processes, examples,
and relationships present in the context.

Synthesize information from multiple passages
rather than repeating them separately.

Use headings, numbered points, or bullet points
where useful.

Make sure the answer is complete and does not
stop in the middle of a list or explanation.
"""

        elif depth == "comprehensive":

            style = """
Give a comprehensive explanation.

Cover all important information from the supplied
context that is relevant to the question.

Synthesize and connect information across multiple
passages to build a thorough answer.

Explain concepts step by step.

Use headings, numbered points, tables, or bullet
points where appropriate.

Make the answer complete and organized.

Do not pad the answer with information that is
not supported by the context. Comprehensive means
deeper synthesis, not more unsupported facts.

Do not stop in the middle of a list or explanation.
"""

        else:

            style = """
Give a clear and complete explanation with enough
detail to properly answer the question.

Cover all major points supported by the context.

Use numbered points or bullet points when the
question asks for multiple items.

Make sure the answer is complete and does not
stop in the middle of a list.
"""

        prompt = f"""Answer the following question using ONLY the
information provided in the CONTEXT below.

RULES:

1. Use ONLY the supplied context as evidence.
   Do not use pretrained knowledge or world knowledge
   to fill gaps where the context is silent.

2. If the context does not contain enough information,
   say: "The provided context does not contain enough
   information to answer this reliably."

3. Do not invent events, dialogue, motivations,
   relationships, or intentions not present in the
   context.

4. Do not infer a character's motivation from
   consequences or later events unless the context
   explicitly supports that motivation.

5. Do not turn literary interpretation into factual
   claims. If interpreting, signal it clearly.

6. Do not continue, imitate, or recreate the source
   text. Do not write fictional narrative. Do not
   imitate the author's writing style.

7. Do not repeat the same point. Answer each point
   once. Do not restate the conclusion in multiple
   paragraphs. Do not repeat sentences.

8. Do not include [Source 1], [Source 2], or any
   [Source X] marker in your answer.

9. Do not mention the prompt, context, retrieval
   system, model, or these instructions.

10. Do not begin with phrases like "To answer the
    question directly" or "In summary" unless a
    summary is genuinely useful.

11. Do not generate additional discussion, notes,
    or caveats after the answer is complete.

12. Answer the question directly.

13. Prefer a short answer supported by the strongest
    evidence over a long answer that fills the token
    budget with weaker claims.

14. When the context comes from a specific book,
    answer specifically about that book.

15. For causal questions (why, what caused, what
    motivated), distinguish between:
    - What is explicitly stated in the context
    - What is strongly implied by the context
    - What is not established by the context
    Only report what the context supports.

16. Do not invent dialogue or speech that does not appear
    verbatim in the context. If quoting a character, use
    only words that appear in the supplied passages.

17. For "what happens after" or consequence questions,
    describe ONLY the immediate events shown in the
    context passages. Do not jump forward to events
    from later chapters unless those later events are
    explicitly present in the supplied context.

18. Do not combine or merge events from different sources
    into a single narrative unless the context explicitly
    connects them. Keep separate events distinct.

ANSWER STYLE:
{style}

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""

        return prompt.strip()

    # ========================================================
    # SECOND PASS RETRIEVAL
    # ========================================================

    def _second_pass_retrieval(self, question, intent_data, work_id, document_id, candidate_k):
        from rag.evidence import extract_important_terms, expand_terms_with_concepts
        
        q_terms = extract_important_terms(question)
        if not q_terms:
            return []
            
        expanded, roots = expand_terms_with_concepts(q_terms)
        
        new_terms = [t for t in expanded if t not in q_terms and len(t) >= 3]
        if not new_terms:
            return []
            
        second_query = " ".join(new_terms[:6])
        
        search_result = self.reranker.search(
            query=second_query,
            top_k=candidate_k,
            document_id=document_id,
            work_id=work_id,
            intent_data=intent_data
        )
        
        return search_result.get("results", [])

    def _merge_results(self, original_results, new_results):
        merged = {}
        for item in original_results:
            merged[item.get("chunk_id")] = item
            
        for item in new_results:
            cid = item.get("chunk_id")
            if cid in merged:
                if item.get("final_score", 0) > merged[cid].get("final_score", 0):
                    merged[cid] = item
            else:
                merged[cid] = item
                
        merged_list = list(merged.values())
        merged_list.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        
        for rank, item in enumerate(merged_list, start=1):
            item["rank"] = rank
            
        return merged_list

    # ========================================================
    # ASK
    # ========================================================

    def ask(
        self,
        question,
        depth="normal",
        document_id=None,
        work_id=None
    ):

        if question is None:

            question = ""

        question = str(
            question
        ).strip()

        if not question:

            return {
                "question":
                    question,

                "answer":
                    "Please enter a question.",

                "sources": []
            }

        # ----------------------------------------------------
        # BACKWARDS COMPATIBILITY
        # ----------------------------------------------------

        if (
            not work_id
            and document_id
        ):

            work_id = document_id

        # ----------------------------------------------------
        # VALIDATE DEPTH
        # ----------------------------------------------------

        depth, config = (
            self.get_depth_config(
                depth
            )
        )

        # ----------------------------------------------------
        # GET LIMITS FROM UNIFIED CONFIG
        # ----------------------------------------------------

        candidate_k = config[
            "candidates"
        ]

        max_chunks = config[
            "context_chunks"
        ]

        generation_tokens = config[
            "max_tokens"
        ]

        total_start = (
            time.perf_counter()
        )

        # ----------------------------------------------------
        # ANALYZE INTENT
        # ----------------------------------------------------
        
        intent_start = time.perf_counter()
        
        intent_data = self.llm.analyze_intent(question)
        
        intent_time = time.perf_counter() - intent_start

        # ----------------------------------------------------
        # RETRIEVE + RERANK
        # ----------------------------------------------------

        retrieval_start = (
            time.perf_counter()
        )

        search_result = (
            self.reranker.search(
                query=question,
                top_k=candidate_k,
                document_id=document_id,
                work_id=work_id,
                intent_data=intent_data
            )
        )

        retrieval_time = (
            time.perf_counter()
            - retrieval_start
        )

        results = search_result.get(
            "results",
            []
        )

        # ----------------------------------------------------
        # NO RESULTS
        # ----------------------------------------------------

        if not results:

            if work_id:

                message = (
                    "I couldn't find enough information "
                    "in this book to answer this question."
                )

            else:

                message = (
                    "I couldn't find enough information "
                    "in the uploaded documents to answer "
                    "this question."
                )

            return {
                "question":
                    question,

                "answer":
                    message,

                "sources": [],

                "depth":
                    depth,

                "work_id":
                    work_id,

                "timing_ms": {
                    "retrieval":
                        round(
                            retrieval_time * 1000,
                            2
                        )
                }
            }

        # ----------------------------------------------------
        # BUILD DYNAMIC CONTEXT
        # ----------------------------------------------------

        (
            context,
            used_items,
            context_chars
        ) = self.build_context(
            results,
            max_chunks
        )

        # ----------------------------------------------------
        # FAST FILTER GATE (V7)
        # ----------------------------------------------------

        fast_filter_start = time.perf_counter()
        fast_filter_result = run_fast_filter(
            question=question,
            intent_data=intent_data,
            evidence_items=used_items,
            mode="combined"
        )
        fast_filter_decision_val = fast_filter_result.get("decision", "NEEDS_LLM_VALIDATION")
        fast_filter_time = time.perf_counter() - fast_filter_start

        # ----------------------------------------------------
        # EVIDENCE QUALITY CHECK
        # ----------------------------------------------------

        validation_start = time.perf_counter()

        if fast_filter_decision_val == "FAST_REJECT":
            verdict = "NOT_SUPPORTED"
            validation_result = {
                "verdict": "NOT_SUPPORTED",
                "details": {},
                "fast_filter": "FAST_REJECT"
            }
        elif fast_filter_decision_val == "FAST_ACCEPT":
            verdict = "SUPPORTED"
            validation_result = {
                "verdict": "SUPPORTED",
                "details": {},
                "fast_filter": "FAST_ACCEPT"
            }
        else:
            # NEEDS_LLM_VALIDATION — run existing LLM validator
            validation_result = self.llm.validate_evidence(question, intent_data, used_items, mode="top-3-comb")
            verdict = validation_result.get("verdict", "NOT_SUPPORTED") if isinstance(validation_result, dict) else validation_result
        
            if verdict == "PARTIALLY_SUPPORTED":
                second_pass_results = self._second_pass_retrieval(
                    question, intent_data, work_id, document_id, candidate_k
                )
                if second_pass_results:
                    merged = self._merge_results(results, second_pass_results)
                    context, used_items, context_chars = self.build_context(merged, max_chunks)
                    validation_result2 = self.llm.validate_evidence(question, intent_data, used_items)
                    verdict = validation_result2.get("verdict", "NOT_SUPPORTED") if isinstance(validation_result2, dict) else validation_result2
        
        validation_time = time.perf_counter() - validation_start

        # ----------------------------------------------------
        # BUILD PROMPT
        # ----------------------------------------------------

        prompt = self.build_prompt(
            question,
            context,
            depth
        )
        
        if verdict == "NOT_SUPPORTED":
            modifier = "The retrieved evidence does not support the premise of the user's question. Do not invent an answer. Explicitly state that the source material does not establish the premise."
            prompt = modifier + "\n\n" + prompt
        elif verdict == "PARTIALLY_SUPPORTED":
            modifier = "The retrieved evidence only partially supports the premise of the user's question. Acknowledge this limitation in your answer."
            prompt = modifier + "\n\n" + prompt

        # ----------------------------------------------------
        # GENERATE ANSWER
        # ----------------------------------------------------

        generation_start = (
            time.perf_counter()
        )

        answer = self.llm.generate(
            prompt,
            max_new_tokens=
                generation_tokens,
            temperature=0.0,
            top_p=0.9
        )

        generation_time = (
            time.perf_counter()
            - generation_start
        )

        # ----------------------------------------------------
        # SOURCES
        # ----------------------------------------------------

        sources = []

        seen = set()

        for item in used_items:

            # ------------------------------------------------
            # Use chunk_id as primary deduplication key.
            #
            # This is important for books because page is None.
            # ------------------------------------------------

            key = item.get(
                "chunk_id"
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            sources.append(
                {
                    "filename":
                        item.get(
                            "filename"
                        ),

                    "page":
                        item.get(
                            "page"
                        ),

                    "chapter":
                        item.get(
                            "chapter"
                        ),

                    "chunk_id":
                        item.get(
                            "chunk_id"
                        ),

                    "work_id":
                        item.get(
                            "work_id",
                            work_id
                        ),

                    "title":
                        item.get(
                            "title"
                        ),

                    "author":
                        item.get(
                            "author"
                        ),

                    "rerank_score":
                        item.get(
                            "rerank_score"
                        ),

                    "rank": item.get("rank"),
                    "normalized_rerank_score": item.get("normalized_rerank_score"),
                    "evidence_score": item.get("evidence_score"),
                    "faiss_norm": item.get("faiss_norm"),
                    "actor_alignment": item.get("actor_alignment"),
                    "event_alignment": item.get("event_alignment"),
                    "local_causal_score": item.get("local_causal_score"),
                    "speaker_score": item.get("speaker_score"),
                    "first_person_narrative": item.get("first_person_narrative"),
                    "directional_subject_alignment": item.get("directional_subject_alignment"),
                    "temporal_phase_alignment": item.get("temporal_phase_alignment"),
                    "motivation_strength": item.get("motivation_strength"),
                    "consequence_strength": item.get("consequence_strength"),
                    "motivation_priority": item.get("motivation_priority"),
                    "redundancy_penalty": item.get("redundancy_penalty"),
                    "final_context_score": item.get("final_context_score", item.get("final_score")),
                    "evidence_signals": item.get("evidence_signals", [])
                }
            )

        # ----------------------------------------------------
        # TOTAL TIME
        # ----------------------------------------------------

        total_time = (
            time.perf_counter()
            - total_start
        )

        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return {

            "question":
                question,

            "depth":
                depth,

            "work_id":
                work_id,

            "answer":
                answer,

            "sources":
                sources,

            "intent_data":
                intent_data,

            "verdict":
                verdict,

            "fast_filter_decision":
                fast_filter_decision_val,

            "fast_filter_signals":
                fast_filter_result.get("signals", {}),

            "fast_filter_reasons":
                fast_filter_result.get("reasons", []),

            "retrieval": {

                "candidate_count":
                    search_result.get(
                        "candidate_count",
                        0
                    ),

                "context_count":
                    len(used_items),

                "context_characters":
                    context_chars

            },

            "timing_ms": {

                "intent_analysis":
                    round(
                        intent_time * 1000,
                        2
                    ),

                "retrieval":
                    round(
                        retrieval_time * 1000,
                        2
                    ),

                "fast_filter":
                    round(
                        fast_filter_time * 1000,
                        2
                    ),

                "validation":
                    round(
                        validation_time * 1000,
                        2
                    ),

                "generation":
                    round(
                        generation_time * 1000,
                        2
                    ),

                "total":
                    round(
                        total_time * 1000,
                        2
                    )

            }

        }


# ============================================================
# CLI
# ============================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "LuminaR RAG Question Answering"
        )
    )

    parser.add_argument(
        "--query",
        required=True
    )

    parser.add_argument(
        "--depth",
        choices=[
            "concise",
            "normal",
            "detailed",
            "comprehensive"
        ],
        default="normal"
    )

    parser.add_argument(
        "--document",
        default=None
    )

    parser.add_argument(
        "--work_id",
        default=None
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # LOAD ENGINE
    # --------------------------------------------------------

    engine = LuminaRAG()

    # --------------------------------------------------------
    # ASK
    # --------------------------------------------------------

    result = engine.ask(
        question=args.query,
        depth=args.depth,
        document_id=args.document,
        work_id=args.work_id
    )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LUMINAR RAG ANSWER")
    print("=" * 70)

    print()

    print(
        f"Question:\n"
        f"{result['question']}"
    )

    print()

    print(
        f"Depth: "
        f"{result['depth']}"
    )

    if result.get("work_id"):

        print()

        print(
            f"Work ID: "
            f"{result['work_id']}"
        )

    if result.get("intent_data"):
        print()
        print("Detected Intent Data:")
        import json
        print(json.dumps(result["intent_data"], indent=2))
        print()

    if result.get("verdict"):
        print(f"Evidence Verdict: {result['verdict']}\n")

    print("Answer:")

    print(
        result["answer"]
    )

    print()

    print("-" * 70)

    print("Sources:")

    for i, source in enumerate(
        result["sources"],
        start=1
    ):

        print("-" * 70)

        print(f"Rank          : {source.get('rank')}")
        print(f"Chunk ID      : {source.get('chunk_id')}")
        print(f"Chapter       : {source.get('chapter')}")
        print(f"CE Raw        : {source.get('rerank_score', 0):.4f}")
        print(f"CE Norm       : {source.get('normalized_rerank_score', 0):.4f}")
        print(f"Evidence      : {source.get('evidence_score', 0):.4f}")
        print(f"FAISS         : {source.get('faiss_norm', 0):.4f}")
        print(f"Actor Alignment: {source.get('actor_alignment', 0):.4f}")
        print(f"Event Alignment: {source.get('event_alignment', 0):.4f}")
        print(f"Local Causal  : {source.get('local_causal_score', 0):.4f}")
        print(f"Speaker       : {source.get('speaker_score', 0):.4f}")
        print(f"First Person Narrative: {source.get('first_person_narrative', 0):.4f}")
        print(f"Directional Alignment : {source.get('directional_subject_alignment', 0):.4f}")
        print(f"Temporal Phase Prior  : {source.get('temporal_phase_alignment', 0):.4f}")
        print(f"Motivation Strength   : {source.get('motivation_strength', 0):.4f}")
        print(f"Consequence Strength  : {source.get('consequence_strength', 0):.4f}")
        print(f"Motivation Priority   : {source.get('motivation_priority', 0):.4f}")
        print(f"Redundancy    : {source.get('redundancy_penalty', 0):.4f}")
        print(f"Final Context Score: {source.get('final_context_score', 0):.4f}")
        
        signals = source.get('evidence_signals', [])
        if signals:
            print("Signals       :")
            for s in signals:
                print(f"  + {s}")
        print()

        title = source.get(
            "title"
        )

        chapter = source.get(
            "chapter"
        )

        if title:

            print(
                f"{i}. {title}"
            )

        else:

            print(
                f"{i}. "
                f"{source.get('filename')}"
            )

        if chapter:

            print(
                f"   Chapter: "
                f"{chapter}"
            )

        print(
            f"   Chunk: "
            f"{source.get('chunk_id')}"
        )

    print()

    print("-" * 70)

    print(
        f"Candidates       : "
        f"{result['retrieval']['candidate_count']}"
    )

    print(
        f"Context chunks   : "
        f"{result['retrieval']['context_count']}"
    )

    print(
        f"Context chars    : "
        f"{result['retrieval']['context_characters']}"
    )

    print(
        f"Retrieval        : "
        f"{result['timing_ms']['retrieval']} ms"
    )

    print(
        f"Generation       : "
        f"{result['timing_ms']['generation']} ms"
    )

    print(
        f"Total            : "
        f"{result['timing_ms']['total']} ms"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()