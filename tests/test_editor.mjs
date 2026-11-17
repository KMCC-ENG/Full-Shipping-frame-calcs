// DOM-level sketcher tests. Node/jsdom are development tools, not app requirements.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {JSDOM}=require('jsdom');
const here=path.dirname(fileURLToPath(import.meta.url));
const assets=path.join(here,'../assets');
const dom=new JSDOM(fs.readFileSync(path.join(assets,'section_editor.html'),'utf8'));
globalThis.document=dom.window.document;
const style=document.createElement('style');style.textContent=fs.readFileSync(path.join(assets,'section_editor.css'),'utf8');document.head.append(style);document.body.style.colorScheme='dark';
const root=document.querySelector('.sf-editor'),svg=root.querySelector('svg');
Object.defineProperty(svg,'clientWidth',{value:1000});
Object.defineProperty(svg,'viewBox',{get(){let [x,y,width,height]=svg.getAttribute('viewBox').split(/\s+/).map(Number);return {baseVal:{x,y,width,height}};}});
const source=fs.readFileSync(path.join(assets,'section_editor.js'),'utf8');
const mount=(await import('data:text/javascript,'+encodeURIComponent(source))).default;
let sent=[];
const send=(name,payload)=>sent.push({name,payload});
mount({parentElement:document.body,data:{beam:'B1',revision:4,shapes:[]},setStateValue:send});
assert.equal(root._sf.shapes.length,0);assert.equal(root.querySelectorAll('.sf-shapes path').length,0);
assert.equal(dom.window.getComputedStyle(root.querySelector('.sf-z')).backgroundColor,'rgb(255, 255, 255)');
assert.equal(dom.window.getComputedStyle(root.querySelector('.sf-z')).color,'rgb(24, 51, 75)');
for(const name of ['z','y','w','h','r','grid-step','dimension-value'])assert.equal(root.querySelector('.sf-'+name).step,'0.5');
const field=(selector,value)=>root.querySelector(selector).value=String(value);
const click=selector=>root.querySelector(selector).click();
const shape=()=>root._sf.shapes.at(-1);
const tool=name=>click(`[data-tool="${name}"]`);
const act=name=>click(`[data-act="${name}"]`);
field('.sf-w',.375);click('[data-step-for="sf-w"][data-step-sign="+"]');assert.equal(root.querySelector('.sf-w').value,'0.875');click('[data-step-for="sf-w"][data-step-sign="-"]');assert.equal(root.querySelector('.sf-w').value,'0.375');
field('.sf-y',5.3);click('[data-step-for="sf-y"][data-step-sign="+"]');assert.equal(root.querySelector('.sf-y').value,'5.8');
tool('rectangle');field('.sf-z',0);field('.sf-y',0);field('.sf-w',4);field('.sf-h',3);act('numeric');
assert.equal(shape().w,4);assert.equal(shape().h,3);assert.equal(sent.at(-1).payload.revision,4);
tool('circle');field('.sf-z',2);field('.sf-y',1.5);field('.sf-r',.5);field('.sf-op','subtract');act('numeric');
assert.equal(shape().op,'subtract');assert.equal(shape().r,.5);
act('undo');assert.equal(root._sf.shapes.length,1);act('redo');assert.equal(root._sf.shapes.length,2);
tool('rectangle');field('.sf-op','add');field('.sf-z',5);field('.sf-y',0);field('.sf-w',2);field('.sf-h',1);act('numeric');
act('rotate');assert.equal(shape().rotation,90);act('mirror');assert.equal(shape().mirror,true);
act('copy');assert.equal(root._sf.shapes.length,4);assert.equal(shape().x,5.125);
act('delete');assert.equal(root._sf.shapes.length,3);
tool('rectangle');field('.sf-z',0);field('.sf-y',5);field('.sf-w',3);field('.sf-h',2);act('numeric');
field('.sf-r',.25);act('fillet');assert.equal(shape().radius,.25);
tool('line');
for (let [x,y] of [[0,0],[2,0],[2,2],[0,2]]) {field('.sf-z',x);field('.sf-y',y);act('vertex');}
act('close');assert.equal(shape().type,'polygon');assert.equal(shape().points.length,4);
field('.sf-corner',1);field('.sf-r',1.5);act('arc-edge');assert.equal(shape().arcs[0].r,1.5);
act('reverse-arc');assert.equal(shape().arcs[0].clockwise,true);
tool('line');for(let [x,y] of [[6,0],[8,0],[8,2],[6,2]]){field('.sf-z',x);field('.sf-y',y);act('vertex');}act('close');
field('.sf-r',.2);act('fillet');assert.ok(shape().points.length>4);
tool('arc');field('.sf-z',10);field('.sf-y',0);field('.sf-r',2);field('.sf-a0',0);field('.sf-a1',90);act('numeric');
assert.equal(shape().type,'arc');assert.equal(shape().a1,90);
// The mount must retain local tools/history on Streamlit redraws, and replace
// geometry only for a new design revision/beam.
const count=root._sf.shapes.length;
mount({parentElement:document.body,data:{beam:'B1',revision:4,shapes:[]},setStateValue:send});assert.equal(root._sf.shapes.length,count);
mount({parentElement:document.body,data:{beam:'B1',revision:5,shapes:[]},setStateValue:send});assert.equal(root._sf.shapes.length,0);
assert.equal(root.querySelector('pattern').getAttribute('width'),'0.125');
assert.equal(sent.length,17);
// Mock only the SVG viewport transforms that jsdom does not implement. The
// actual pointer, snap, ortho, selection, drag, pan and zoom handlers run below.
svg.createSVGPoint=()=>({x:0,y:0,matrixTransform(m){return {x:this.x*m.a+m.e,y:this.y*m.d+m.f};}});
svg.getScreenCTM=()=>({inverse(){const v=svg.viewBox.baseVal;return {a:v.width/1000,d:v.height/400,e:v.x,f:v.y};}});
svg.setPointerCapture=()=>{};
const screen=([z,y])=>{const v=svg.viewBox.baseVal;return {clientX:(z-v.x)/v.width*1000,clientY:(-y-v.y)/v.height*400};};
const point=(kind,p,target=svg)=>svg['onpointer'+kind]({button:0,pointerId:1,target,...screen(p)});
tool('rectangle');point('down',[0,0]);point('move',[2,1]);point('up',[2,1]);
assert.equal(shape().w,2);assert.equal(shape().h,1);
tool('select');const outline=root.querySelector(`path[data-id="${shape().id}"]`);
point('down',[1,.5],outline);point('move',[1.5,.75]);point('up',[1.5,.75]);
assert.equal(shape().x,.5);assert.equal(shape().y,.25);
tool('line');root.querySelector('.sf-ortho').checked=true;point('down',[0,0]);point('down',[1.1,.3]);
assert.ok(Math.abs(root._sf.draft[1][1])<1e-12);point('down',[1.1,1.1]);act('close');assert.equal(shape().type,'polygon');
tool('circle');point('down',[5,5]);point('move',[6,5]);point('up',[6,5]);assert.equal(shape().r,1);
tool('pan');const oldX=svg.viewBox.baseVal.x;
svg.onpointerdown({button:0,pointerId:1,target:svg,clientX:300,clientY:100});
svg.onpointermove({clientX:360,clientY:150});svg.onpointerup({});assert.notEqual(svg.viewBox.baseVal.x,oldX);
const oldWidth=svg.viewBox.baseVal.width;svg.onwheel({clientX:300,clientY:100,deltaY:-1,preventDefault(){}});assert.ok(svg.viewBox.baseVal.width<oldWidth);
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} differs from ${b}`);
function dimension(selector,value){
 const button=root.querySelector(selector);assert.ok(button,selector+' dimension missing');button.click();
 assert.equal(root.querySelector('.sf-dimension-edit').hidden,false);
 field('.sf-dimension-value',value);root.querySelector('.sf-dimension-value').onkeydown({key:'Enter',preventDefault(){},stopPropagation(){}});
 assert.equal(root.querySelector('.sf-dimension-edit').hidden,true);
}
act('clear');tool('rectangle');field('.sf-op','add');field('.sf-z',0);field('.sf-y',0);field('.sf-w',4);field('.sf-h',3);act('numeric');
dimension('[data-dim-kind="w"]',6.25);near(shape().w,6.25);near(shape().x,0);
dimension('[data-dim-kind="h"]',3.125);near(shape().h,3.125);
act('undo');near(shape().h,3);act('redo');near(shape().h,3.125);
tool('circle');field('.sf-z',10);field('.sf-y',10);field('.sf-r',2);act('numeric');dimension('[data-dim-kind="r"]',3.125);near(shape().r,3.125);near(shape().x,10);near(shape().y,10);
tool('arc');field('.sf-z',20);field('.sf-y',5);field('.sf-r',2);field('.sf-a0',0);field('.sf-a1',90);act('numeric');dimension('[data-dim-kind="r"]',4.25);near(shape().r,4.25);
// Enter a live segment dimension before placing the endpoint. Exact values
// override the grid; editing an existing edge keeps its start point fixed.
act('clear');tool('line');point('down',[0,0]);point('move',[3,0]);
assert.ok(root.querySelector('[data-dim-source="live"]').textContent.includes('3'));
dimension('[data-dim-source="live"]',5.3);near(root._sf.draft[1][0],5.3);near(root._sf.draft[1][1],0);
dimension('[data-dim-source="draft"]',4.125);near(root._sf.draft[1][0],4.125);
point('down',[4.125,2]);act('close');dimension('[data-dim-source="shape"][data-edge="0"]',6.75);
near(shape().points[0][0],0);near(shape().points[1][0],6.75);
act('rotate');act('mirror');
const displayed=()=>root.querySelector(`path[data-id="${shape().id}"]`).getAttribute('d').slice(1,-1).split('L').map(s=>s.split(',').map(Number)).map(([x,y])=>[x,-y]);
const before=displayed();dimension('[data-dim-source="shape"][data-edge="0"]',2.125);const after=displayed();
near(after[0][0],before[0][0]);near(after[0][1],before[0][1]);near(Math.hypot(after[1][0]-after[0][0],after[1][1]-after[0][1]),2.125);
// Curved-edge radius labels remain editable, and invalid dimensions cannot
// replace the material model.
field('.sf-corner',1);field('.sf-r',2);act('arc-edge');dimension('[data-dim-kind="r"][data-edge="0"]',3);near(shape().arcs[0].r,3);
const prior=JSON.stringify(root._sf.shapes);root.querySelector('[data-dim-kind="r"][data-edge="0"]').click();field('.sf-dimension-value',.01);root.querySelector('[data-dimension="apply"]').click();assert.equal(JSON.stringify(root._sf.shapes),prior);root.querySelector('[data-dimension="cancel"]').click();
// A dimensioned plate with a central circular hole is round-tripped through
// the Python section calculator by the optional verification harness.
act('clear');tool('rectangle');field('.sf-op','add');field('.sf-z',0);field('.sf-y',0);field('.sf-w',4);field('.sf-h',3);act('numeric');dimension('[data-dim-kind="w"]',5.5);dimension('[data-dim-kind="h"]',3.25);
tool('circle');field('.sf-op','subtract');field('.sf-z',2.75);field('.sf-y',1.625);field('.sf-r',.5);act('numeric');dimension('[data-dim-kind="r"]',.625);
const kept=JSON.stringify(root._sf.shapes);act('close-panel');assert.equal(sent.at(-1).payload.close,true);assert.equal(JSON.stringify(sent.at(-1).payload.shapes),kept);
if(process.env.SF_EDITOR_QA_OUT)fs.writeFileSync(process.env.SF_EDITOR_QA_OUT,JSON.stringify(sent.at(-1).payload));
root._sf=null;mount({parentElement:document.body,data:{beam:'B2',color:'#168063',revision:5,shapes:JSON.parse(kept)},setStateValue:send});
assert.equal(JSON.stringify(root._sf.shapes),kept);assert.equal(root.querySelector('.sf-shapes path').getAttribute('stroke'),'#168063');
// Home unmounts the component. Recreate its DOM to exercise a real remount
// rather than keeping input nodes alive between views.
function mountDraft(viewId) {
 const host=document.createElement('div');
 host.innerHTML=fs.readFileSync(path.join(assets,'section_editor.html'),'utf8');
 document.body.append(host);
 const canvas=host.querySelector('svg');
 Object.defineProperty(canvas,'viewBox',{get(){
  const [x,y,width,height]=canvas.getAttribute('viewBox').split(/\s+/).map(Number);
  return {baseVal:{x,y,width,height}};
 }});
 const unmount=mount({parentElement:host,data:{beam:'B1',revision:6,view_id:viewId,shapes:[]},setStateValue:send});
 return {host,unmount};
}
let visit=mountDraft('design-one');
visit.host.querySelector('[data-tool="line"]').click();
visit.host.querySelector('.sf-z').value='1.75';
visit.host.querySelector('[data-act="vertex"]').click();
visit.host.querySelector('.sf-y').value='2.25';
visit.host.querySelector('[data-act="vertex"]').click();
visit.host.querySelector('.sf-w').value='7.375';
visit.unmount();
visit.host.remove();
visit=mountDraft('design-one');
assert.equal(visit.host.querySelector('.sf-w').value,'7.375');
assert.equal(visit.host.querySelector('.sf-y').value,'2.25');
assert.equal(visit.host.querySelectorAll('.sf-draft circle').length,2);
assert.ok(visit.host.querySelector('[data-tool="line"]').classList.contains('active'));
visit.unmount();
visit.host.remove();
visit=mountDraft('new-design-with-reused-beam-id');
assert.equal(visit.host.querySelector('.sf-w').value,'3');
assert.equal(visit.host.querySelectorAll('.sf-draft circle').length,0);
visit.unmount();
visit.host.remove();
console.log('Sketcher checks passed, including draft and field persistence across Home and isolation for a new design.');
