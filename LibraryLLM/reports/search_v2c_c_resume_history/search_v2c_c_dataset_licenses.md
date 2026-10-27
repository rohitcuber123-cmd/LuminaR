# V2C-C dataset access and license audit

Audit date: 2026-10-15. No external dataset files or query records were downloaded or copied into this benchmark or production. Public documentation informs query-shape categories only. LuminaR plan labels are newly authored; web relevance/wellformedness labels are not plan gold.

| Source | Primary source / observed terms | Decision |
|---|---|---|
| MS MARCO | [Official datasets and terms](https://microsoft.github.io/msmarco/): intended for non-commercial research; underlying document rights not guaranteed | No records used or downloaded; query-fragment shape inspiration only |
| ORCAS | [Official paper](https://arxiv.org/abs/2006.05324), [MS MARCO data documentation](https://microsoft.github.io/msmarco/Datasets) | Click/relevance labels do not fit typed library plans; no records used; no redistribution permission assumed |
| Query Wellformedness | [Official repository](https://github.com/google-research-datasets/query-wellformedness): CC BY-SA4.0, third-party content as-is | Read description only; no queries copied; no derived record distribution |
| Natural Questions | [Official repository/license](https://github.com/google-research-datasets/natural-questions/blob/master/LICENSE) | QA annotations do not fit plan labels; no records used or downloaded; no blanket permission inferred for Wikipedia content |
| Open Library | [Official licensing statement](https://openlibrary.org/developers/licensing): Internet Archive asserts no new copyright, existing rights may remain | Existing local authoritative catalogue used read-only for scope vocabularies; no new dump downloaded; not claimed universally CC0 |
| Goodreads/UCSD Book Graph | [Official dataset page](https://sites.google.com/eng.ucsd.edu/ucsdbookgraph): academic use only | Excluded; no download, redistribution, or production ingestion |
| Google MQR | Mentioned as potential inspiration; exact dataset identity/license not cleared | Excluded; no download or reuse |
| MIMICS | No reuse license cleared in this task | Excluded; no download or reuse |
| QUEST | Exact dataset/version/license not cleared in this task | Excluded; no download or reuse |
| Amazon ESCI | No reuse license cleared in this task | Excluded; no download or reuse |

These are recorded engineering reuse decisions, not a claim that public access grants an unrestricted license. No external source supplied LuminaR expected values.
