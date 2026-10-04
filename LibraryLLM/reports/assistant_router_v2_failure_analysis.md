# Router V2 baseline failure analysis

49/116 baseline failures, each assigned exactly one primary category. Original evidence is unchanged.

- WRONG_GOAL: 7
- WRONG_INTENT: 9
- MISSED_CRITERION: 5
- WRONG_REFERENCE_POSITION: 9
- WRONG_SEARCH_EXTRACTION: 4
- WRONG_ACCOUNT_INTENT: 9
- UNNECESSARY_CLARIFICATION: 3
- EXPLICIT_ENTITY_FAILURE: 2
- PAGE_CONTEXT_FAILURE: 1

| Case | Context | Expected | Actual | Primary failure |
| --- | --- | --- | --- | --- |
| how do they stack up against each other | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| what's the tradeoff between them | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| how would you distinguish these | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| what does one offer that the other doesn't | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| can you contrast them | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| put the pair side by side | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| give me a rundown of their differences | selected | COMPARE_BOOKS | COMPARE_BOOKS | WRONG_GOAL |
| what differences do these books indicate | selected | COMPARE_BOOKS | CLARIFICATION | WRONG_INTENT |
| which one would be better for learning sports economics | selected | COMPARE_BOOKS | COMPARE_BOOKS | MISSED_CRITERION |
| I want to learn about soccer finance; which of these fits | selected | COMPARE_BOOKS | COMPARE_BOOKS | MISSED_CRITERION |
| which of these might help with my course on sports markets | selected | COMPARE_BOOKS | COMPARE_BOOKS | MISSED_CRITERION |
| I care about the economics of clubs rather than players; compare their fit | selected | COMPARE_BOOKS | COMPARE_BOOKS | MISSED_CRITERION |
| help me choose for a research project about sport | selected | COMPARE_BOOKS | COMPARE_BOOKS | MISSED_CRITERION |
| would either of these be available | selected | CHECK_AVAILABILITY | CLARIFICATION | WRONG_REFERENCE_POSITION |
| which one isn't unavailable | selected | CHECK_AVAILABILITY | CLARIFICATION | WRONG_REFERENCE_POSITION |
| can I get a copy of either today | selected | CHECK_AVAILABILITY | CLARIFICATION | WRONG_INTENT |
| which of these has a copy ready | selected | CHECK_AVAILABILITY | CLARIFICATION | WRONG_REFERENCE_POSITION |
| do I have to wait for either one | selected | CHECK_AVAILABILITY | COMPARE_BOOKS | WRONG_INTENT |
| what about the first one's subjects | selected | BOOK_DETAILS | COMPARE_BOOKS | WRONG_INTENT |
| what about the second one | selected | BOOK_DETAILS | CHECK_AVAILABILITY | WRONG_INTENT |
| not the first one, tell me about the other | selected | BOOK_DETAILS | CLARIFICATION | WRONG_INTENT |
| does the latter have a free copy | selected | CHECK_AVAILABILITY | CLARIFICATION | WRONG_REFERENCE_POSITION |
| what else is like the first one | selected | MORE_LIKE_THIS | CLARIFICATION | WRONG_REFERENCE_POSITION |
| can you find graph relatives of the former | selected | MORE_LIKE_THIS | CLARIFICATION | WRONG_REFERENCE_POSITION |
| show related titles for my last pick | selected | MORE_LIKE_THIS | CLARIFICATION | WRONG_REFERENCE_POSITION |
| find neighbours of the second book | selected | MORE_LIKE_THIS | CLARIFICATION | WRONG_INTENT |
| I liked these two, what else might fit | selected | RECOMMEND_FROM_SELECTION | CLARIFICATION | WRONG_INTENT |
| use my picks to suggest my next read | selected | RECOMMEND_FROM_SELECTION | COMPARE_BOOKS | WRONG_INTENT |
| help me find books about urban planning | none | SEARCH_BOOKS | CLARIFICATION | WRONG_SEARCH_EXTRACTION |
| I want to browse gothic fiction | none | SEARCH_BOOKS | CLARIFICATION | WRONG_SEARCH_EXTRACTION |
| look for beginner-friendly books on investing | none | SEARCH_BOOKS | CLARIFICATION | WRONG_SEARCH_EXTRACTION |
| show books about neural networks | none | SEARCH_BOOKS | CLARIFICATION | WRONG_SEARCH_EXTRACTION |
| how much do I owe | none | USER_FEES | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| is there an unpaid balance on my account | none | USER_FEES | USER_LOANS | WRONG_ACCOUNT_INTENT |
| do I have any fines outstanding | none | USER_FEES | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| what am I waiting to pick up | none | USER_RESERVATIONS | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| check my holds | none | USER_RESERVATIONS | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| what have I borrowed in the past | none | USER_HISTORY | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| show my earlier borrowing activity | none | USER_HISTORY | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| what have I saved to read later | none | USER_READING_LIST | CLARIFICATION | WRONG_ACCOUNT_INTENT |
| open my saved reading list | none | USER_READING_LIST | CLEAR_READING_LIST | WRONG_ACCOUNT_INTENT |
| and which one is available | comparison | CHECK_AVAILABILITY | CLARIFICATION | UNNECESSARY_CLARIFICATION |
| can either be borrowed right now | comparison | CHECK_AVAILABILITY | CLARIFICATION | UNNECESSARY_CLARIFICATION |
| what is their availability | comparison | CHECK_AVAILABILITY | CLARIFICATION | UNNECESSARY_CLARIFICATION |
| which one is the better choice | changed | COMPARE_BOOKS | CLARIFICATION | WRONG_REFERENCE_POSITION |
| what distinguishes my current pair | changed | COMPARE_BOOKS | CLARIFICATION | WRONG_REFERENCE_POSITION |
| tell me about Dune | selected | BOOK_DETAILS | CLARIFICATION | EXPLICIT_ENTITY_FAILURE |
| who wrote Dune | selected | BOOK_DETAILS | CLARIFICATION | EXPLICIT_ENTITY_FAILURE |
| is this book in stock | page | CHECK_AVAILABILITY | CLARIFICATION | PAGE_CONTEXT_FAILURE |

Complete decoded decisions, expected IDs/criteria/fields and executor results are in assistant_router_v2_failure_analysis.json.
