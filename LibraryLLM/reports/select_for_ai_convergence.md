# Select for AI convergence

BookSelectButton and useAssistantStore remain one selection implementation. Global and linked local cards/detail/Home bind the same global_work_id, share saved/selected state and update the existing Ask LuminaR counter. Accepted selection limit and existing_qwen/router contracts remain.

Local-only records cannot be selected: the accepted Assistant validates OL work IDs and retrieves global metadata. library_book_id is not fabricated as a work identity. Detail explains this and supports saving. Assistant list summaries disclose local-only targets.

useAssistantPageContext includes linked global works only. Lending context derives from the current URL and current active GENERAL_USER membership, rather than stale remembered library. Explicit submitted context still passes backend guards. Matrix-generated global/library selection/counter tests and frozen selected-context/Assistant/authority suites pass. No Router research, training or model redesign ran. Browser counter walkthrough pending.
