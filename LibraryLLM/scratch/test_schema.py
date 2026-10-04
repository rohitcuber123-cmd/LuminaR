import json
import pydantic

class V(pydantic.BaseModel):
    supported: bool
    event_match: bool
    polarity_match: bool
    temporal_match: bool
    reason: str

print(json.dumps(V.schema(), indent=2))
