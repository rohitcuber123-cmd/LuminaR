# Exhaustive saved-V5 cue audit

All **158** detector events were inspected source-first in the [cue inventory](rag_domain_qa_v6_v5_cue_inventory.md). Each has an exact source clause/sentence span, lexical trigger, candidate surface fields, and explicit no-match reason. No cue was missing, unparseable, or offset-mismatched. Replaying the detector conditions found all 158; none matched a concrete V4 extractor regex surface. This supports a broad-cue/narrow-pattern diagnosis, not a silent candidate-emission failure.

The V5 quote cue metric increments only after emission, so the 158-event count does not include failed V5 quote scans. That instrumentation issue did not cause the zero-emission result. All frozen V5 artifact hashes remain unchanged.
