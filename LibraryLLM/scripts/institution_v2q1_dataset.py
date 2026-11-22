"""Build a reproducible, unjudged discovery query inventory; no service calls."""
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]
subjects = ['Python programming','database systems','operating systems','computer networking',
    'machine learning','statistics','distributed systems','algorithms','research methodology',
    'space exploration','cybersecurity','ecology','world history','mystery fiction',
    'science fiction','computer graphics']
templates = [
    ('subject','Find books about {subject}.'),
    ('beginner','Books for learning {subject} from scratch.'),
    ('introductory','Recommend an introduction to {subject}.'),
    ('practical','I want a practical guide to {subject} with examples.'),
    ('advanced','Find an advanced book on {subject}.'),
    ('vague','I am curious about {subject}; where should I start?'),
    ('limited_prerequisites','Explain {subject} without assuming advanced prerequisites.'),
    ('availability','Which books about {subject} are available?'),
]
extra = [
    ('exact_title','Find TEST Campus Network Practice Workbook.','SEARCH_BOOKS','LIBRARY'),
    ('exact_title','Do you have Dune?','SEARCH_BOOKS','GLOBAL'),
    ('partial_title','Find books titled Operating Systems.','SEARCH_BOOKS','GLOBAL'),
    ('author','Find books by Bram Stoker.','SEARCH_BOOKS','GLOBAL'),
    ('author','Show books written by Ursula Le Guin.','SEARCH_BOOKS','GLOBAL'),
    ('similar','Books like Dune.','RECOMMEND_FROM_BOOK','GLOBAL'),
    ('similar','Books similar to Harry Potter.','RECOMMEND_FROM_BOOK','GLOBAL'),
    ('multi_constraint','Short mystery books with suspense.','SEARCH_BOOKS','GLOBAL'),
    ('format','Find an online book about networking.','SEARCH_BOOKS','LIBRARY'),
    ('no_match','Find a book about quazzleflorp thermodynamic aardvarks.','SEARCH_BOOKS','LIBRARY'),
    ('recommendation','Pick a book from this library for someone interested in AI.','RECOMMEND_BOOKS','LIBRARY'),
    ('recommendation','Recommend something this library owns, not from the global catalogue.','RECOMMEND_BOOKS','LIBRARY'),
    ('follow_up','Which one is shortest?','FOLLOW_UP','INHERIT'),
    ('follow_up','Which of those books is available?','CHECK_AVAILABILITY','INHERIT'),
    ('follow_up','Tell me more about the second book.','BOOK_DETAILS','INHERIT'),
    ('follow_up','Compare the first two recommendations.','COMPARE_BOOKS','INHERIT'),
    ('follow_up','Is the second one available?','CHECK_AVAILABILITY','INHERIT'),
    ('ambiguous','Find me something good.','AMBIGUOUS','INHERIT'),
    ('ambiguous','Which is best if I know only basic Java?','AMBIGUOUS','INHERIT'),
    ('document','Explain chapter three.','DOCUMENT_OR_CLARIFY','INHERIT'),
    ('document','Summarize this book without an accessible document.','ABSTAIN_OR_METADATA','INHERIT'),
    ('typo','Find books about datbase systms.','SEARCH_BOOKS','GLOBAL'),
    ('typo','Beginer pythn books.','SEARCH_BOOKS','GLOBAL'),
    ('synonym','Books about network security for newcomers.','SEARCH_BOOKS','GLOBAL'),
    ('synonym','Introductions to artificial intelligence for new learners.','SEARCH_BOOKS','GLOBAL'),
    ('tenant_conflict','Show only books owned by this library.','SEARCH_BOOKS','LIBRARY'),
    ('tenant_conflict','Is a book from another library available here?','CHECK_AVAILABILITY','LIBRARY'),
    ('similar','Something like this but shorter.','RECOMMEND_SIMILAR','INHERIT'),
    ('similar','More books on the same subject but less advanced.','RECOMMEND_SIMILAR','INHERIT'),
    ('multi_constraint','Science-fiction books available in this library.','SEARCH_BOOKS','LIBRARY'),
    ('multi_constraint','Beginner-friendly database textbooks with examples.','SEARCH_BOOKS','GLOBAL'),
    ('recommendation','Give me a practical introduction to operating systems.','RECOMMEND_BOOKS','GLOBAL'),
]

def main():
    rows=[]
    for subject in subjects:
        for category, template in templates:
            rows.append({'query':template.format(subject=subject),'category':category,'context':'GLOBAL',
                'expected_intent':'SEARCH_BOOKS','expected_relevant_categories':[subject],
                'constraints':[category] if category not in {'subject','vague'} else [],
                'expected_ids':None,'relevance_labels':'UNJUDGED','requires_subjective_review':True})
    for category,query,intent,context in extra:
        rows.append({'query':query,'category':category,'context':context,'expected_intent':intent,
            'expected_relevant_categories':[],'constraints':[],'expected_ids':None,
            'relevance_labels':'UNJUDGED','requires_subjective_review':True,
            'expected_follow_up_binding':'prior current-context results' if context=='INHERIT' else None})
    for i,row in enumerate(rows,1):
        row['id']=f'Q{i:03}'
        row['supported_metadata']='UNVERIFIED: check the catalogue snapshot before judging constraints'
        row['expected_unavailable_behavior']='Report insufficient evidence or no local match; do not invent availability.'
        row['reference_book_id']=None
        row['annotation_confidence']='PROVISIONAL'
    result={'version':'2q1-inventory-v1','created_at':datetime.now(timezone.utc).isoformat(),
        'judgment_provenance':'Query author annotations only; no independent judgments or complete relevance sets. No precision or recall scores are implied.',
        'execution':'Inventory only. Rows do not imply execution. Created after initial exploratory live probes; not a held-out set.', 'queries':rows}
    target=ROOT/'reports/institution_v2q1_query_inventory.json'
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    print('Queries:',len(rows))

if __name__=='__main__':main()
