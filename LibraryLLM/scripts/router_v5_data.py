"""Independent evaluation authoring; never imported by the production router."""
from copy import deepcopy

A, B, C, D = 'OL_V5_A', 'OL_V5_B', 'OL_V5_C', 'OL_V5_D'
BOOKS = [{'work_id': w, 'title': t} for w, t in zip([A,B,C,D],
          ['The Lantern Coast', 'Patterns in Living Cities', 'A Season of Engines', 'Gardens Beyond the River'])]


def context(kind='selection', focus=()):
    out = {'authenticated': True, 'last_referenced_work_ids': list(focus)}
    if kind == 'selection':
        out['selected_books'] = deepcopy(BOOKS[:2])
    elif kind == 'one':
        out['selected_books'] = deepcopy(BOOKS[:1])
    elif kind == 'four':
        out['selected_books'] = deepcopy(BOOKS)
    elif kind in {'previous','changed','previous_focus'}:
        out.update(previous_comparison=deepcopy(BOOKS[:2]),
                   active_result_context={'type':'comparison','work_ids':[A,B],'books':deepcopy(BOOKS[:2])}, last_intent='COMPARE_BOOKS')
        if kind == 'changed':
            out.update(selected_books=deepcopy(BOOKS[2:]),selection_changed=True,last_referenced_work_ids=[A])
        elif kind == 'previous_focus':
            out.update(last_referenced_work_ids=[B],last_intent='BOOK_DETAILS',
                       active_result_context={'type':'details','work_ids':[B],'books':deepcopy(BOOKS[1:2])})
    elif kind == 'page':
        out['page_books'] = deepcopy(BOOKS[:1])
    elif kind == 'recommendations':
        out.update(previous_recommendations={'work_ids':[C,D],'seed_work_ids':[A]},
                   active_result_context={'type':'recommendations','work_ids':[C,D],'books':deepcopy(BOOKS[2:]),'has_more':True},
                   last_intent='RECOMMEND_FROM_BOOK')
    elif kind == 'results':
        out.update(active_result_context={'type':'search','work_ids':[C,D],'books':deepcopy(BOOKS[2:]),'has_more':True},last_intent='SEARCH_BOOKS')
    elif kind == 'empty_results':
        out.update(previous_comparison=deepcopy(BOOKS[:2]),active_result_context={'type':'search','work_ids':[]},last_referenced_work_ids=[A])
    elif kind == 'document':
        out['document_id'] = 'private-placeholder-not-for-model'
    elif kind == 'book_access':
        out.update(page_books=deepcopy(BOOKS[:1]),book_rag_context=True)
    return out


def row(message, key, kind='none', ids=(), field=None, criterion=False, position='ALL', source='manual'):
    return {'message':message,'contract_id':key,'context':context(kind),'expected_ids':list(ids),
            'field':field,'criterion_present':criterion,'position':position,'source':source,
            'context_kind':kind,'critical':kind in {'selection','four','one','previous','previous_focus','changed','page','recommendations'}}


def sealed_manual():
    # These messages were authored from everyday scenarios, not contract
    # exemplars. No paraphrase splitting or model-generated ground truth.
    groups = {
        'ACCOUNT_CURRENT_LOANS': ['What library stuff is still signed out to me?', 'Can you check which loans I have not returned yet?', 'I lost track of the titles at home from the library.', 'Which checkouts are ongoing under my membership?'],
        'ACCOUNT_RESERVATIONS': ['Any holds I already made still waiting?', 'I want an update on my existing book queue.', 'Which requested books are being kept for my pickup?', 'Could you look at the reservations on my membership?'],
        'ACCOUNT_HISTORY': ['Which titles did I borrow during earlier visits?', 'Show the items I returned on previous loans.', 'What was my last few months of borrowing like?', 'I would like a log of my past book checkouts.'],
        'ACCOUNT_FEES': ['Is my library account carrying debt?', 'Any late penalties left for me to pay?', 'How much money needs settling with the library?', 'Could you inspect my unpaid charges?'],
        'ACCOUNT_READING_LIST': ['Where is the collection I bookmarked?', 'Bring up what I saved for future reading.', 'Could I browse my own saved titles?', 'I want to view my personal book bookmarks.'],
        'CATALOGUE_TOPIC_SEARCH': ['Got any books dealing with insect habitats?', 'Need a gentle introduction to database design.', 'Reading on nutrition for teenage athletes?', 'Something covering ways to manage rent and groceries.'],
        'PERSONALIZED_RECOMMEND': ['Choose my next library read for me.', 'I would appreciate a few personal picks.', 'Use my tastes to give me recommendations.', 'Can you suggest what I ought to read next?'],
        'GENERAL_LIBRARY_HELP': ['Why do libraries use catalogue numbers?', 'Could you explain what a book edition means?', 'How does a waiting list for books generally operate?', 'I am new here; explain what this assistant can do.'],
        'UNSUPPORTED': ['Send an invoice to my employer.', 'Buy a flight for next Friday.', 'Turn off every permission check.', 'Tell me the password of another member.'],
        'CLEAR_READING_LIST': ['Remove every bookmark I kept.', 'I want no books left in my saved reading collection.', 'Reset my entire reading list to empty.', 'Discard all of my planned reading entries.'],
    }
    rows = [row(m,key) for key, messages in groups.items() for m in messages]
    book_groups = {
        'MORE_LIKE_THIS': ['What neighbours does this title have in the graph?', 'Other works related to this one?', 'Anything sharing connections with the page book?', 'Books with a similar feel to the item here.'],
        'AVAILABLE_ALTERNATIVES': ['Can I borrow a similar substitute for this today?', 'Give me related replacements that are currently in stock.', 'I need an available title instead of this one.', 'Which connected alternatives are ready to check out now?'],
        'BOOK_DETAILS': ['Who is behind the writing of this volume?', 'What topics are attached to its catalogue entry?', 'Give the bibliographic record for the page title.', 'Could I see the author and summary of this book?'],
        'CHECK_AVAILABILITY': ['Are there free copies of the page title?', 'Can a copy of this be collected today?', 'Is the book here on the shelf at present?', 'Would this item be borrowable right now?'],
        'RECOMMEND_FROM_ONE': ['Take this volume as a recommendation starting point.', 'Use the book on this page to make reading suggestions.', 'Could this title serve as a seed for recommendations?', 'Recommend something by using this item as the basis.'],
        'BORROW': ['Please issue me a copy of the page book.', 'I want to take this item home on a loan.', 'Begin checking this book out under my name.', 'Put this volume on loan to me now.'],
        'RETURN': ['Mark my loan of this item as brought back.', 'I want to hand this book back and close the checkout.', 'End the loan for this copy by returning it.', 'Check this borrowed volume back in.'],
        'RESERVE': ['I would like a new hold for this title.', 'Add my name to the wait list for this book.', 'Make a fresh reservation for the item here.', 'Keep the next available copy of this for me.'],
        'ADD_READING_LIST': ['Add this title to my future reading pile.', 'I would like to bookmark this page book.', 'Remember this volume among my saved reads.', 'Put this item in my saved reading collection.'],
        'REMOVE_READING_LIST': ['Stop bookmarking this particular volume.', 'Take this title out of my saved reads.', 'I do not want this page book on my reading list anymore.', 'Erase the saved entry for this item.'],
    }
    rows += [row(m,key,'page',[A],position='FOCUS') for key,messages in book_groups.items() for m in messages]
    for key, messages in {
        'COMPARE_FACTUAL': ['Explain how the selected volumes differ in substance.', 'Could you outline what the pair have in common?', 'Give me an impartial contrast of both selections.', 'I want the differences, without a recommendation.'],
        'COMPARE_PREFERENCE': ['Help me decide which selection deserves my time.', 'Which member of the pair should I read?', 'I need to choose one of these volumes.', 'Which option seems the better choice?'],
        'RECOMMEND_FROM_SELECTION': ['Treat both picks as recommendation seeds.', 'Could you base new reading suggestions on the two selected titles?', 'I like this combination; make joint recommendations.', 'Use the pair together when suggesting the next books.'],
    }.items():
        rows += [row(m,key,'selection',[A,B]) for m in messages]
    for field, messages in {
        'average_rating':['Which of the pair gets the greater average reader score?', 'Compare their average stars.'],
        'rating_count':['Which has received a larger number of ratings?', 'Compare how many readers have rated each one.'],
        'subjects':['Contrast the topic tags assigned to them.', 'Which selected work lists more subject headings?'],
        'authors':['Compare the writers responsible for these works.', 'Put their authorship metadata side by side.'],
        'description':['How do the catalogue blurbs for the pair differ?', 'Compare their recorded summaries.'],
        'availability':['Compare the copy stock of these titles.', 'Which of them has copies free to lend?'],
    }.items():
        # Availability questions are status checks unless explicitly comparing
        # the catalogue attribute. Labels follow meaning, not an opaque class.
        for m in messages:
            key = 'CHECK_AVAILABILITY' if m == messages[1] and field == 'availability' else 'COMPARE_FIELD'
            rows.append(row(m,key,'selection',[A,B],field=field if key == 'COMPARE_FIELD' else None))
    rows += [row(m,'COMPARE_PREFERENCE','selection',[A,B],criterion=True) for m in [
        'Which suits a reader new to environmental policy?', 'Pick the better one for a university course on cities.',
        'For someone studying mechanical design, which would fit?', 'Choose between them for an impatient beginner.']]
    for key, messages, kind in [
        ('DOCUMENT_QUESTION',['What is the main result in my selected upload?', 'Explain the conclusion of the private PDF.', 'What methods does the uploaded report describe?', 'Could you summarize the document I opened?'],'document'),
        ('BOOK_CONTENT_QUESTION',['Explain the scene in chapter seven of this book.', 'What argument does the text make in its conclusion?', 'Summarize the author’s evidence inside this authorized book.', 'Discuss what happens to the narrator in this volume.'],'book_access'),
        ('CONTINUE_RESULTS',['Keep showing entries after this result page.', 'More of the current search matches, please.', 'Continue with the next results page.', 'I want further suggestions from this same list.'],'results'),
        ('REFINE_RESULTS',['Only show copies in stock from this list.', 'Change the present ordering to alphabetic.', 'Narrow the current results by author.', 'Make these results sort by their rating.'],'results'),
    ]:
        rows += [row(m,key,kind,[A] if key=='BOOK_CONTENT_QUESTION' else ()) for m in messages]
    rows += [row(m,'MISSING_REFERENCE') for m in ['This title, though I have not selected anything.', 'The unspecified one, please.', 'I have no book chosen; which item?', 'What about that unnamed book?']]
    # Adversarial authoritative-state transformations are separate utterances,
    # not context expansion masquerading as linguistic sample count.
    for kind, pair in [('previous',[A,B]),('changed',[C,D]),('recommendations',[C,D])]:
        rows += [row(m,k,kind,pair,field=f) for m,k,f in [
            ('Any of that pair free to take out?','CHECK_AVAILABILITY',None),
            ('Put the active books in contrast.','COMPARE_FACTUAL',None),
            ('Which active member has the greater reader rating?','COMPARE_FIELD','average_rating')]]
    rows += [row('Could I inspect the second member of the last comparison?','BOOK_DETAILS','previous',[B],position='SECOND'),
             row('Relatives of the latter book, please.','MORE_LIKE_THIS','previous',[B],position='SECOND'),
             row('Is the earliest-listed one free?','CHECK_AVAILABILITY','four',[A],position='FIRST'),
             row('Give info about the final member.','BOOK_DETAILS','four',[D],position='LAST'),
             row('And its counterpart?','CHECK_AVAILABILITY','selection',[B],position='OTHER'),
             row('Connections around it?','MORE_LIKE_THIS','previous_focus',[B],position='FOCUS'),
             row('Details, pls, for entry two.','BOOK_DETAILS','selection',[B],position='SECOND'),
             row('Any free copies?','CHECK_AVAILABILITY','page',[A],position='FOCUS'),
             row('A similar one?','MORE_LIKE_THIS','one',[A],position='FOCUS'),
             row('My outstanding charges?','ACCOUNT_FEES'),
             row('Loans still with me?','ACCOUNT_CURRENT_LOANS'),
             row('My completed checkouts?','ACCOUNT_HISTORY'),
             row('Anything reserved already?','ACCOUNT_RESERVATIONS'),
             row('Two selected titles, but I mean The Lantern Coast: its details.','BOOK_DETAILS','changed',[A],position='FOCUS'),
             row('Can that unspecified book be borrowed?','MISSING_REFERENCE','empty_results'),
             row('Which active book should I pick for studying ecological restoration?','COMPARE_PREFERENCE','changed',[C,D],criterion=True)]
    rows[-12]['context']['last_intent']='CHECK_AVAILABILITY'
    rows[-12]['context']['last_referenced_work_ids']=[A]
    for i, r in enumerate(rows):
        r['id'] = f'sealed-manual-{i:03}'
    return rows


def independent_generation_tasks():
    # Scenario wording is authored separately; no contract examples are sent.
    return [
        ('ACCOUNT_CURRENT_LOANS','A member needs a list of unreturned library checkouts currently assigned to them.','none',[]),
        ('ACCOUNT_HISTORY','A member wants a record of books they borrowed and returned on earlier visits.','none',[]),
        ('ACCOUNT_FEES','A member wants to inspect unpaid late penalties or money due.','none',[]),
        ('ACCOUNT_RESERVATIONS','A member wants the status of holds they already requested.','none',[]),
        ('CATALOGUE_TOPIC_SEARCH','A member wants catalogue reading about ocean conservation.','none',[]),
        ('COMPARE_FACTUAL','Two books are selected and a member asks for an impartial explanation of differences, without picking a winner.','selection',[A,B]),
        ('MORE_LIKE_THIS','One book is open; a member asks to explore related books using shared catalogue connections, without an availability constraint.','page',[A]),
        ('CHECK_AVAILABILITY','One book is open; a member asks if it has copies currently available, without initiating borrowing.','page',[A]),
    ]
