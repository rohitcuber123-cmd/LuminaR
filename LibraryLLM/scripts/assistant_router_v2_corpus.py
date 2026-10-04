"""Held-out language: evaluation data, never imported by production routing."""
from evaluate_assistant_semantics import A,B,C,D


def hidden():
    rows=[]
    def group(domain,category,intent,messages,ids=(A,B),context='selected',criterion=False,fields=None):
        rows.extend(dict(domain=domain,category=category,expected_intent=intent,message=m,
            expected_ids=list(ids),context=context,criterion=criterion,fields=fields or []) for m in messages)
    group('comparison','factual_comparison','COMPARE_BOOKS',[
        'walk me through the ways these two diverge',
        'give me a neutral account of how my picks vary',
        'lay out the similarities alongside the differences',
        'what distinguishes their catalogue entries from each other?',
        'compare their recorded attributes without recommending either',
        'summarise the contrasts in this pair',
        'how closely do the two entries match?',
        'I wanna see the differences between my selections',
        'could u juxtapose these books for me?',
        'describe the distinguishing features of each pick',
        'make a factual side-by-side of both entries',
        'where are these books alike and where are they different?',
        'review the differences across the selected titles',
        'please compare these without choosing a winner',
        'is there much difference btwn my two picks?'])
    group('preference_criterion','preference','COMPARE_BOOKS',[
        'I gotta choose one, any thoughts?',
        'which of my selections would you advise me to read?',
        'would you lean toward one of these?',
        'pick the more suitable one for me please',
        'which is the smarter reading choice here?'])
    group('preference_criterion','preference_criterion','COMPARE_BOOKS',[
        'which fits a first-year student looking into football finances?',
        'help choose the book that suits a dissertation on league business',
        'as someone totally new to sports markets, which would fit me?',
        'my focus is commercial football clubs; which pick fits that goal?',
        'which selection makes sense for studying how leagues earn money?',
        'if I need an introductory treatment of sports finance, which should I read?',
        'I teach economics and need material on soccer; which would you suggest?',
        'choose between these for a reader researching professional sport',
        'which will suit me if im learning the business side of soccer?',
        'for my essay on football revenues, which of the pair is appropriate?'],criterion=True)
    group('availability','availability','CHECK_AVAILABILITY',[
        'are there spare copies for either pick?',
        'which titles in my selection can be taken out today?',
        'can someone check the present stock of both?',
        'any copies left of these two?',
        'are my chosen books actually on hand?',
        'do these entries have available copies rn?',
        'is either selected title out of stock?',
        'show whether these books are ready to borrow',
        'have copies of both been checked out already?',
        'whats the current copy availability across my picks?'])
    group('recommendation','recommendation','RECOMMEND_FROM_SELECTION',[
        'suggest a next book using both of these as inspiration',
        'base a few reading suggestions on my chosen pair',
        'I enjoy these selections, propose my next reads',
        'use the two selected titles to generate recommendations',
        'what should I read next given these picks?',
        'gimme some recommendations based on both',
        'my pair represents my taste; suggest more books',
        'build a reading recommendation list using these two seeds',
        'take my selections into account and suggest titles',
        'recommend my next reads from these choices'])
    group('graph_details','graph','MORE_LIKE_THIS',[
        'find connections to the first selected title',
        'trace related books from the earlier selection',
        'gimme a book connected to selection one'],ids=(A,))
    group('graph_details','graph','MORE_LIKE_THIS',[
        'what titles are neighbours of selection two?',
        'find books in the same vein as the latter selection'],ids=(B,))
    group('graph_details','ordinal_details','BOOK_DETAILS',[
        'show the catalogue information for the former selection',
        'could u tell me about book number 1?'],ids=(A,))
    group('graph_details','ordinal_details','BOOK_DETAILS',[
        'open up the metadata of the latter book',
        'who is credited with writing the last selection?',
        'let me see the information about pick number 2'],ids=(B,))
    for intent,messages in {
        'USER_LOANS':['list the books I have checked out at present','am I holding any library books rn?','what items are currently on loan to me?'],
        'USER_FEES':['are any charges still owing on my library account?','tell me my outstanding library debt','whats my unpaid fine amount?'],
        'USER_RESERVATIONS':['show the items I am queued up for','any books on hold under my account?','which reservations are pending for me?'],
        'USER_HISTORY':['show records of my completed borrows','what did I take out previously?','bring up my loan history please'],
        'USER_READING_LIST':['bring up the titles saved for future reading','what is on my to-read list?','show books I bookmarked in my reading list'],
    }.items():group('account','account',intent,messages,ids=(),context='none')
    group('search','search','SEARCH_BOOKS',[
        'im looking for an introduction to oceanography',
        'got any titles that cover sustainable transport?',
        'I would like to browse books concerning ancient pottery',
        'need reading material on personal tax planning',
        'can u find titles about the mathematics of games?',
        'show me a few books dealing with food science',
        'I am after beginner books covering satellite technology',
        'help locate some reading on the history of printing',
        'are there books discussing public health policy?',
        'find reading material concerning home composting'],ids=(),context='none')
    # Dedicated twenty-case previous-comparison subset, no selection.
    group('context_followups','previous_comparison','CHECK_AVAILABILITY',[
        'can I take out either of the books we just compared?',
        'how is stock looking for that pair?',
        'are copies of those compared books free?',
        'of that previous pair, which can be borrowed?',
        'check the availability of both entries from the comparison'],context='comparison')
    group('context_followups','previous_comparison','COMPARE_BOOKS',[
        'which of those had a stronger star score?',
        'compare the ratings of the pair we discussed',
        'what were their recorded ratings like?'],context='comparison',fields=['average_rating'])
    group('context_followups','preference_criterion','COMPARE_BOOKS',[
        'which compared title would fit an undergraduate studying football finance?',
        'from that pair, choose for someone researching sports revenues',
        'which of those is suitable for someone new to football economics?',
        'id like the one that suits a sports business course; which is it?'],context='comparison',criterion=True)
    group('context_followups','previous_comparison','BOOK_DETAILS',[
        'bring up details for the latter book from our comparison',
        'who wrote the second compared title?',
        'show the catalogue entry of the last one we compared',
        'tell me more about book two from that pair'],ids=(B,),context='comparison')
    group('context_followups','previous_comparison','MORE_LIKE_THIS',[
        'find connected titles around the former of those books',
        'what is related to the first entry we compared?',
        'show graph neighbours for the earlier compared title',
        'any similar books linked to the first from that comparison?'],ids=(A,),context='comparison')
    group('explicit_page','explicit_entity','BOOK_DETAILS',[
        'I would like the catalogue information for Dune',
        'can you identify the writer of Dune?',
        'show me the entry named Dune'],ids=(D,))
    group('explicit_page','explicit_entity','CHECK_AVAILABILITY',[
        'are any copies of Dune presently free?',
        'does Dune have an available copy in the library?'],ids=(D,))
    group('explicit_page','page','CHECK_AVAILABILITY',[
        'is a copy of the book on this page ready?',
        'could I get a copy of this title today?'],ids=(B,),context='page')
    group('explicit_page','page','BOOK_DETAILS',[
        'who is credited as the writer of this title?',
        'bring up the metadata for the book I am viewing'],ids=(B,),context='page')
    group('explicit_page','page','MORE_LIKE_THIS',[
        'what other titles connect to the book on this page?'],ids=(B,),context='page')
    group('selection_change','selection_change','COMPARE_BOOKS',[
        'compare the catalogue ratings of my newly selected pair',
        'which current selection gets the stronger rating?',
        'I changed my picks, compare their ratings now'],ids=(C,D),context='changed',fields=['average_rating'])
    group('selection_change','factual_comparison','COMPARE_BOOKS',[
        'how do my new selections differ in their catalogue entries?',
        'lay out the differences for the books currently in my tray',
        'compare the attributes of this new pair'],ids=(C,D),context='changed')
    assert len(rows)==121
    return rows


if __name__=='__main__':
    import hashlib,json
    from pathlib import Path
    from collections import Counter
    import evaluate_assistant_semantics as original
    from assistant.router_v2 import examples,make_plan
    rows=hidden()
    primary={c['message'] for c in original.corpus()}
    shots={m for context in [{},{'selected_books':[{'work_id':A},{'work_id':B}]},{'page_books':[{'work_id':A}]}]
        for m,_ in examples(make_plan(context),False)}
    assert not ({r['message'] for r in rows}&(primary|shots))
    body=json.dumps(rows,sort_keys=True,ensure_ascii=False)
    path=Path(__file__).resolve().parents[1]/'reports/assistant_router_v2_hidden_manifest.json'
    assert not path.exists(),'Never reseal an observed held-out corpus'
    path.write_text(json.dumps({'sealed':True,'sha256':hashlib.sha256(body.encode()).hexdigest(),
        'total':len(rows),'domains':dict(Counter(r['domain'] for r in rows)),
        'policy':'Never use these utterances in prompts, few-shots, production rules or post-result tuning',
        'cases':rows},indent=2),encoding='utf8')
