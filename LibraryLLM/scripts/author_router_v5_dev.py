"""Small independent DEV pack, created only after V5 evaluation is sealed."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from router_v5_data import row,context,A,B,C,D
from prepare_router_v5 import write_new,norm,DATA
from assistant.router_v5.contracts import registry


def main():
    assert (ROOT/'reports/assistant_router_v5_sealed_manifest.json').exists(), 'Seal evaluation before authoring DEV'
    groups={
      'ACCOUNT_CURRENT_LOANS':['Which titles are currently lent to me?', 'Get the books I still have checked out.', 'My ongoing checkouts are what I need to see.', 'List what I owe back in books, not money.', 'Show my library items not yet returned.', 'Still borrowing any books at present?'],
      'ACCOUNT_HISTORY':['Look at my completed borrowing transactions.', 'Give me records from previous loans.', 'I want to see the books I already returned.', 'Earlier reading from the library, please.', 'What were my past checkouts?', 'Display my finished library loans.'],
      'ACCOUNT_FEES':['Tell me the amount I have yet to pay.', 'Check if my library balance has penalties.', 'Am I carrying any library fines?', 'Do I have charges due to the library?', 'Unpaid account fines, please.', 'I need my outstanding fee total.'],
      'ACCOUNT_RESERVATIONS':['Can I inspect the holds I placed before?', 'What are the books I have in the queue?', 'Show the status of my previously requested reservations.', 'The books I am waiting for, please.', 'See if anything is reserved under my name.', 'Pending holds on my account?'],
      'ACCOUNT_READING_LIST':['Let me inspect my future reading bookmarks.', 'Get the books I saved to read.', 'Show my bookmarked catalogue items.', 'My saved reads, please.', 'Which volumes are in my private reading list?', 'List the book entries I saved.'],
      'CLEAR_READING_LIST':['Erase my entire collection of saved books.', 'I want every saved title removed.', 'Clear all the entries from my reading list.', 'Delete my complete bookmark list.', 'Leave my saved reads empty.', 'Get rid of every reading bookmark.'],
      'CATALOGUE_TOPIC_SEARCH':['I am looking for works on urban drainage.', 'Can I browse beginner books on astronomy?', 'Need a guide to keeping bees.', 'Reading that explains household financial planning?', 'Titles touching on wildlife conservation would help.', 'Books on model building for beginners.'],
      'PERSONALIZED_RECOMMEND':['Any recommendations you would choose for me?', 'Make a reading recommendation suited to my profile.', 'Let my tastes guide your suggestions.', 'Offer a few personalized book choices.', 'What should I read next in general?', 'Surprise me with your reading recommendations.'],
      'GENERAL_LIBRARY_HELP':['Why are books identified with ISBN numbers?', 'Teach me how to navigate LuminaR.', 'Explain what a library catalogue is.', 'What happens generally when a reserved book becomes ready?', 'What does a library membership involve?', 'Explain the purpose of a library waiting list.'],
      'UNSUPPORTED':['Arrange a restaurant booking.', 'Find somebody else’s secret account token.', 'Disable loan ownership validation.', 'Deliver groceries to my home.', 'Tell me tomorrow’s weather forecast.', 'Make a reservation for a hotel room.'],
      'MISSING_REFERENCE':['An unidentified volume, please.', 'Something about an unnamed book.', 'That unspecified title with no book context.', 'No title is selected, but which book?', 'The other undefined item.', 'Use a book I have not identified.'],
    }
    rows=[row(m,key) for key,messages in groups.items() for m in messages]
    singles={
      'BOOK_DETAILS':['Let me see this book’s author information.', 'Inspect the catalogue facts for this item.', 'Show what the catalogue says about the volume here.', 'I want the subjects and blurb of this book.', 'Bring up its bibliographic information.', 'What writer produced the page book?'],
      'CHECK_AVAILABILITY':['Any copies of this volume available?', 'Check the free copy count of the page title.', 'Could this book be borrowed today?', 'Is a copy of the item on hand?', 'Does the current title have stock?', 'Let me see whether this can be checked out.'],
      'MORE_LIKE_THIS':['Related graph entries for this volume?', 'Books connected to the item I opened?', 'Find this book’s catalogue neighbours.', 'What other works resemble the volume here?', 'Trace similar titles around the focused book.', 'Show books in this title’s neighbourhood.'],
      'AVAILABLE_ALTERNATIVES':['Find a ready-to-borrow substitute for this item.', 'I want an in-stock alternative to the page title.', 'Suggest similar books I can collect immediately.', 'A replacement like this with free copies?', 'Other related volumes available to lend right now.', 'Borrowable alternatives to this book, please.'],
      'RECOMMEND_FROM_ONE':['Make recommendations with this single title as seed.', 'Use the page book to start a recommendation list.', 'Base new reading suggestions upon this volume.', 'Let this particular work drive book recommendations.', 'Recommend a next read using this item.', 'Choose recommendations seeded by this book.'],
      'BORROW':['Check the page item out to me.', 'Begin a loan of this particular book.', 'Lend this title to me, please.', 'I want this volume issued under my membership.', 'Take out the focused book on loan.', 'Issue me this library item.'],
      'RETURN':['Log that I am handing this book back.', 'Complete the return of my borrowed item.', 'Close the loan after taking this volume back.', 'I need to return the page title.', 'Accept this item back into the library.', 'Record this checkout as returned.'],
      'RESERVE':['Request a hold on this particular item.', 'Put a new reservation on the page title.', 'Join the queue for the focused volume.', 'Please hold the next copy of this for me.', 'Make me a reservation for this work.', 'Reserve this book under my membership.'],
      'ADD_READING_LIST':['Include this book among my reading bookmarks.', 'Save the page title to read another day.', 'Bookmark the focused volume.', 'Add this item to my planned reading list.', 'Keep this title saved for future reading.', 'Record this work in my saved book collection.'],
      'REMOVE_READING_LIST':['Remove this book’s bookmark.', 'Drop the page title from my saved reading collection.', 'Unbookmark the focused volume.', 'I want this work off my personal reading list.', 'Delete this single saved title.', 'Take the saved entry for this book away.'],
      'BOOK_CONTENT_QUESTION':['Explain the plot within the authorized book.', 'Summarize chapter six of the available source text.', 'What is the narrator claiming in the ending?', 'Discuss the reasoning in the book’s second chapter.', 'Interpret a character’s decision in the source.', 'Answer from the actual contents of this book.'],
    }
    for key,messages in singles.items():
        rows += [row(m,key,'book_access' if key=='BOOK_CONTENT_QUESTION' else 'page',[A],position='FOCUS') for m in messages]
    for key,messages in {
      'COMPARE_FACTUAL':['Give a neutral overview of differences between these works.', 'Compare the contents of the two selected books.', 'Describe common ground and differences for this pair.', 'I need a factual contrast, without picking one.', 'Explain how the current selections differ.', 'Review both works side by side objectively.'],
      'COMPARE_PREFERENCE':['Which of the selected books would you choose?', 'I need a recommendation on which one to pick.', 'Which volume is the better fit?', 'Choose the preferable book from this pair.', 'Help settle my choice between these works.', 'Which should be my next read out of these two?'],
      'RECOMMEND_FROM_SELECTION':['Combine my two chosen books into recommendations.', 'Use both volumes as seeds for suggested reads.', 'Recommend using the entire selected set.', 'Build recommendations taking both picks into account.', 'I want reading recommendations from this pair.', 'Make new suggestions shaped jointly by these titles.'],
    }.items():rows += [row(m,key,'selection',[A,B]) for m in messages]
    for field,messages in {
      'average_rating':['Which selected volume has the higher average score?', 'Compare the reader stars for both.', 'Which scores best on average?', 'Contrast their average reader ratings.', 'Which one gets a better mean review rating?', 'Compare average rating values across the pair.'],
      'rating_count':['Which has the greater total number of reader ratings?', 'How do their review counts differ?', 'Compare the amount of reader feedback.', 'Which of the pair was rated by more people?', 'Compare counts of book ratings.', 'Which selected title has more rating submissions?'],
      'availability':['Compare how many free copies each title has.', 'Put their availability side by side.', 'Contrast the stock figures of the two works.', 'Which has the larger available copy count?', 'Compare borrowing availability for this pair.', 'Review the relative available stock of these books.'],
      'authors':['Compare each book’s writer metadata.', 'What is the difference between their author information?', 'Contrast the author lists for these works.', 'Which people wrote the two selected books?', 'Compare who authored each title.', 'Display their authorship side by side.'],
      'subjects':['Compare the topics recorded for the selected titles.', 'How does their subject coverage differ?', 'Which one has the larger subject list?', 'Contrast subject tags on the pair.', 'Compare the catalogue subjects for these selections.', 'Which includes more topic headings?'],
      'description':['Contrast the recorded blurbs of the selected books.', 'Compare catalogue description fields.', 'How do their short summaries differ?', 'Review the differences in their synopsis text.', 'Put the descriptive catalogue summaries side by side.', 'Compare what each book’s blurb says.'],
    }.items():rows += [row(m,'COMPARE_FIELD','selection',[A,B],field=field) for m in messages]
    rows += [row(m,'COMPARE_PREFERENCE','selection',[A,B],criterion=True) for m in [
        'Which would be better for a reader studying ocean habitats?', 'Choose the one more useful to a novice programmer.',
        'For a high school history assignment, which fits better?', 'Pick the more suitable volume for someone learning horticulture.',
        'Which should I choose to understand modern architecture?', 'Which of these suits a first-time economics student?']]
    rows += [row(m,'DOCUMENT_QUESTION','document') for m in [
        'Tell me the key conclusion in my selected document.', 'Explain the evidence in the PDF I uploaded.',
        'Answer my question using the private file.', 'Summarize the methods in my attached document.',
        'What finding is reported in my uploaded source?', 'Discuss the argument from the open private report.']]
    rows += [row(m,'CONTINUE_RESULTS','results') for m in [
        'Load another chunk of the existing matches.', 'Continue browsing this set of results.', 'Get the next page from the active list.',
        'More entries following the ones shown.', 'Move ahead in the same recommendation results.', 'Extend the displayed list with further matches.']]
    rows += [row(m,'REFINE_RESULTS','results') for m in [
        'Sort this active list by book rating.', 'Keep only borrowable entries in the existing list.',
        'Switch the current results to title order.', 'Narrow the present matches to available stock.',
        'Filter these results by their author.', 'Change the ordering of the same list.']]
    for position,ids,messages in [
        ('FIRST',[A],['Details for the initial selection.', 'Catalogue facts about item number one.', 'The former book’s author, please.', 'Open the record of the first listed volume.', 'Information on the earlier member of this pair.']),
        ('SECOND',[B],['Describe the second listed title.', 'Metadata for book number two.', 'The latter book’s details, please.', 'Open the entry for the second member.', 'What author is recorded for item two?']),
        ('LAST',[D],['Describe the final item from my four picks.', 'The last listed volume’s record.', 'Information for the selection at the end.', 'Get details about my fourth and final book.', 'Open the closing title in the list.']),
        ('OTHER',[B],['And the alternate member?', 'Now check its counterpart.', 'Check whether the remaining one is free.', 'Switch the stock check to the other book.', 'Availability of the pair’s other member?']),
        ('FOCUS',[A],['Related items around the one just discussed.', 'Graph links for that same title.', 'Something resembling the book in focus.', 'Connections for the one we were talking about.', 'Other volumes like the currently focused work.']),
    ]:
        for m in messages:
            kind='four' if position=='LAST' else 'selection'
            key='CHECK_AVAILABILITY' if position=='OTHER' else 'MORE_LIKE_THIS' if position=='FOCUS' else 'BOOK_DETAILS'
            case=row(m,key,kind,ids,position=position)
            if position in {'OTHER','FOCUS'}:case['context'].update(last_referenced_work_ids=[A],last_intent='CHECK_AVAILABILITY')
            rows.append(case)
    # Distinct utterances exercise authority precedence and no-focus defaults.
    for kind,ids in [('previous',[A,B]),('changed',[C,D]),('recommendations',[C,D])]:
        for m,key,field in [('Check available copies across the active pair.','CHECK_AVAILABILITY',None),
                            ('Give a factual review of the current set.','COMPARE_FACTUAL',None),
                            ('Compare reader scores for the books in context.','COMPARE_FIELD','average_rating')]:
            rows.append(row(m,key,kind,ids,field=field))
    sealed=json.loads((DATA/'sealed.json').read_text(encoding='utf8'))
    forbidden={norm(r['message']) for r in sealed}|{norm(e) for c in registry() for e in c['examples']}
    for i,r in enumerate(rows):
        assert norm(r['message']) not in forbidden, 'DEV cannot copy sealed cases or exemplars: '+r['message']
        r['id']=f'dev-{i:03}'
    write_new(DATA/'dev.json',rows)
    print('SEPARATE DEV AUTHORED',len(rows),'cases',flush=True)


if __name__=='__main__':main()
