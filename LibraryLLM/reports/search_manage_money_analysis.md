# Manage-money review and broader-results decision

Actual resident GPU Search against the Mongo catalogue, semantic generation30. No fabricated books. The complete ordered rank1–50 dump (work_id/title/authors/subjects/CE/HNSW scores) is in search_manage_money_ranking.json. Eight-query metrics and before/after IDs are in search_depth_regression.json and the baseline/after result files.

Top10 prioritizes close title/subject matches about managing money. Lower results expose practical alternatives: rank13 Managing Your Money All-In-One for Dummies (budget, debt, investing, retirement in its catalogue description); rank20 The art of managing money (Personal Budgets); rank22 The complete idiot's guide to managing your money (consumer credit, investing, retirement metadata); rank24 Manage Your Student Finances Now!; rank35 Financial management: theory and practice (budgeting); rank40 Handbook of financial planning; rank46 Be Smart About Money (financial literacy); rank48 Budgeting101; rank50 Living on a budget. Catalogue metadata supports these topic observations; detailed content/relevance labels were not evaluated.

Pagination is sufficient for the observed narrow initial display: broader choices already exist in ranks11–50. This does not prove optimal retrieval or universal coverage. Keep default CE ranking and do not implement Broad/MMR mode or a broad-mode flag in this pass.

Metrics compare distinct pipe-separated casefolded author/subject labels, mean pairwise subject Jaccard distance, and title word-token repetition (includes stopwords). These are diagnostic metadata proxies, not relevance judgments. No semantic book embeddings were recomputed.

| Query | Authors10/50 | Subjects10/50 | Subject distance10/50 | Title repetition10/50 |
|---|---:|---:|---:|---:|
| manage money for finances | 14/54 | 28/68 | 0.8374/0.7857 | 0.5902/0.6439 |
| beginner artificial intelligence | 10/53 | 35/91 | 0.9044/0.8881 | 0.4634/0.6148 |
| gothic horror | 10/45 | 22/92 | 0.7272/0.8804 | 0.4359/0.6354 |
| database systems | 12/62 | 22/61 | 0.6172/0.754 | 0.5102/0.6927 |
| time travel science fiction | 14/61 | 25/77 | 0.8009/0.8459 | 0.4681/0.5953 |
| machine learning | 14/74 | 15/56 | 0.7973/0.7417 | 0.434/0.6802 |
| personal finance | 9/44 | 5/23 | 0.4578/0.53 | 0.6176/0.665 |
| investing for beginners | 9/46 | 7/45 | 0.8481/0.8365 | 0.7778/0.6215 |

All eight Top10 sequences are identical. Finance Top50 is identical. AI ranks31/32 and33/34 swap within equal CE-score pairs due explicit deterministic secondary ordering; Top10 remains identical. All index/model paths and recommendation weights are unchanged.

| Rank | Title | Authors | CE score |
|---:|---|---|---:|
| 1 | The Complete Guide to Managing Your Money: Your Finances in Changing Times : Using Your Money Wisely | Larry Burkett | 6.085206 |
| 2 | Managing Your Finances (Allied Dunbar Money Guides) | Helen Pridham | 5.550888 |
| 3 | Manage Your Money Manager | Jorge Castro | 5.007253 |
| 4 | Managing your money with managing your money | Jim Bartimo | 4.945917 |
| 5 | Managing money and finance | Geoffrey P. E. Clarkson | 4.914565 |
| 6 | 52 simple ways to manage your money | Judith A. Martindale  /  Mary J. Moses  /  Judy Martindale | 4.843843 |
| 7 | Managing your money | J. K. Lasser  /  Sylvia F. Porter | 4.785708 |
| 8 | Managing money | Nan Bostick | 3.606369 |
| 9 | How to manage your money | John Kirk | 3.472623 |
| 10 | Complete guide to managing your money | Jeff Blyskal  /  Janet Bamford | 3.458815 |
| 11 | Money Management for Young Adults | Luke Villermin | 3.282221 |
| 12 | How to Manage Your Money | Larry Burkett | 3.149650 |
| 13 | Managing Your Money All-In-One For Dummies® | Consumer Dummies | 3.099646 |
| 14 | Managing money | Barbara Gottfried Hollander | 2.933413 |
| 15 | Managing Your Personal Finances 7th Edition | Joan S. Ryan | 2.897394 |
| 16 | How you can manage your money | John Warren Johnson | 2.883173 |
| 17 | Managing your personal finances | Joan S. Ryan | 2.725436 |
| 18 | Money management for those who don't have any | James L. Paris | 2.703995 |
| 19 | Managing Your Personal Finances | Joan S. Ryan | 2.638226 |
| 20 | The art of managing money | Lois Restemayer | 2.545714 |
| 21 | How to manage your money | Faye Henle | 2.511949 |
| 22 | The complete idiot's guide to managing your money | Robert Heady | 2.361653 |
| 23 | Managing your money | Indigo Canada | 2.346334 |
| 24 | Manage Your Student Finances Now! | Keith Houghton | 2.344446 |
| 25 | Money management for women with no money | Patricia J. Plute | 2.315656 |
| 26 | How to manage your money when you don't have any | Erik Wecks | 2.199365 |
| 27 | Managing your money | Elizabeth James | 1.553195 |
| 28 | Managing money | Linda Crotta Brennan | 1.528427 |
| 29 | Kids manage money | Ellen Keller | 1.487514 |
| 30 | Cash Savings And All That Stuff A Guide To Money And How To Manage It | Kira Vermond | 1.086568 |
| 31 | Money Management | Evelyn Fernandez | -0.118409 |
| 32 | Money management | Marcella E. Finegan | -0.656254 |
| 33 | J. K. Lasser's managing your family finances | J.K. Lasser Institute | -0.709126 |
| 34 | Guru Guide to Money Management | Joseph H. Boyett  /  Jimmie T. Boyett | -1.434494 |
| 35 | Financial management : theory and practice | Eugene F. Brigham  /  Michael C. Ehrhardt | -2.090308 |
| 36 | Money management | Household Finance Corporation. | -2.509367 |
| 37 | Moneywise guide to planning your finances | Caroline Laws  /  Isabel Berwick | -2.783933 |
| 38 | A measurement and interpretation of money management understandings of twelfth-grade students | Herbert Mahlon Jelley | -2.839087 |
| 39 | Working From Home: Managing Your Time, Money & and Stuff | Paul and Sarah Edwards | -5.422473 |
| 40 | Handbook of Financial Planning | Jae K. Shim | -6.548901 |
| 41 | Money is Everything | Amanda Reaume | -7.296461 |
| 42 | Money smarts | Peggy Santamaria | -8.164156 |
| 43 | The MsSpent Money Guide | Deborah Knuckey | -9.178972 |
| 44 | The Money Therapist | Marcia Brixey | -9.404976 |
| 45 | All about your money | Dan Fitzgibbon | -9.871766 |
| 46 | Be smart about money | Sherri Mabry Gordon | -9.876707 |
| 47 | Your money | Gerry Bailey | -10.537923 |
| 48 | Budgeting 101 | Michele Cagan | -10.701811 |
| 49 | QuickStudy - Personal Finance | Steven M Berner | -10.826970 |
| 50 | Living on a budget | Cecilia Minden | -11.075031 |

Additional regression evidence: original top_k=10 requests were replayed for all eight queries using the saved original engine source against the unchanged catalogue/index; all eight return exactly the same Top10 IDs in the same order (search_depth_original_top10_replay.json).
