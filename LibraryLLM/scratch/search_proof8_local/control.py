"""Semantic control is byte-frozen7r1, not a new production parser."""
from scratch.search_proof_recovery_v7r1 import parser
from scratch.search_proof_recovery_v7r1.restricted import parse as restricted_parse
from scratch.search_proof_recovery_v7r1.extraction import validate_proposal,compile_proposal
CANDIDATE_ID="search-smarteng-disabled-proof-8-local"
CONTROL_PARSER_VERSION=parser.PARSER_VERSION


def compact_ontology():
    """Generate model vocabulary from the same frozen enforcement ontology."""
    from scratch.search_proof_recovery_v7r1.ontology import DOMAINS
    return {name:{'native':d.native,'operators':d.operators,'operand_type':d.operand,'enforcement':d.enforcement} for name,d in DOMAINS.items()}
