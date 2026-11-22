"""Additional public-only probes against the already running RAG service."""
from pathlib import Path
import institution_v2q1_public_rag_probe as probe

probe.OUT=Path(__file__).resolve().parents[1]/'reports/institution_v2q1_public_rag_extended.json'
probe.queries=[
    ('RAG005','According to Dracula, who is Jonathan Harker?','Use only evidence from returned public sources.'),
    ('RAG006','What does the provided text say about smartphones?','Abstain if the retrieved text lacks evidence.'),
    ('RAG007','Which dinosaur species appears in Dracula?','Do not invent a claim without source evidence.'),
    ('RAG008','What is the publication page count of The Time Machine?','Do not infer page count without source evidence.'),
    ('RAG009','How did the Time Traveller describe his machine?','Ground any description in retrieved public text.'),
]
if __name__=='__main__':probe.main()
