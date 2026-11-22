"""Exact reviewed RAG source acceptance for the post-generation closure.

Historical baseline manifests and the v2o2 QA projection remain immutable.
This guard accepts the reviewed installed implementation only; the old QA
runtime remains historical evidence because it can cite a contradictory answer.
"""
import hashlib
from pathlib import Path


REVIEWED = {
    "rag/qa.py": "ab7f3d2baa5e828a5c2eb5fe6e6e9ac8bdb6e596cb3fe70348edb7bde88f9830",
    "rag/llm.py": "6f35a4034ae0acff78596b8cc81ed9c355a055f6560cf8dd703d907c02aab2da",
    "rag/fast_filter.py": "c76962d3427d0d14a70731bee43ddffdbbdb4b426ffe5e715bb3121d2fa5aaff",
    "rag/factual_evidence.py": "aec553cd0799bb2e5cfcfb8ab2f1136c51e9b5bc06d2f09800b7c96b9c898d0a",
    "rag/document_grounding.py": "61f809fdd8ca7b5b42aceead9ea07fd0602f780695f5f41d8d3779674fc1a180",
    "rag/generated_answer_verification.py": "c1e81fa77e7dd3139cc03ed13c095f12e1d6f576cac57349fa788260b9edbed9",
    "rag/citation_boundary.py": "5495a2deab7e240011b529045f53ab26893eb07f4aeefe9f14fb7d4188fadf8b",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_reviewed_file(root, relative, historical_hash):
    """Reject every unreviewed byte, even whitespace or an unrelated import."""
    actual = digest(Path(root) / relative)
    expected = REVIEWED.get(relative, historical_hash.lower())
    assert actual == expected, f"Unreviewed protected source: {relative}"


def assert_reviewed_rag_tree(root, historical_rows):
    root = Path(root)
    anchor = Path(historical_rows[0]["Path"]).parents[1]
    for row in historical_rows:
        if Path(row["Path"]).name == "api.py":
            continue  # Existing API authorization contract is checked elsewhere.
        relative = Path(row["Path"]).relative_to(anchor).as_posix()
        assert_reviewed_file(root, relative, row["Hash"])
    for relative in REVIEWED:
        assert_reviewed_file(root, relative, REVIEWED[relative])
    # The original QA projection helper remains independently frozen. Its old
    # bytes are evidence, not an alternate runtime accepted by this guard.
    assert digest(root / "tests/contracts/rag_grounding_v2o2.py") == (
        "966841216c41f64feb7da38a5cc7e9107a1f6b4a3eafbede75fcc39f119ed38b"
    )
