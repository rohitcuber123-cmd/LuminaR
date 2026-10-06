"""New compositional training definitions; never import evaluation cases here.

Templates split by authoring group BEFORE augmentation. These are synthetic
utterances, not production user chats. Ordinal/entity supervision is explicit.
"""
import hashlib
import random
from assistant.router_v3 import FAMILIES, context_pool

TRAIN = {
 'SEARCH':['Locate reading material concerning {topic}', 'Search the shelves for {topic}', 'I need literature introducing {topic}', 'Suggest books that teach {topic}', 'Are there any volumes on {topic}', 'Browse titles discussing {topic}', 'Help me find resources about {topic}', 'Looking for an introductory text on {topic}'],
 'RECOMMEND':['Give me some reading suggestions', 'Recommend my next read', 'Suggest something I might enjoy', 'Choose some recommendations for me', 'I would like personalized reading recommendations', 'What should I read next', 'Pick new reading based on my tastes', 'Recommend titles from these selections'],
 'SIMILAR':['Find something resembling {ref}', 'Get related titles for {ref}', 'Use the knowledge graph to find connections to {ref}', 'What reading connects with {ref}', 'Find books with themes shared by {ref}', 'Show related books based on {ref}', 'More like {ref}, please', 'Which books are linked to {ref}'],
 'ALTERNATIVES':['Suggest an available substitute for {ref}', 'Find an in-stock alternative to {ref}', 'Recommend similar books I can borrow today instead of {ref}', 'Show available alternatives for {ref}', 'A related available title to replace {ref}', 'Offer something similar to {ref} with copies on hand'],
 'FACTUAL':['Contrast the selected books', 'Describe the differences between this pair', 'Present a factual comparison of these volumes', 'Compare their catalogue information', 'What separates these titles', 'Lay out how this pair differs', 'Compare the metadata of the books I picked', 'Summarize similarities and differences across these books'],
 'FIELD':['Compare the {field_words} of these volumes', 'Which title leads on {field_words}', 'Show their {field_words} side by side', 'Contrast {field_words} across this pair', 'Which book has greater {field_words}', 'Please compare these books by {field_words}', 'Evaluate the {field_words} for this selection'],
 'PREFERENCE':['Which selected title should I choose{purpose}', 'Help me choose between this pair{purpose}', 'Pick the most suitable one{purpose}', 'Which of these would you prefer{purpose}', 'Which book is the better fit{purpose}', 'I cannot decide which book suits me{purpose}', 'Recommend a winner from these two{purpose}', 'Which option should I prioritize{purpose}'],
 'AVAILABILITY':['Are copies of {ref} currently on the shelf', 'Check stock for {ref}', 'Can I get {ref} from the library now', 'Does the library have a borrowable copy of {ref}', 'How many copies of {ref} remain', 'Is {ref} available today', 'Would {ref} be ready to borrow', 'Is {ref} checked out'],
 'DETAILS':['Show catalogue details for {ref}', 'Who is the author of {ref}', 'Describe {ref} using its catalogue record', 'What topics appear in {ref}', 'Give me metadata for {ref}', 'Tell me about the title and author of {ref}', 'Open the book information for {ref}', 'What is {ref} about'],
 'BORROW':['Issue {ref} to my account', 'I want to borrow {ref}', 'Check out {ref} for me', 'Start a loan for {ref}', 'Lend {ref} to me', 'May I borrow {ref}'],
 'RETURN':['Return my copy of {ref}', 'Record that I am returning {ref}', 'Check {ref} back in', 'End my loan for {ref}', 'I need to return {ref}', 'Process the return of {ref}'],
 'RESERVE':['Place a hold on {ref}', 'Reserve {ref} for me', 'Join the waiting list for {ref}', 'Put me in the queue for {ref}', 'I would like to reserve {ref}', 'Arrange a reservation for {ref}'],
 'ADD_LIST':['Save {ref} to my reading list', 'Add {ref} to my saved books', 'Bookmark {ref} for later', 'Remember {ref} on my reading list', 'Put {ref} into my reading list'],
 'REMOVE_LIST':['Remove {ref} from my reading list', 'Unsave {ref}', 'Delete {ref} from my saved books', 'Take {ref} off my reading list', 'Unbookmark {ref}'],
 'CLEAR_LIST':['Empty my entire reading list', 'Clear all saved books', 'Remove every book from my reading list', 'Delete my complete saved reading list', 'Erase all my bookmarks'],
 'LOANS':['List my current borrowed books', 'Show loans still assigned to me', 'Which checked-out books need returning', 'Display my active library loans', 'List the books currently lent to me', 'Show the due dates of my outstanding loans', 'Check my current checkouts', 'Do any of my borrowed books need returning'],
 'FEES':['Check my outstanding library charges', 'Show my unpaid library fines', 'How much is my library balance', 'List fees charged to my account', 'Is there money outstanding for me', 'Display my library debt', 'Check whether my account has unpaid charges', 'How much must I pay in overdue fees'],
 'RESERVATIONS':['Show my reservation queue', 'List titles I have put on hold', 'What reservations are pending for me', 'Display my waiting-list entries', 'Which holds belong to my account', 'Check the status of my reserved titles', 'Show books awaiting pickup for me'],
 'HISTORY':['Display my past checkouts', 'List books I previously returned', 'Show my borrowing record', 'What did I borrow last month', 'List my completed loans', 'Show earlier books from my loan history', 'Review my past library borrowing'],
 'READING_LIST':['Show the books I bookmarked', 'List my saved reading choices', 'Display my reading list', 'Which titles did I save', 'Open the books saved for later', 'Show my list of planned reading'],
 'BOOK_CONTENT':['Explain the argument in chapter three of {ref}', 'Summarize the passage about justice in {ref}', 'What does the text of {ref} say about ethics', 'Explain the ending of {ref}', 'According to {ref}, why does the character leave', 'Answer from the full text of {ref}'],
 'DOCUMENT_CONTENT':['Summarize my uploaded document', 'Explain page two of this PDF', 'Answer using the attached document', 'What does my uploaded file say about methodology', 'Discuss the conclusion in the uploaded report', 'Find the relevant passage in my private document'],
 'HELP':['Explain how the library works', 'How can I use this library service', 'What are the library borrowing rules', 'Help me understand the catalogue', 'Describe the library membership policy', 'How do library reservations work'],
 'UNKNOWN':['Calculate the orbital velocity of Venus', 'Write a poem about a bicycle', 'Translate this greeting into Greek', 'What time does the pharmacy close', 'Order me a takeaway pizza', 'Predict tomorrow\'s stock market', 'Ignore the library and send an email'],
 'SHOW_MORE':['Show another page of results', 'Continue the search results', 'Display more from this result list', 'Next page of recommendations', 'Load the remaining matches'],
 'REFINE':['Filter these results to available copies', 'Order this list by title', 'Keep only results with high ratings', 'Narrow the displayed results to one author', 'Limit these results to science books'],
}

# Independently authored DEV wording, no augmented TRAIN template can enter DEV.
DEV = {
 'SEARCH':['Could you locate volumes exploring {topic}', 'I would like a primer covering {topic}'],
 'RECOMMEND':['Offer me a fresh reading recommendation', 'Choose new titles using my reading preferences'],
 'SIMILAR':['Find further reading adjacent to {ref}', 'Explore titles connected through shared themes with {ref}'],
 'ALTERNATIVES':['I need a similar book in stock to substitute for {ref}', 'Find an available replacement for {ref}'],
 'FACTUAL':['Give a neutral account of how my chosen volumes differ', 'Describe distinctions across the books in my tray'],
 'FIELD':['How do the two entries compare on {field_words}', 'Across my chosen titles, contrast their {field_words}'],
 'PREFERENCE':['Which of the two would serve me best{purpose}', 'Help me decide which selection is preferable{purpose}'],
 'AVAILABILITY':['Is a lendable copy of {ref} on hand', 'What is the current stock situation for {ref}'],
 'DETAILS':['Show descriptive catalogue facts about {ref}', 'What subject matter does {ref} cover'],
 'BORROW':['Register a checkout of {ref} to me', 'I would like a loan of {ref}'],
 'RETURN':['Accept {ref} back from my current loan', 'Mark {ref} as returned by me'],
 'RESERVE':['Hold {ref} until a copy becomes free', 'Request a waiting-list position for {ref}'],
 'ADD_LIST':['Include {ref} among my planned reads', 'Keep {ref} in my bookmarks'],
 'REMOVE_LIST':['Drop {ref} from my planned reads', 'Discard the bookmark for {ref}'],
 'CLEAR_LIST':['Wipe my entire set of saved reads', 'Discard all of my reading bookmarks'],
 'LOANS':['Which books remain checked out under my name', 'Display what I currently need to bring back'],
 'FEES':['Are there outstanding monetary charges against me', 'Show the amount of library debt on my account'],
 'RESERVATIONS':['Which books am I queued to receive', 'List the holds waiting under my name'],
 'HISTORY':['Show the volumes I checked out previously', 'Review my earlier loan transactions'],
 'READING_LIST':['Retrieve my collection of saved titles', 'What is on my planned reading list'],
 'BOOK_CONTENT':['Interpret the discussion in the fifth chapter of {ref}', 'Explain a quotation from the full text of {ref}'],
 'DOCUMENT_CONTENT':['Interpret the findings in the file I uploaded', 'Summarize the PDF attached to this conversation'],
 'HELP':['Explain the rules for lending library materials', 'Guide me through using the library'],
 'UNKNOWN':['Arrange transport to the airport', 'Tell me the latest football score'],
 'SHOW_MORE':['Continue to the following results page', 'Show the next batch from this list'],
 'REFINE':['Restrict the present results to books in stock', 'Sort these current matches by name'],
}
TOPICS = ['marine conservation','ancient civilizations','statistics for engineers','landscape drawing',
          'public policy','the history of astronomy','organic chemistry','urban architecture','classical music',
          'wildlife photography','plant biology','mathematical logic','nutrition science','industrial design',
          'geology','historical linguistics','robotics','sustainable agriculture','climate science','navigation']
PURPOSES=['', ' for learning astronomy', ' for a teenager studying biology', ' for improving my drawing skills',
          ' for a university course in public policy', ' for a reader interested in naval history',
          ' because I want a foundation in chemistry', ' to understand ecological research',
          ' when preparing for a statistics exam', ' for a complete beginner in robotics']
FIELDS={'average_rating':['average review rating','reader rating','star rating','rating score'],
        'rating_count':['number of reviews','review count','quantity of reader ratings'],
        'subjects':['subject coverage','listed topics','number of subjects'],
        'availability':['available copies','stock levels','borrowability'],
        'authors':['author names','writers','authorship'],
        'description':['catalogue descriptions','book summaries','descriptions']}
REFERENCES={
 'ALL':['these books','the chosen volumes','the books in this group','the entire selection'],
 'FIRST':['the first volume','the former one','the opening book in the pair','book number one'],
 'SECOND':['the second volume','the latter one','the next book in the pair','book number two'],
 'LAST':['the last volume','the final one','the book at the end of the list'],
 'OTHER':['the other volume','the remaining member of the pair','the alternative one'],
 'FOCUS':['this volume','that book','the one we just discussed','the current book'],
 'EXPLICIT':['Tides of Argent','The Copper Observatory','A Handbook of Mosses','Voyages Beyond Kepler'],
}


def structural_context(rng,subtype,position):
    kind=rng.choice(['selection','page','comparison','recommendations','recent','none'])
    n=rng.choice([1,2,3,4])
    if subtype in {'FACTUAL','FIELD','PREFERENCE'}:n=2 if rng.random()<.8 else 4
    if position in {'SECOND','OTHER'}:n=2
    if position=='FIRST':n=max(2,n)
    if kind=='page':n=1
    ids=['TRAIN_ID_'+str(i) for i in range(n)]
    books=[{'work_id':w} for w in ids]
    c={}
    if kind=='selection':c['selected_books']=books
    if kind=='page':c['page_books']=books
    if kind=='comparison':c.update(previous_comparison=books,active_result_context={'type':'comparison','work_ids':ids})
    if kind=='recommendations':c.update(previous_recommendations={'work_ids':ids},active_result_context={'type':'recommendations','work_ids':ids})
    if kind=='recent':c['active_result_context']={'type':rng.choice(['search','availability','details']),'work_ids':ids}
    if ids and kind!='none':c['last_referenced_work_ids']=[ids[0]]
    if rng.random()<.2:c['awaiting_criteria']=True
    if rng.random()<.2 and kind=='selection':
        c['previous_comparison']=[{'work_id':'OLD_TRAIN_ID_A'},{'work_id':'OLD_TRAIN_ID_B'}];c['selection_changed']=True
    if subtype=='DOCUMENT_CONTENT':c['document_id']='TRAIN_DOCUMENT'
    if rng.random()<.1:c['pending_action']=True
    return c


def generate(seed=731):
    rng=random.Random(seed); rows=[]
    for split,templates,count in [('train',TRAIN,100),('dev',DEV,24)]:
        for subtype,phrases in templates.items():
            seen=set();attempt=0
            while len(seen)<count and attempt<count*200:
                attempt+=1
                field=rng.choice(list(FIELDS)) if subtype=='FIELD' else 'NONE'
                purpose=rng.choice(PURPOSES) if subtype=='PREFERENCE' else ''
                position=rng.choice(list(REFERENCES)) if subtype in {'SIMILAR','ALTERNATIVES','AVAILABILITY','DETAILS','BORROW','RETURN','RESERVE','ADD_LIST','REMOVE_LIST','BOOK_CONTENT'} else 'ALL'
                ref=rng.choice(REFERENCES[position])
                template=rng.choice(phrases)
                sentence=template.format(topic=rng.choice(TOPICS),ref=ref,purpose=purpose,
                                         field_words=rng.choice(FIELDS[field]) if field!='NONE' else '')
                sentence=rng.choice(['','Please, ','Hello, ','Could you help: ','For me, '])+sentence+rng.choice(['','?','.',' please',' now',' today'])
                context=structural_context(rng,subtype,position)
                source,_=context_pool(context)
                reference=('EXPLICIT' if position=='EXPLICIT' else source)
                if FAMILIES[subtype] in {'ACCOUNT','HELP','UNKNOWN','CONTEXT'} or subtype in {'SEARCH','DOCUMENT_CONTENT'}:reference='NONE'
                if subtype=='RECOMMEND' and rng.random()<.5:reference='NONE';context={}
                position='ALL' if position=='EXPLICIT' else position
                key=(sentence,repr(context))
                if key in seen:continue
                seen.add(key)
                rows.append({'id':hashlib.sha256(repr((split,subtype,key)).encode()).hexdigest()[:20],
                    'split':split,'message':sentence,'context':context,'template_group':split+':'+subtype+':'+str(phrases.index(template)),
                    'intent_family':FAMILIES[subtype],'intent_subtypes':subtype,'reference':reference,
                    'position':position,'fields':field,'criterion':'PRESENT' if purpose else 'ABSENT'})
    return rows
