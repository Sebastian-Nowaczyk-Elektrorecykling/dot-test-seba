/* Dependency-free controller/DOM test double; this is not a browser layout test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const cwd=path.resolve(__dirname, '..');
class Element {
  constructor(tag='div',text=''){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.events={};this.dataset={};this.className='';this._text=text;this.value='';this.disabled=false;this.hidden=false;this.parentElement=null;}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('')}
  set textContent(v){this._text=String(v);this.children=[]}
  append(...children){for(let child of children){if(typeof child==='string')child=new Element('#text',child);child.parentElement=this;this.children.push(child)}}
  prepend(child){child.parentElement=this;this.children.unshift(child)}
  replaceChildren(...children){this._text='';this.children=[];this.append(...children)}
  setAttribute(k,v){this.attributes[k]=String(v)}
  removeAttribute(k){delete this.attributes[k];delete this[k]}
  getAttribute(k){return this.attributes[k]}
  addEventListener(event,listener){(this.events[event]??=[]).push(listener)}
  dispatch(event){for(const listener of this.events[event]||[])listener({target:this,preventDefault(){}})}
  get firstElementChild(){return this.children[0]}
  get childElementCount(){return this.children.length}
  matches(s){return s.startsWith('.')?this.className.split(' ').includes(s.slice(1)):this.tagName===s.toUpperCase()}
  querySelectorAll(selector){const out=[];const sels=selector.split(',').map(s=>s.trim());for(const child of this.children){if(sels.some(s=>child.matches(s)))out.push(child);out.push(...child.querySelectorAll(selector))}return out}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null}
  closest(selector){for(let current=this;current;current=current.parentElement)if(current.matches(selector))return current;return null}
  focus(){} scrollIntoView(){} reportValidity(){return true}
}
const html=fs.readFileSync(cwd+'/gus_app/static/index.html','utf8');
const elements={};for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)){const el=new Element(m[1]);el.id=m[2];elements[el.id]=el}
const modeButtons=['variables','units','data'].map(mode=>{const el=new Element('button');el.dataset.mode=mode;return el});
const exampleButtons=['population','unemployment','warsaw'].map(example=>{const el=new Element('button');el.dataset.example=example;return el});
const allButtons=[...modeButtons,...exampleButtons];
const document={getElementById:id=>elements[id],createElement:tag=>new Element(tag),createTextNode:text=>new Element('#text',text),querySelectorAll:s=>s==='[data-mode]'?modeButtons:s==='[data-example]'?exampleButtons:allButtons};
const catalog=JSON.parse(execFileSync('python3',['-c','import json; from gus_app.catalog import CATALOG; print(json.dumps(CATALOG))'],{cwd}));
let calls=[];let responseData={results:[],totalRecords:0};let source='https://bdl.stat.gov.pl/api/v1/variables/search';let pending=[];let defer=false;
const fetch=async (url,opts)=>{calls.push({url,opts});if(url==='/api/catalog')return {ok:true,json:async()=>catalog};if(defer)return new Promise(resolve=>pending.push(resolve));return {ok:true,json:async()=>({data:responseData,source})}};
const sandbox={document,fetch,URL,URLSearchParams,AbortController,Intl,console,Option:function(text,value){const el=new Element('option',text);el.value=value;return el}};
vm.runInNewContext(fs.readFileSync(cwd+'/gus_app/static/app.js','utf8'),sandbox);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const input=name=>elements.parameters.querySelectorAll('input, select').find(el=>el.name===name);
const submit=()=>elements['query-form'].dispatch('submit');
(async()=>{
 await tick();assert.equal(elements.endpoint.value,'/variables/search');assert.equal(input('page').value,'0');assert.equal(input('page-size').value,'20');
 assert.equal(elements.parameters.querySelectorAll('input, select').length,catalog.endpoints.find(e=>e.id==='/variables/search').parameters.length);
 input('name').value='ludność';input('year').value='2022, 2023;2024';
 responseData=JSON.parse('{"results":[{"id":123,"name":"<img src=x onerror=alert(1)>","zero":0,"null":null,"false":false,"future_field":[{"deep":[null,false,0,"x"]}],"__proto__":"safe"}],"totalRecords":41,"metadata":{"unknown":"preserved"},"links":{"next":"https://evil.example/never-fetch"}}');
 submit();await tick();
 const url=new URL(calls.at(-1).url,'http://localhost');assert.deepEqual(url.searchParams.getAll('year'),['2022','2023','2024']);assert.equal(url.searchParams.get('page'),'0');
 const text=elements['results-content'].textContent;
 for(const literal of ['<img src=x onerror=alert(1)>','Brak wartości (null)','Nie (false)','future_field','safe','preserved'])assert(text.includes(literal),literal);
 assert.equal(elements['results-content'].querySelectorAll('img').length,0);
 assert.equal(elements['previous-page'].disabled,true);assert.equal(elements['next-page'].disabled,false);assert.equal(elements['page-label'].textContent,'Strona 1 z 3');
 elements['next-page'].dispatch('click');await tick();assert.equal(new URL(calls.at(-1).url,'http://localhost').searchParams.get('page'),'1');assert.equal(elements['previous-page'].disabled,false);
 input('name').value='inne';input('name').dispatch('input');assert.equal(elements['next-page'].disabled,true);
 source='https://stat.gov.pl.evil.example/no';submit();await tick();assert.equal(elements['source-link'].hidden,true);
 elements['clear-button'].dispatch('click');assert.equal(input('name').value,'');assert.equal(elements['empty-state'].hidden,false);
 input('page-size').value='';responseData={results:[{id:0}],totalRecords:11};submit();await tick();assert.equal(elements['page-label'].textContent,'Strona 1 z 2');assert.equal(elements['next-page'].disabled,false);
 // No navigation fetch ever uses a URL received from a result.
 assert(calls.every(c=>c.url==='/api/catalog'||c.url.startsWith('/api/query?')));
 // Errors are displayed as text; retry retains the exact previous query.
 const goodFetch=sandbox.fetch;
 sandbox.fetch=async()=>({ok:false,status:429,json:async()=>({error:'Limit <script> bez wykonania'})});
 submit();await tick();assert.equal(elements['error-box'].hidden,false);assert(elements['error-message'].textContent.includes('<script>'));
 sandbox.fetch=goodFetch;responseData={results:[],totalRecords:0};elements['retry-button'].dispatch('click');await tick();assert.equal(elements['error-box'].hidden,true);assert.equal(elements['no-results'].hidden,false);
 // Ignore stale responses after changing endpoint, even if transport ignores abort.
 defer=true;submit();await tick();assert.equal(elements['search-button'].disabled,true);
 modeButtons[1].dispatch('click');assert.equal(elements.endpoint.value,'/units/search');
 pending.shift()({ok:true,json:async()=>({data:{results:[{name:'OBSOLETE'}]},source})});await tick();assert(!elements['results-content'].textContent.includes('OBSOLETE'));
 // Newer repeated example wins. Abort safety does not depend on the server cancelling.
 exampleButtons[0].dispatch('click');await tick();assert.equal(elements.endpoint.value,'/subjects/search');assert.equal(input('name').placeholder,'np. ludność…');exampleButtons[2].dispatch('click');await tick();
 pending[1]({ok:true,json:async()=>({data:{results:[{id:'000000001',name:'NEWEST'}]},source:'https://bdl.stat.gov.pl/api/v1/units/search'})});await tick();
 pending[0]({ok:true,json:async()=>({data:{results:[{name:'STALE'}]},source})});await tick();
 assert(elements['results-content'].textContent.includes('NEWEST'));assert(!elements['results-content'].textContent.includes('STALE'));
 const dataButton=elements['results-content'].querySelectorAll('button').find(b=>b.textContent==='Zobacz dane →');dataButton.dispatch('click');assert.equal(input('unit-id').value,'000000001');assert.equal(elements.endpoint.value,'/data/by-unit/{unit-id}');
 // Cancel interrupts loading and ignores any eventual result.
 submit();await tick();elements['cancel-button'].dispatch('click');assert.equal(elements['loading-state'].hidden,true);assert.equal(elements['search-button'].disabled,false);
 pending.at(-1)({ok:true,json:async()=>({data:{results:[{name:'CANCELLED'}]},source})});await tick();assert(!elements['results-content'].textContent.includes('CANCELLED'));
 console.log('PASS: dynamic catalog, all parameters, repeated arrays, null/false/zero/unknown/nested content, XSS-safe text, trusted source, zero-based/default-size pagination, stale requests, repeated examples, subject labels, 429/retry, empty response, cancel, clear and drill-down identifiers.');
})().catch(error=>{console.error(error);process.exitCode=1});
