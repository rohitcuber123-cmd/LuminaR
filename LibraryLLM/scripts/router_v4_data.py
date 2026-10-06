"""Offline semantic seeds. Split families before generation; never runtime rules."""
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from assistant.router_v3 import FAMILIES, context_pool

# Four TRAIN, two DEV and two independently authored INTERNAL seeds per type.
# Templates are semantic seed families, not production phrase matchers.
SEEDS = {
 'SEARCH': ['A reading guide to {topic} would help me', 'Can the catalogue supply an introduction to {topic}', 'Find reading on {topic} suitable for novices', 'I am looking into {topic} and need books', 'Any literature dealing with {topic}', 'Point me toward an accessible treatment of {topic}', 'A book covering {topic} is what I am after', 'Help locate a volume that explains {topic}'],
 'RECOMMEND':['Choose my next book', 'Give me reading ideas based on my picks', 'Recommend a few titles to explore next', 'Suggest reading using these as starting points', 'What would you put on my next reading pile', 'I want fresh suggestions from my selection', 'Pick out books I may enjoy', 'Use my choices to recommend another read'],
 'SIMILAR':['Track down a book with a connection to {ref}', 'Use {ref} as the starting point for related reading', 'I enjoyed {ref}; what shares its themes', 'Find a neighbour of {ref} in the book graph', 'Can you connect {ref} to other titles', 'I would like another book in the vein of {ref}', 'What reading branches out from {ref}', 'Look for material resembling {ref}'],
 'ALTERNATIVES':['An available replacement for {ref} please', 'Find a similar title to {ref} that is on the shelf', 'I cannot get {ref}; give me something comparable in stock', 'A borrowable substitute for {ref} would be useful', 'What can I borrow instead of {ref} with similar themes', 'Find an alternative to {ref} available right now', 'Offer a currently stocked stand-in for {ref}', 'Locate a related title with copies available instead of {ref}'],
 'FACTUAL':['Set out the contrasts between this group of books', 'I want a neutral side-by-side account of these titles', 'Describe what distinguishes the books under discussion', 'Compare the catalogue facts across these volumes', 'What similarities and differences do these entries have', 'How do these titles differ in their recorded information', 'Outline the distinctions between this set', 'Walk through the factual differences among these books'],
 'FIELD':['Which entry comes out ahead for {field}', 'Compare this pair in terms of {field}', 'Display their {field} side by side across these books', 'Focus the comparison on {field}', 'How does {field} differ across this group', 'Evaluate the titles using {field} alone', 'Contrast this set by {field}', 'Show me a side-by-side view of {field}'],
 'PREFERENCE':['Help decide which of these suits me{purpose}', 'Which would you choose for me{purpose}', 'I want the better fit from this set{purpose}', 'Pick the best choice for my reading needs{purpose}', 'Advise me which title to favour{purpose}', 'Which selection would serve my purpose best{purpose}', 'Tell me which of the choices makes more sense{purpose}', 'Guide my choice between these volumes{purpose}'],
 'AVAILABILITY':['Could I get a copy of {ref} today', 'Check whether {ref} is sitting on the shelf', 'Is {ref} currently checked out', 'What is the copy situation for {ref}', 'Would a copy of {ref} be obtainable now', 'Does {ref} have any copies left to lend', 'Can the library supply {ref} at the moment', 'Tell me whether {ref} is ready for borrowing'],
 'DETAILS':['Who created {ref}', 'Bring up the catalogue entry for {ref}', 'What information is recorded about {ref}', 'Give me the author and subject information for {ref}', 'Introduce {ref} using the catalogue', 'What does the record say about {ref}', 'I need bibliographic facts about {ref}', 'Describe the listed metadata for {ref}'],
 'BORROW':['Put {ref} on loan to me', 'I would like to take {ref} home', 'Begin a checkout for {ref}', 'Issue a copy of {ref} under my account', 'Can you lend me {ref}', 'Make {ref} my next checkout', 'Arrange for me to borrow {ref}', 'Start borrowing {ref}'],
 'RETURN':['Check my copy of {ref} back into the library', 'Close my active loan of {ref} by returning it', 'I am giving {ref} back', 'Process a return for {ref}', 'End the borrowing period for {ref}', 'Accept the return of {ref}', 'Log {ref} as handed back', 'Close out my loan of {ref}'],
 'RESERVE':['Put me on the waiting queue for {ref}', 'I want a hold placed on {ref}', 'Keep a copy of {ref} for me when one opens up', 'Make a reservation for {ref}', 'Could I join the queue for {ref}', 'Arrange a hold for {ref} under my name', 'Request the next copy of {ref}', 'Reserve my place to borrow {ref}'],
 'ADD_LIST':['Remember {ref} for my future reading', 'Bookmark {ref} on my list', 'Save {ref} among my planned reads', 'Add {ref} to the books I have saved', 'Keep {ref} in my reading list', 'Put {ref} on my saved pile', 'Mark {ref} for later reading', 'Store {ref} in my bookmarks'],
 'REMOVE_LIST':['Take {ref} off my saved reading pile', 'I no longer want {ref} bookmarked', 'Delete the saved entry for {ref}', 'Remove {ref} from my planned reading', 'Discard {ref} from my bookmarks', 'Unsave {ref} from my list', 'Drop {ref} from the books I plan to read', 'Erase the bookmark for {ref}'],
 'CLEAR_LIST':['Remove everything I have saved for reading', 'Empty the entire bookmark collection', 'I want my whole reading list cleared', 'Delete every saved reading entry', 'Clear out all my planned reads', 'Wipe the complete collection of bookmarks', 'Discard my full saved list', 'Erase all the books on my reading list'],
 'LOANS':['Which library books are still with me', 'What do I currently need to bring back', 'Show everything currently checked out under my account', 'List the volumes I am still borrowing', 'What items remain on loan to me', 'Have I still got library books at home', 'What needs returning from my current checkouts', 'Retrieve the books still lent under my name'],
 'FEES':['Is there a library balance I need to settle', 'Have any overdue charges been put on my account', 'What amount remains unpaid at the library', 'Check whether I owe money on my account', 'Are there fines outstanding against my membership', 'How much would settle my library debt', 'Show any charges I have yet to pay', 'Does my account have a monetary balance due'],
 'RESERVATIONS':['Which books am I waiting in line for', 'Have I requested any copies that are pending', 'List the holds attached to my membership', 'What titles are being held for me', 'Am I in any book queues at present', 'Show my pending book requests', 'Which reservations are linked to my account', 'What books am I expecting through a hold'],
 'HISTORY':['What was on my earlier checkout record', 'Which books have I taken out in the past', 'Look up my previous borrowing activity', 'Show the items I finished borrowing', 'Retrieve my past loan transactions', 'What titles did I previously bring back', 'List my earlier library checkouts', 'What has my borrowing activity been lately'],
 'READING_LIST':['What have I put aside to read later', 'Show my personal saved book collection', 'Retrieve my bookmarked titles', 'List the books I plan to read', 'Which entries are in my saved reading pile', 'Bring up the titles I have kept for later', 'Open my planned reading collection', 'Show what I bookmarked for future reading'],
 'BOOK_CONTENT':['Explain the events of chapter four in {ref}', 'What does the actual text of {ref} say about courage', 'Summarize the opening passage from {ref}', 'Interpret the conclusion in {ref}', 'Discuss the argument made inside {ref}', 'Answer from the full text of {ref} about memory', 'Explain a scene in the third chapter of {ref}', 'What does the narrator in {ref} mean by loyalty'],
 'DOCUMENT_CONTENT':['Explain the conclusion in the PDF I uploaded', 'Summarize the attached file for me', 'Find the argument about policy inside my document', 'Answer this using my uploaded report', 'Discuss the findings on page three of my PDF', 'What is stated in the document I attached', 'Interpret a passage in my private upload', 'Describe the methods used in my uploaded file'],
 'HELP':['Explain what library membership lets me do', 'How does the library lending process work', 'Give me guidance on using the library service', 'What are the general borrowing policies', 'Describe how reservations work in this library', 'Help me understand the rules of this service', 'Walk me through library membership', 'Explain the services offered by the library'],
 'UNKNOWN':['Compose an advertisement for a bakery', 'What is the weather in Helsinki', 'Solve this arithmetic puzzle', 'Book me a train ticket', 'Translate a sentence into Italian', 'Write code for a calculator', 'Tell me a joke about cats', 'Order a meal to my house'],
 'SHOW_MORE':['Continue the displayed result list', 'Give the next page of matches', 'Show more entries from this search', 'Load further results from this list', 'Display the following page of matched books', 'Are there more results beyond these', 'Keep paging through this result set', 'Display the remaining search matches'],
 'REFINE':['Limit the current matches to copies in stock', 'Reorder this result list alphabetically', 'Keep highly rated entries in this list', 'Filter the present results to fiction', 'Narrow these matches by author', 'Show only available books from these results', 'Sort the books already found by title', 'Filter this list down to science titles'],
}
FIELDS={'average_rating':['reader scores','average star rating','overall review rating'], 'rating_count':['number of reader reviews','rating count','how many ratings they received'], 'subjects':['subject coverage','number of listed topics','listed subject matter'], 'availability':['copy availability','stock status','available copy counts'], 'authors':['authorship','the writers','author names'], 'description':['catalogue summaries','their descriptions','the recorded synopsis']}
REFS={'FIRST':['the first book','the former volume','book one'], 'SECOND':['the second book','the latter volume','book two'], 'LAST':['the final book','the last volume','the entry at the end'], 'OTHER':['the other book','the remaining one','the alternative member of the pair'], 'FOCUS':['it','that one','this book'], 'ALL':['these books','all of the listed books','the books in this group'], 'EXPLICIT':['Tides over Meridian','The Glass Apiary','A Map of Silent Rivers']}
TOPICS=['beekeeping','personal accounting','data visualisation','coastal ecology','public speaking','medieval trade','ceramic design','number theory','bird migration','woodworking','food chemistry','garden planning','oral history','electrical circuits','community leadership','acoustic music','planetary science','urban cycling','botanical illustration','statistics','geography','ethical philosophy','soil conservation','stage lighting']
PURPOSES=['',' for understanding coastal ecology',' for a novice studying electrical circuits',' because I want practical guidance on woodworking',' for a course on medieval trade',' to learn how to organise community projects']
TITLES=['The Amber Estuary','Practical Glassmaking','An Atlas of Orchard Birds','The Violet Ledger','Sailing Past Winter','Quiet Cities','Experiments with Clay','A Handbook of Sky Maps','The Cedar Workshop','Songs of a Small Harbour','Measuring the Tide','The Copper Garden']
HEADS=['intent_family','intent_subtypes','reference','position','fields','criterion','action']
ROOT=Path(__file__).resolve().parents[1]

def norm(text):return ' '.join(''.join(c if c.isalnum() else ' ' for c in text.casefold()).split())

def seed_rows():
    return [{'seed_id':f'{sub}:{i}', 'family_id':f'{sub}:{i}', 'split':'train' if i<4 else 'dev' if i<6 else 'internal', 'subtype':sub,'message':text} for sub,values in SEEDS.items() for i,text in enumerate(values)]

def contexts(rng):
    books=[{'work_id':'SYNTH_'+str(i),'title':t} for i,t in enumerate(rng.sample(TITLES,8))]
    a,b=books[:4],books[4:];aid=[x['work_id'] for x in a];bid=[x['work_id'] for x in b]
    values=[('none',{}), *[(f'selected_{n}',{'selected_books':a[:n]}) for n in [1,2,3,4]],
      ('previous_comparison',{'previous_comparison':a[:2],'active_result_context':{'type':'comparison','books':a[:2],'work_ids':aid[:2]}}),
      ('previous_recommendations',{'previous_recommendations':{'work_ids':aid,'books':a},'active_result_context':{'type':'recommendations','books':a,'work_ids':aid}}),
      ('page',{'page_books':a[:1]}),('stale_comparison',{'selected_books':a[:2],'previous_comparison':b[:2],'active_result_context':{'type':'comparison','books':b[:2],'work_ids':bid[:2]}}),
      ('selection_changed',{'selected_books':a[:3],'previous_comparison':b[:2],'selection_changed':True}),
      ('page_previous',{'page_books':a[:1],'previous_comparison':b[:2],'active_result_context':{'type':'comparison','books':b[:2],'work_ids':bid[:2]}}),
      ('document',{'document_id':'SYNTH_DOCUMENT'}),('authorized_book',{'page_books':a[:1],'book_rag_context':True}),
      ('recent',{'active_result_context':{'type':'availability','books':a[:2],'work_ids':aid[:2]}})]
    for name,c in values:
        source,pool=context_pool(c)
        if pool:c['last_referenced_work_ids']=[rng.choice(pool)]
        yield name,c

def build(paraphrases,seed=947):
    rng=random.Random(seed);rows=[];seen={};frozen=json.loads((ROOT/'reports/assistant_router_v3_baseline_snapshot/existing_sealed.json').read_text(encoding='utf8'))+json.loads((ROOT/'reports/assistant_router_v3_baseline_snapshot/hidden_sealed.json').read_text(encoding='utf8'))
    forbidden={norm(x['message']) for x in frozen};rejected=Counter()
    for s in seed_rows():
      sub=s['subtype'];sentences=[s['message'], *paraphrases.get(s['seed_id'],[])]
      for pi,template in enumerate(sentences):
        if '{ref}' in template: positions=rng.sample(list(REFS),4)
        else:positions=['ALL']
        for pos in positions:
          variants=[(f,p) for f in (list(FIELDS) if sub=='FIELD' else ['NONE']) for p in (PURPOSES if sub=='PREFERENCE' else [''])]
          for field,purpose in variants:
            message=template.replace('{ref}',rng.choice(REFS[pos])).replace('{topic}',rng.choice(TOPICS)).replace('{field}',rng.choice(FIELDS[field]) if field!='NONE' else '').replace('{purpose}',purpose)
            # Controlled generic character noise, never a hand-coded typo dictionary.
            if s['split']=='train' and rng.random()<.08 and len(message)>20:
              j=rng.randrange(2,len(message)-2)
              if message[j].isalpha() and message[j+1].isalpha():message=message[:j]+message[j+1]+message[j]+message[j+2:]
            if norm(message) in forbidden:rejected['frozen_exact']+=1;continue
            # Same text can repeat under distinct contexts within its own family.
            owner=seen.get(norm(message))
            if owner and owner!=s['family_id']:rejected['cross_family_duplicate']+=1;continue
            seen[norm(message)]=s['family_id']
            for name,c in contexts(rng):
              source,pool=context_pool(c);reference='EXPLICIT' if pos=='EXPLICIT' else source
              position='ALL' if pos=='EXPLICIT' else pos
              if FAMILIES[sub] in {'ACCOUNT','HELP','UNKNOWN','CONTEXT'} or sub in {'SEARCH','DOCUMENT_CONTENT'}:reference='NONE'
              if sub=='RECOMMEND' and not pool:reference='NONE'
              r={'seed_id':s['seed_id'],'family_id':s['family_id'],'split':s['split'],'message':message,'context':c,'context_kind':name,'origin':'manual_seed' if pi==0 else 'offline_qwen', 'intent_family':FAMILIES[sub],'intent_subtypes':sub,'reference':reference,'position':position,'fields':field,'criterion':'PRESENT' if purpose else 'ABSENT','action':sub+(':'+field if sub=='FIELD' else '')}
              r['id']=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()[:20];rows.append(r)
    # Do not inflate count through repeated equivalent instances.
    unique={r['id']:r for r in rows};rows=list(unique.values())
    return rows,dict(rejected)

def loss_mask(row,head):
    if head=='fields':return row['intent_subtypes']=='FIELD'
    if head=='criterion':return row['intent_subtypes']=='PREFERENCE'
    if head=='position':return row['reference'] not in {'NONE','AMBIGUOUS','EXPLICIT'}
    return True
