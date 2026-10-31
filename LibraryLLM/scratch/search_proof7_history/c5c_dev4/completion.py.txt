"""Pure bound completion draft. No issuance, persistence, auth or commits."""
from dataclasses import dataclass
import re
from .contract import State,digest
from .parser import parse_query,validate,executable,PARSER_VERSION,_decode
from .proof import projection
from .proposals import FAMILIES

@dataclass(frozen=True)
class BoundContext:
    owner:str
    login_session:str
    library_id:str|None
    workspace:str
    parser_version:str
    mode:str
    query_digest:str
    base_version:int
    expires_at:float
    used:bool=False

def complete_draft(plan,requirement_id,value,issued,current,*,now,facets,capabilities,authorized=False):
    from .recompilation import issue_completion,recompile
    edit=issue_completion(plan,requirement_id,value,issued.base_version)
    return recompile(edit,plan,issued,current,now=now,facets=facets,capabilities=capabilities,authorized=authorized)
