// Independent Part 3 acceptance probes; mock HTTP, no real-user mutations.
import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
localStorage.setItem('luminar_token', 'fixture-session')
localStorage.setItem('luminar_user', JSON.stringify({email:'fixture@test.invalid',role:'GENERAL_USER'}))
const { render, screen, fireEvent, cleanup, act, waitFor } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { AIChatWidget } = await import('../src/components/AIChatWidget.tsx')
const { AssistantTurn } = await import('../src/components/assistant/AssistantTurn.tsx')
const { useAssistantStore: store } = await import('../src/store/useAssistantStore.ts')
const { useAuthStore } = await import('../src/store/useAuthStore.ts')
const { default: axe } = await import('axe-core')
const book = (id='OL1W') => ({work_id:id,title:`Fixture ${id}`,authors:'Fixture Author',subjects:['Science'],average_rating:null,available_copies:1,total_copies:1,shelf_location:null,description:null})
const response = (patch={}) => ({conversation_id:'fixture-conversation',intent:'GENERAL_LIBRARY_HELP',message:'Fixture response',books:[],comparison:null,recommendation_mode:null,seed_work_ids:[],availability:[],actions:[],clarification:null,pending_action:null,account:null,reading_list:null,rag:null,errors:[],has_more:false,result_offset:0,explanation_available:false,...patch})
let calls: any[] = [], next: any = response(), originalFetch: typeof fetch
beforeEach(() => {
  act(() => {
    store.setState({owner:'fixture@test.invalid',selected:[],conversationId:null,messages:[],recent:[],open:false,busy:false,startedAt:null,selectionNotice:'',pageContext:{},pagePath:''})
    useAuthStore.setState({isAuthenticated:true,token:'fixture-session',user:{email:'fixture@test.invalid',role:'GENERAL_USER'}})
  })
  calls=[]; next=response(); originalFetch=globalThis.fetch
  globalThis.fetch=async (_url,options={}) => { calls.push(JSON.parse(String(options.body))); return new Response(JSON.stringify(next),{status:200,headers:{'Content-Type':'application/json'}}) }
})
afterEach(() => {cleanup();globalThis.fetch=originalFetch})
async function mountResult(data:any) {
  next=data; render(<MemoryRouter><AIChatWidget/></MemoryRouter>)
  fireEvent.click(screen.getByRole('button',{name:'Open LuminaR AI'}))
  fireEvent.change(screen.getByLabelText('Message LuminaR AI'),{target:{value:'Fixture query'}})
  fireEvent.click(screen.getByRole('button',{name:'Send message'}))
  await waitFor(() => assert.equal(store.getState().busy,false))
}
test('recommendation explanation button sends the explain API action',async () => {
  await act(async () => {store.getState().select(book())})
  await mountResult(response({intent:'RECOMMEND_FROM_BOOK',books:[book('OL2W')],seed_work_ids:['OL1W'],recommendation_mode:'SINGLE_SELECTED_BOOK',explanation_available:true}))
  next=response();fireEvent.click(screen.getByRole('button',{name:'Why these recommendations?'}))
  await waitFor(() => assert.equal(store.getState().busy,false))
  assert.equal(calls.at(-1).action,'EXPLAIN_RECOMMENDATION')
})
test('comparison explanation button issues a request',async () => {
  await mountResult(response({intent:'COMPARE_BOOKS',comparison:{books:[book(),book('OL2W')],requested_fields:[],missing_fields:[]},explanation_available:true}))
  next=response();fireEvent.click(screen.getByRole('button',{name:/Explain comparison/}))
  await act(async () => {})
  assert.equal(calls.length,2)
  assert.equal(calls.at(-1).action,'EXPLAIN_COMPARISON')
})
test('search pagination retains the original query and uses a supported action',async () => {
  await mountResult(response({intent:'SEARCH_BOOKS',books:[book()],has_more:true}))
  next=response();fireEvent.click(screen.getByRole('button',{name:'Show more results'}))
  await waitFor(() => assert.equal(store.getState().busy,false))
  assert.notEqual(calls.at(-1).action,'SEARCH_BOOKS')
  assert.equal(calls.at(-1).message,'Fixture query')
})
test('reading-list remove button binds its card ID',async () => {
  await mountResult(response({intent:'USER_READING_LIST',reading_list:[book()]}))
  next=response();fireEvent.click(screen.getByRole('button',{name:/Remove Fixture OL1W from reading list/}))
  await waitFor(() => assert.equal(store.getState().busy,false))
  assert.equal(calls.at(-1).action,'REMOVE_FROM_READING_LIST')
  assert.deepEqual(calls.at(-1).selected_work_ids,['OL1W'])
})
test('Part 3 reading-list and explanation controls pass axe semantic checks',async () => {
  await mountResult(response({intent:'USER_READING_LIST',reading_list:[book()]}))
  const result=await axe.run(screen.getByRole('dialog'),{rules:{'color-contrast':{enabled:false}}})
  assert.deepEqual(result.violations.map(v=>v.id),[])
})
