/* Offline JavaScript behavior checks. This does not replace browser visual QA. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, 'docs/reports', name), 'utf8');
const scripts = html => [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
const element = (value = '') => ({ value, innerHTML: '', textContent: '', addEventListener() {} });
const matrix = read('comparison_matrix.html');
const rows = [...matrix.matchAll(/<tr data-persona="([^"]+)" data-status="([^"]+)">([\s\S]*?)<\/tr>/g)].map(m => ({dataset:{persona:m[1],status:m[2]}, textContent:m[3].replace(/<[^>]*>/g, ''), hidden:false}));
const elements = {query:element(),persona:element(),status:element(),count:element()};
const context = vm.createContext({document:{querySelectorAll:()=>rows,querySelector:s=>elements[s.slice(1)],getElementById:id=>elements[id]}});
vm.runInContext(scripts(matrix).at(-1)[1],context);
assert.equal(rows.filter(r=>!r.hidden).length,96);
elements.persona.value='quick_lookup';vm.runInContext('filter()',context);assert.equal(rows.filter(r=>!r.hidden).length,24);
elements.query.value='EV012';vm.runInContext('filter()',context);assert.equal(rows.filter(r=>!r.hidden).length,1);
elements.query.value='no_such_task';vm.runInContext('filter()',context);assert.equal(rows.filter(r=>!r.hidden).length,0);
const scenarios = read('scenario_recommendations.html');
const dataText = scenarios.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const data=JSON.parse(dataText);const controls={data:{textContent:dataText},persona:element('all'),scenario:element('all'),cards:element()};
const cx=vm.createContext({document:{getElementById:id=>controls[id]}});vm.runInContext(scripts(scenarios).at(-1)[1],cx);
const cardCount=()=>[...controls.cards.innerHTML.matchAll(/<section class="card /g)].length;
assert.equal(cardCount(),6);
for(const persona of Object.keys(data.views)){
 controls.persona.value=persona;vm.runInContext('render()',cx);assert.equal(cardCount(),6);
 assert.equal(new Set(data.views[persona].flatMap(c=>c.tasks.map(t=>t.task_id))).size,24);
}
controls.scenario.value='incident';vm.runInContext('render()',cx);assert.equal(cardCount(),1);
assert.equal(data.views.quick_lookup.flatMap(c=>c.tasks).find(t=>t.task_id==='EV001').decision.code,'both');
assert.equal(data.views.source_checker.flatMap(c=>c.tasks).find(t=>t.task_id==='EV001').decision.code,'coze_app');
assert.equal(data.views.all.flatMap(c=>c.tasks).find(t=>t.task_id==='EV018').decision.code,'shared_gap');
console.log('Report UI behavior passed: 96-row filtering; 6 scenarios; 5 Persona views; evidence-based decisions.');
