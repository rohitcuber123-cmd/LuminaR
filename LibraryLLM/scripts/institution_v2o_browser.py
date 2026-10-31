"""Real Chromium + authenticated Mongo + actual routes/native encoder, owned only."""
import os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2o_fixture import AuthMongo,provision_application


def main():
    with AuthMongo() as server:
        provision_application(server)
        os.environ.update(LUMINAR_MONGO_MODE='AUTHENTICATED',MONGO_URI=server.app_uri,MONGO_DB_NAME=server.database,
                          LUMINAR_SESSION_DB=str(server.root/'sessions.sqlite'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        with (ROOT/'reports/institution_v2o_vite.log').open('w') as log:
            vite=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(port),'--strictPort'],cwd=ROOT/'frontend',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                for _ in range(100):
                    with socket.socket() as sock:
                        if sock.connect_ex(('127.0.0.1',port))==0:break
                    time.sleep(.1)
                source=(ROOT/'scripts/institution_v2i_browser.py').read_text(encoding='utf8')
                source=source.replace("DBNAME = 'luminar_institution_v2i_browser_' + uuid4().hex[:24]", 'DBNAME = os.environ["MONGO_DB_NAME"]')
                source=source.replace("MONGO_URI='mongodb://127.0.0.1:27017'", 'MONGO_URI=os.environ["MONGO_URI"]')
                source=source.replace('from tests.institution_v2g.test_intelligence import encoder', '''from sentence_transformers import SentenceTransformer
import torch
torch.set_num_threads(2)
cache=Path.home()/'.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2'
revision=(cache/'refs/main').read_text().strip()
model=SentenceTransformer(str(cache/'snapshots'/revision),device='cpu',local_files_only=True)
def encoder(texts):return model.encode(texts,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)''')
                source=source.replace('from backend.utils.jwt_utils import create_access_token','from backend.utils.jwt_utils import create_access_token\nfrom backend.services.auth_service import hash_password')
                source=source.replace("'role': 'GENERAL_USER', 'is_active': True, 'is_email_verified': True}", "'role':'GENERAL_USER','is_active':True,'is_email_verified':True,'password_hash':hash_password('Owned browser passphrase')}")
                source=source.replace("BASE = 'http://127.0.0.1:5189'", f"BASE = 'http://127.0.0.1:{port}'")
                source=source.replace("url.netloc != '127.0.0.1:5189'", f"url.netloc != '127.0.0.1:{port}'")
                source=source.replace("'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'", "'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE','access_code':'Owned private fixture code'")
                source=source.replace('[(1440,1000),(1024,768),(390,844),(375,812)]','[(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]')
                source=source.replace("mongo.drop_database(DBNAME)", 'mongo.close() # Parent owns server directory cleanup; app has no drop right.')
                source=source.replace("DBNAME.startswith('luminar_institution_v2i_browser_')", "DBNAME.startswith('luminar_v2o_fixture_')")
                source=source.replace("page.route('**/*', route_request)", "page.route('**/*', route_request)\n                    page._fixture_route = route_request")
                source=source.replace('institution_v2i','institution_v2o').replace('luminar-v2i-browser-','luminar-v2o-browser-')
                for label in ['Queued','Needs recovery']:
                    source=source.replace(f"get_by_text('{label}', exact=True)",f"get_by_text('{label}', exact=True).first")
                marker="                passed('Focused axe accessibility: no violations')"
                extension='''
                admin.set_viewport_size({'width':1440,'height':900})
                open_intelligence(admin,a)
                admin.get_by_role('button',name='Open account menu for',exact=False).click()
                admin.get_by_role('menuitem',name='Sign Out',exact=True).click()
                expect(admin.get_by_role('heading',name='Semantic Search Index',exact=True)).not_to_be_visible()
                admin.wait_for_url(lambda url:urlsplit(url).path=='/login',timeout=30000)
                # A clean browser context has no fixture token-init script. All
                # credentials/session state now come from the real Staff form.
                login_context=browser.new_context(viewport={'width':1440,'height':900});contexts.append(login_context)
                signed_in=login_context.new_page();signed_in.route('**/*',admin._fixture_route)
                signed_in.goto(BASE+'/staff/login')
                signed_in.get_by_label('Email',exact=True).fill('v2i-1@example.com')
                signed_in.get_by_label('Password',exact=True).fill('Owned browser passphrase')
                signed_in.get_by_role('button',name='Sign in',exact=True).click()
                signed_in.wait_for_url(lambda url:'/staff/login' not in url,timeout=30000)
                open_intelligence(signed_in,a)
                passed('Real browser logout and Staff password relogin restore fresh authorized status')
'''
                source=source.replace(marker,marker+'\n'+extension)
                source=source.replace('intelligence_'+"{width}.png", 'intelligence_'+"{width}.png")
                exec(compile(source,str(ROOT/'scripts/institution_v2i_browser.py'),'exec'),{'__file__':str(ROOT/'scripts/institution_v2i_browser.py'),'__name__':'__main__'})
            finally:
                vite.terminate();vite.wait(timeout=15)


if __name__=='__main__':main()
