// API traffic is intercepted; no requests can create or edit live accounts.
const { chromium } = require(process.env.LUMINAR_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.LUMINAR_TEST_BASE || 'http://127.0.0.1:5173';
const out = process.env.LUMINAR_TEST_OUTPUT || path.resolve('test-results/staff-auth');
fs.mkdirSync(out, { recursive:true });
const results=[];
const account=role=>({user_id:role==='ADMIN'?1:role==='LIBRARIAN'?2:3,name:role+' Tester',email:role.toLowerCase()+'@example.com',role,is_email_verified:true,is_active:true,created_at:'2026-09-01T00:00:00Z'});
const book={book_id:1,work_id:'OL1W',title:'Test catalogue book',authors:'Test author',subjects:'Fiction',total_copies:3,available_copies:2,average_rating:4,rating_count:2,reading_log_count:1,readable:true,rag_available:true};

(async()=>{
 const browser=await chromium.launch({headless:true});
 async function test(name,role,run,options={}) {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  let currentRole=role;
  let staff=[account('ADMIN'),account('LIBRARIAN')];
  const calls=[],errors=[];
  if(role) await context.addInitScript(({user,storedRole})=>{
   localStorage.setItem('luminar_token','test-session');
   localStorage.setItem('luminar_user',JSON.stringify({...user,role:storedRole||user.role}));
  },{user:account(role),storedRole:options.storedRole});
  await context.route(url=>url.origin===base && /^\/(api|search-api|rag-api|recommendation-api)\//.test(url.pathname),async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   calls.push({path:p,method:req.method(),body:req.postData()});
   const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
   if(p==='/api/auth/login'||p==='/api/auth/staff-login') {
    const body=req.postDataJSON(), role=body.email.toUpperCase().startsWith('ADMIN@')?'ADMIN':body.email.toUpperCase().startsWith('LIBRARIAN@')?'LIBRARIAN':'GENERAL_USER';
    if(body.password!=='test-only-password') return json({detail:'Invalid email or password'},401);
    if(p.endsWith('staff-login')&&role==='GENERAL_USER') return json({detail:'This account is not authorized for staff access.'},403);
    currentRole=role;return json({access_token:'test-session',token_type:'bearer',user:account(role)});
   }
   if(p==='/api/auth/staff-setup') return json({message:'Account setup completed.'});
   if(p.startsWith('/api/staff/')) {
    if(currentRole!=='ADMIN') return json({detail:'Insufficient permissions'},403);
    if(p==='/api/staff/'&&req.method()==='GET') return options.directoryError?json({detail:'Unavailable'},503):json({users:staff,count:staff.length,librarian_count:staff.filter(u=>u.role==='LIBRARIAN').length});
    if(p==='/api/staff/librarians') {
     const body=req.postDataJSON();assert.deepEqual(Object.keys(body).sort(),['email','name']);
     const user={...account('LIBRARIAN'),user_id:4,name:body.name,email:body.email,is_email_verified:false};staff.push(user);
     return json({user,verification_sent:true},201);
    }
    if(req.method()==='PATCH') {
     const id=Number(p.split('/').at(-1));staff=staff.map(u=>u.user_id===id?{...u,...req.postDataJSON()}:u);return json({user:staff.find(u=>u.user_id===id)});
    }
    return json({message:'Verification email sent.'});
   }
   if(p==='/api/books/categories') return json({categories:[],count:0});
   if(p==='/api/books/OL1W/read') return json({...book,authors:['Test author'],text:'Existing reader content.'});
   if(p==='/api/books/OL1W') return json(book);
   if(p==='/api/books/capabilities') return json({books:[book]});
   if(p.startsWith('/api/books/')) return json({results:[book],count:1});
   if(p.startsWith('/api/reading-list/')) return json({items:[],count:0});
   if(p.startsWith('/api/issues/')) return json({issues:[]});
   if(p.startsWith('/api/reservations/')) return json({reservations:[]});
   if(p.startsWith('/api/fines/')) return json({fines:[],total_unpaid:0});
   if(p.startsWith('/api/activity/')) return json({activities:[]});
   if(p.startsWith('/api/inventory/')) return json({results:[]});
   if(p==='/api/know-more/books') return json({books:[],count:0});
   if(p.startsWith('/search-api/')) return json({results:[book],count:1});
   if(p.startsWith('/recommendation-api/')) return json({recommendations:[],count:0});
   if(p.startsWith('/rag-api/')) return json({books:[],documents:[],count:0,status:'healthy'});
   return json({detail:'Unmapped isolated request'},404);
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  try {await run(page,calls);assert.deepEqual(errors,[]);results.push({name,status:'passed'});}
  catch(e){results.push({name,status:'failed',error:e.message});await page.screenshot({path:path.join(out,'failure-'+results.length+'.png'),fullPage:true});}
  console.log(name,results.at(-1).status,results.at(-1).error||'');await context.close();
 }
 async function noStaffLinks(p) {
  assert.equal(await p.locator('a[href="/staff/login"],a[href="/admin"],a[href="/librarian"],a[href="/staff/setup"]').count(),0);
  assert.equal(await p.getByText(/^(Staff Login|Admin Dashboard|Librarian Dashboard|Staff Management)$/i).count(),0);
 }
 for(const role of [null,'GENERAL_USER']) await test('Public desktop/mobile navigation '+(role||'guest'),role,async p=>{
  for(const route of ['/', '/catalog', ...(role?['/dashboard','/profile']:['/login','/signup'])]){
   await p.goto(base+route);await p.locator('h1').first().waitFor();await noStaffLinks(p);
  }
  await p.goto(base+'/catalog');await p.setViewportSize({width:390,height:844});
  await p.getByRole('button',{name:'Toggle menu'}).click();await noStaffLinks(p);
  await p.screenshot({path:path.join(out,(role?'reader':'public')+'-mobile.png'),fullPage:true});
 });
 for(const route of ['/admin','/librarian']) await test('Anonymous '+route+' uses staff portal',null,async p=>{await p.goto(base+route);await p.waitForURL('**/staff/login');});
 for(const role of ['GENERAL_USER','LIBRARIAN','ADMIN']) for(const route of ['/admin','/librarian']) await test('Route guard '+role+' '+route,role,async p=>{
  await p.goto(base+route);
  const destination=role==='GENERAL_USER'?'/profile':role==='LIBRARIAN'?'/librarian':route;
  await p.waitForURL(base+destination);await p.getByRole('heading',{name:destination==='/admin'?'Admin dashboard':destination==='/librarian'?'Librarian dashboard':'My Library',exact:true}).waitFor();
 });
 for(const role of ['GENERAL_USER','ADMIN','LIBRARIAN']) await test('Normal login redirect '+role,null,async p=>{
  await p.goto(base+'/login');await noStaffLinks(p);
  await p.getByLabel('Email Address').fill(account(role).email);await p.getByLabel('Password',{exact:true}).fill('test-only-password');
  await p.getByRole('button',{name:'Sign In',exact:true}).click();await p.waitForURL(base+(role==='ADMIN'?'/admin':role==='LIBRARIAN'?'/librarian':'/profile'));
 });
 for(const role of ['GENERAL_USER','ADMIN','LIBRARIAN']) await test('Staff login '+role,null,async(p,calls)=>{
  await p.goto(base+'/staff/login');
  assert.equal(await p.locator('input').count(),2);assert.equal(await p.getByText(/register|choose role|create staff/i).count(),0);
  await p.getByLabel('Email',{exact:true}).fill(account(role).email);await p.getByLabel('Password',{exact:true}).fill('test-only-password');await p.getByRole('button',{name:'Sign in',exact:true}).click();
  if(role==='GENERAL_USER') {await p.getByRole('alert').filter({hasText:'not authorized for staff access'}).waitFor();assert.equal(await p.evaluate(()=>localStorage.getItem('luminar_token')),null);}
  else await p.waitForURL(base+(role==='ADMIN'?'/admin':'/librarian'));
  const call=calls.find(c=>c.path==='/api/auth/staff-login');assert.deepEqual(Object.keys(JSON.parse(call.body)).sort(),['email','password']);
 });
 await test('Invalid staff credentials stay generic',null,async p=>{
  await p.goto(base+'/staff/login');await p.getByLabel('Email',{exact:true}).fill('unknown@example.com');await p.getByLabel('Password',{exact:true}).fill('wrong');await p.getByRole('button',{name:'Sign in',exact:true}).click();
  await p.getByRole('alert').filter({hasText:'Invalid email or password'}).waitFor();assert.equal(await p.getByLabel('Password',{exact:true}).inputValue(),'');
  await p.screenshot({path:path.join(out,'staff-login-desktop.png'),fullPage:true});await p.setViewportSize({width:390,height:844});await p.screenshot({path:path.join(out,'staff-login-mobile.png'),fullPage:true});
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 });
 await test('Admin invitation, edit, disable and resend','ADMIN',async(p,calls)=>{
  await p.goto(base+'/admin');await p.getByRole('button',{name:'Create Librarian',exact:true}).click();
  const dialog=p.getByRole('dialog');await dialog.getByLabel('Name',{exact:true}).fill('New librarian');await dialog.getByLabel('Email',{exact:true}).fill('new@example.com');assert.equal(await dialog.locator('input[type=password],select').count(),0);
  await dialog.getByRole('button',{name:'Create and send code'}).click();await dialog.waitFor({state:'hidden'});await p.getByText('New librarian',{exact:true}).waitFor();
  let row=p.getByRole('row').filter({hasText:'new@example.com'});await row.getByRole('button',{name:'Resend verification'}).click();await p.getByRole('status').filter({hasText:'Verification code sent'}).waitFor();
  await row.getByRole('button',{name:'Edit name'}).click();await dialog.getByLabel('Name',{exact:true}).fill('Renamed librarian');await dialog.getByRole('button',{name:'Save name'}).click();await dialog.waitFor({state:'hidden'});
  row=p.getByRole('row').filter({hasText:'new@example.com'});await row.getByRole('button',{name:'Disable',exact:true}).click();await dialog.getByRole('button',{name:'Confirm',exact:true}).click();await dialog.waitFor({state:'hidden'});await row.getByText('Disabled',{exact:true}).waitFor();
  assert(!calls.some(c=>c.method==='PATCH'&&JSON.parse(c.body).role));
  await p.screenshot({path:path.join(out,'staff-management-desktop.png'),fullPage:true});await p.setViewportSize({width:390,height:844});await p.screenshot({path:path.join(out,'staff-management-mobile.png'),fullPage:true});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 });
 await test('Directory errors are not empty staff lists','ADMIN',async p=>{await p.goto(base+'/admin');await p.getByRole('alert').filter({hasText:'server could not complete'}).waitFor();assert.equal(await p.getByText('No staff accounts found.').count(),0);},{directoryError:true});
 await test('Forged localStorage does not grant API access','GENERAL_USER',async p=>{await p.goto(base+'/admin');await p.getByRole('alert').filter({hasText:'Insufficient permissions'}).waitFor();assert.equal(await p.getByText('ADMIN Tester',{exact:true}).count(),0);},{storedRole:'ADMIN'});
 for(const role of ['ADMIN','LIBRARIAN','GENERAL_USER']) await test('Logout clears shared session '+role,role,async p=>{
  await p.goto(base+(role==='ADMIN'?'/admin':role==='LIBRARIAN'?'/librarian':'/profile'));
  await p.getByRole('button',{name:role+' Tester'}).click();await p.getByRole('button',{name:'Sign Out'}).click();
  await p.waitForURL('**/login');assert.deepEqual(await p.evaluate(()=>[localStorage.getItem('luminar_token'),localStorage.getItem('luminar_user')]),[null,null]);
 });
 await test('Invitation completion sends no role',null,async(p,calls)=>{
  await p.goto(base+'/staff/setup');await p.getByLabel('Email',{exact:true}).fill('new@example.com');await p.getByLabel('Verification code').fill('123456');await p.getByLabel('New password',{exact:true}).fill('test-only-password');await p.getByLabel('Confirm password').fill('test-only-password');await p.getByRole('button',{name:'Set password and verify'}).click();await p.getByText('Your account is ready.').waitFor();
  assert.deepEqual(Object.keys(JSON.parse(calls.find(c=>c.path==='/api/auth/staff-setup').body)).sort(),['email','otp','password']);
 });
 await test('Original feature requests remain available','GENERAL_USER',async(p,calls)=>{
  await p.goto(base+'/catalog');await p.locator('a[href="/book/OL1W"]').first().waitFor();
  const search=p.waitForResponse(r=>r.url().includes('/search-api/search'));await p.goto(base+'/search?q=fiction');await search;
  await p.goto(base+'/llm');await p.getByRole('heading').first().waitFor();
  await p.evaluate(async()=>{const api=await import('/src/lib/api.ts');await api.getRecommendations();await api.askRAG('A non-sensitive test','concise');});
  assert(calls.some(c=>c.path==='/recommendation-api/recommendations'));assert(calls.some(c=>c.path==='/rag-api/rag/ask'));
  await p.goto(base+'/book/OL1W/read');await p.getByText('Existing reader content.').waitFor();
 });
 await browser.close();fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify(results,null,2));console.log(`${results.filter(r=>r.status==='passed').length}/${results.length} passed`);if(results.some(r=>r.status==='failed'))process.exitCode=1;
})().catch(error=>{console.error(error.message);process.exitCode=1});
