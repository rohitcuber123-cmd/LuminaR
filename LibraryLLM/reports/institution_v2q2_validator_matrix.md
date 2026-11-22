# Exact validator comparison

DO_NOT_APPLY_CANDIDATE: expanded tests expose unsupported entity/field/value acceptances. Existing validator also has limitations. Protected approval absent.

|Case|Repeat|Question|Expected|Original|Candidate|
|---|---:|---|---|---|---|
|01_exact_present|1|What calibration code is recorded for Sensor Kestrel?|SUPPORTED|SUPPORTED|SUPPORTED|
|02_absent|1|What is Sensor Kestrel maximum operating temperature?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|03_other_entity|1|What calibration code is recorded for Sensor Kestrel?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|04_other_document|1|What calibration code does the Kestrel manual record?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|05_similar_field|1|What is Sensor Kestrel calibration code?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|06_wrong_value|1|Is Sensor Kestrel calibration code ALPHA-SEVEN?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|07_conflicting|1|What is Sensor Kestrel calibration code?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|
|08_negation|1|Is Sensor Kestrel calibration code BRAVO-NINE?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|09_false_premise|1|Why did Sensor Kestrel change its calibration code to ALPHA-SEVEN?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|10_no_evidence|1|What calibration code is recorded for Sensor Kestrel?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|11_ambiguous_entity|1|What is the sensor calibration code?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|
|12_ambiguous_field|1|What is Sensor Kestrel service code?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|13_numeric_mismatch|1|Do Sensor Kestrel routine checks take 12 minutes?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|14_date_mismatch|1|Was Sensor Kestrel calibrated on 2026-10-01?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|15_inferred_relationship|1|Did Sensor Kestrel cause Sensor Heron to fail?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|16_source_injection|1|What is Sensor Kestrel calibration code?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|
|17_unrelated_word|1|What is Sensor Kestrel calibration code?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|18_mixed_provenance|1|What is Sensor Kestrel calibration code?|SUPPORTED|SUPPORTED|SUPPORTED|
|19_foreign_library|1|What is Sensor Kestrel calibration code in Private A?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|20_inaccessible_document|1|What calibration code may the current user read for Sensor Kestrel?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|
|21_unknown_request|1|What is Sensor Kestrel serial number?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|22_false_assertion|1|Explain why Sensor Kestrel code is ALPHA-SEVEN.|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|23_definition|1|What does calibration code mean?|SUPPORTED|SUPPORTED|SUPPORTED|
|24_multiple_conditions|1|Was Sensor Kestrel calibrated before inspection and approved by Mira?|NOT_SUPPORTED|NOT_SUPPORTED|NOT_SUPPORTED|
|25_chronology|1|Did Sensor Kestrel inspection occur before calibration?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|
|01_exact_present|2|What calibration code is recorded for Sensor Kestrel?|SUPPORTED|SUPPORTED|SUPPORTED|
|07_conflicting|2|What is Sensor Kestrel calibration code?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|
|09_false_premise|2|Why did Sensor Kestrel change its calibration code to ALPHA-SEVEN?|NOT_SUPPORTED|NOT_SUPPORTED|SUPPORTED|
|16_source_injection|2|What is Sensor Kestrel calibration code?|NOT_SUPPORTED|SUPPORTED|SUPPORTED|

Authored strict claim-grounding expectations. Yes/no and contradictory-record questions can admit a corrective answer under other answerability policies; rows retain exact questions/evidence. Wrong entity/field/absent-value failures are decisive independent of that ambiguity.

Evidence, entity/field oracles, provenance, structured intent, raw model JSON and timings for all58runs: institution_v2q2_validator_matrix.json. No failed run discarded.