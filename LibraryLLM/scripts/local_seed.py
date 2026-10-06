"""Repeatable sample data for an isolated, loopback-only development database."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
os.chdir(ROOT)

TOPICS = [
    ('Database Foundations', 'Computer Science', 'A database is an organized collection of information. A primary key uniquely identifies a record in a table. A foreign key links a record to a record in another table. An index speeds up lookups but requires additional storage. A transaction groups related changes into one reliable operation. Atomicity means that every operation in a transaction succeeds or none of the operations takes effect.'),
    ('Network Essentials', 'Computer Science', 'A network connects computers so they can exchange information. An IP address identifies an interface on a network. A router forwards packets between networks. DNS translates domain names into IP addresses. TCP provides an ordered stream of bytes and retransmits lost data. TLS encrypts traffic between a client and a server. A firewall filters traffic using rules.'),
    ('Python Study Guide', 'Programming', 'Python is a programming language used for automation and data processing. A variable refers to a value. A function packages reusable instructions and can return a result. A list stores an ordered sequence of values. A dictionary maps keys to values. An exception signals an error that a program can handle. A virtual environment separates the dependencies of one project from other projects.'),
    ('Web Application Design', 'Programming', 'A web application combines a user interface with server services. A browser sends an HTTP request to a server. A server returns an HTTP response with a status code. Authentication identifies the user. Authorization determines which actions that user may perform. Input validation rejects values that violate an expected format. A session associates requests with a signed-in user.'),
    ('Library Operations Handbook', 'Library Science', 'A library catalogue records the titles and authors of library materials. Inventory records the number of physical copies at a location. A loan temporarily assigns a copy to a borrower. A due date specifies when a borrowed copy must be returned. A reservation places a reader in a queue for a title. Returning a copy increases the number of available copies. A reading list stores books a reader plans to explore.'),
    ('Information Security Basics', 'Computer Science', 'Information security protects confidentiality, integrity and availability. Confidentiality limits access to authorized people. Integrity protects information from unauthorized changes. Availability keeps information accessible when it is needed. A password hash is a derived value used to verify a password without storing the original password. Least privilege grants only the permissions needed for a task. A backup provides a recoverable copy of important information.'),
    ('Statistics for Beginners', 'Mathematics', 'Statistics describes patterns in collected observations. The mean is the sum of observations divided by their count. The median is the middle value after the observations are ordered. The mode is the value that appears most frequently. Variance measures the spread of observations around the mean. A sample is a subset of a larger population. Correlation measures an association and does not establish causation.'),
    ('Learning and Memory', 'Education', 'Active recall asks a learner to retrieve information from memory. A flashcard pairs a question with an answer. Spaced practice revisits information after increasing intervals. Interleaving mixes related topics during practice. Feedback helps a learner correct misunderstandings. A source citation lets a reader inspect the evidence behind a statement. A study summary selects the most useful ideas from a longer source.'),
    ('Project Planning Workbook', 'Management', 'A project is a temporary effort to produce a defined result. A milestone marks an important point in the project. A task has a responsible person and a completion condition. A dependency means one task relies on another task. A risk is an uncertain event that may affect a project. A checkpoint records completed work and the next action. Version control preserves a history of changes to project files.'),
    ('Environmental Science Notes', 'Science', 'An ecosystem includes organisms and their physical environment. Biodiversity describes the variety of living organisms. Producers convert energy into forms used by other organisms. Consumers obtain energy by eating organisms or organic matter. Decomposers break down dead material and return nutrients to the environment. A food web describes feeding relationships in an ecosystem. Conservation protects habitats and biological resources.'),
    ('Research Methods Primer', 'Education', 'A research question defines what an investigation seeks to understand. A hypothesis is a testable explanation. An experiment compares outcomes under controlled conditions. A control group provides a reference for comparison. A reproducible method describes enough detail for another researcher to repeat the work. A limitation identifies a boundary of the evidence. A citation records the source of an idea or observation.'),
    ('Data Structures Companion', 'Programming', 'A data structure organizes values for efficient use. A stack follows last-in, first-out order. A queue follows first-in, first-out order. A tree connects nodes in a hierarchy. A graph represents nodes and relationships between them. A hash table uses a hash function to locate a value associated with a key. An algorithm is a sequence of steps that solves a defined problem.'),
]

def local_guard():
    uri = os.environ.get('MONGO_URI', '')
    if urlparse(uri).hostname not in ('localhost', '127.0.0.1') or os.environ.get('MONGO_DB_NAME') != 'luminar_local':
        raise SystemExit('Sample setup requires loopback MongoDB and MONGO_DB_NAME=luminar_local.')

def seed(email=None, password=None):
    local_guard()
    from backend.database.mongodb import db
    from backend.services.auth_service import hash_password
    from backend.services.identity_service import next_user_id
    db.users.create_index('email', unique=True)
    db.users.create_index('user_id', unique=True)
    accounts = [('reader@luminar.example.com', 'LuminaR-Local-123!', 'Local Reader', 'GENERAL_USER'),
                ('admin@luminar.example.com', 'LuminaR-Admin-123!', 'Local Admin', 'ADMIN')]
    if email and password:
        accounts.append((email.lower().strip(), password, 'Karthikeya', 'GENERAL_USER'))
    for address, secret, name, role in accounts:
        if not db.users.find_one({'email': address}):
            db.users.insert_one(dict(user_id=next_user_id(), name=name, email=address,
                password_hash=hash_password(secret), role=role, is_email_verified=True,
                is_active=True, created_at=datetime.now(timezone.utc), local_sample=True))
    categories = {}
    for n, (title, subject, text) in enumerate(TOPICS, 1):
        wid = f'OL900000{n:03d}W'  # Local fixture IDs, not Open Library catalogue claims.
        row = dict(book_id=900000+n, work_id=wid, title='Local Sample: '+title,
            authors='LuminaR Development', subjects=subject,
            description='An original local study sample. '+text[:180],
            first_publish_date='2026', average_rating=4.0, rating_count=3,
            reading_log_count=20-n, total_copies=3, available_copies=3,
            shelf_location=f'DEV-{n:02}', cover_url=f'/sample-covers/{wid}.svg',
            created_at=datetime.now(timezone.utc), local_sample=True)
        db.books.update_one({'work_id':wid}, {'$setOnInsert':row}, upsert=True)
        db.library_inventory.update_one({'work_id':wid,'library_id':'LIB001'},
            {'$setOnInsert':dict(work_id=wid, library_id='LIB001', total_copies=3,
                available_copies=3, shelf_location=f'DEV-{n:02}', local_sample=True)}, upsert=True)
        categories[subject] = categories.get(subject, 0)+1
        cover = ROOT/'frontend/public/sample-covers'/f'{wid}.svg'
        cover.parent.mkdir(parents=True, exist_ok=True)
        cover.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="440"><rect width="300" height="440" fill="{["#274b4b","#772f27","#233958"][n%3]}"/><path d="M28 36H272M28 392H272" stroke="#dfc89d"/><text x="28" y="75" fill="#dfc89d" font-size="15">LUMINAR LOCAL LIBRARY</text><foreignObject x="28" y="130" width="244" height="190"><div xmlns="http://www.w3.org/1999/xhtml" style="color:white;font:32px Georgia">{title}</div></foreignObject><text x="28" y="365" fill="#dfc89d" font-size="16">DEVELOPMENT SAMPLE {n:02}</text></svg>', encoding='utf-8')
    for category, count in categories.items():
        preview = db.books.find_one({'subjects':category, 'local_sample':True}, {'_id':0,'work_id':1,'title':1,'authors':1,'book_id':1})
        db.book_categories.update_one({'category':category}, {'$set':{'name':category,'count':count,'preview_book':preview}}, upsert=True)
    print('Local accounts ready; 12 sample books and inventory records available.')

def assets():
    local_guard()
    import fitz
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from backend.database.mongodb import db
    from search.index_manager import IndexManager
    from search.sync_queue import index_root
    from search.lexical_build import build_snapshot
    from search.lexical_store import default_path
    from scripts.build_catalogue_graph import build as build_graph
    from knowledge_graph.core import DEFAULT_GRAPH
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu', local_files_only=True)
    model.max_seq_length = 256
    manager = IndexManager(index_root(), db.books, model, recover=True)
    manager.rebuild_full_index()
    manager.process_once()
    print('Catalogue search index:', manager.status())
    if manager.status()['index_status'] != 'HEALTHY':
        raise RuntimeError('Catalogue index build did not complete; inspect the sync status before starting search.')
    if not (default_path()/'active_lexical.json').exists():
        build_snapshot(db.books.find({}, {'_id':0}), default_path(), source_db='luminar_local', limit=1000)
    if not DEFAULT_GRAPH.exists():
        build_graph(db.books.find({}, {'_id':0}), DEFAULT_GRAPH, db.books.count_documents({}))
    base = ROOT/'rag'
    destination = base/'book_index/rag.index'
    if destination.exists():
        print('Existing book RAG assets retained. Sample PDF is still available.')
    else:
        rows, vectors = [], []
        for n, (title, subject, text) in enumerate(TOPICS, 1):
            wid = f'OL900000{n:03d}W'
            for folder in ('processed', 'book_chunks', 'book_index/books'):
                (base/folder).mkdir(parents=True, exist_ok=True)
            (base/'processed'/f'{wid}.txt').write_text(title+'\n\n'+text, encoding='utf-8')
            (base/'processed'/f'{wid}.book.json').write_text(json.dumps(dict(work_id=wid,
                filename=f'{wid}.txt', rights='authorized', full_text=True, local_sample=True)), encoding='utf-8')
            row = dict(work_id=wid, document_id=wid, chunk_id=f'{wid}_000001',
                title='Local Sample: '+title, author='LuminaR Development', page=1, text=text)
            emb = np.asarray(model.encode([text], normalize_embeddings=True), dtype='float32')
            index = faiss.IndexFlatIP(384); index.add(emb)
            faiss.write_index(index, str(base/'book_index/books'/f'{wid}.index'))
            (base/'book_index/books'/f'{wid}_metadata.json').write_text(json.dumps([row]), encoding='utf-8')
            (base/'book_chunks'/f'{wid}.json').write_text(json.dumps({'chunks':[row]}), encoding='utf-8')
            rows.append(row); vectors.append(emb)
        index = faiss.IndexFlatIP(384); index.add(np.concatenate(vectors))
        faiss.write_index(index, str(destination))
        (base/'book_index/rag_metadata.json').write_text(json.dumps(rows), encoding='utf-8')
        print('12 real embedding indexes generated from sample text.')
    document = fitz.open()
    for title, subject, text in TOPICS[:6]:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50,50,545,790), title+'\n\n'+text, fontsize=14)
    target = ROOT/'local-data/sample-study-guide.pdf'
    target.parent.mkdir(exist_ok=True)
    document.save(target); document.close()
    print('Upload sample:', target)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', action='store_true')
    parser.add_argument('--email')
    args = parser.parse_args()
    if args.email and not os.environ.get('LUMINAR_LOCAL_PASSWORD'):
        parser.error('--email requires LUMINAR_LOCAL_PASSWORD in the environment')
    seed(args.email, os.environ.get('LUMINAR_LOCAL_PASSWORD'))
    if args.assets:
        assets()
