/* Captured game imagery with live, engine-calibrated positions. No network assets. */
function createResidentMedia(manifest,base='media/'){
 const ns='http://www.w3.org/2000/svg',map=manifest?.map,maps=new WeakMap();
 const validFile=name=>typeof name==='string'&&/^[a-z0-9-]+\.(png|jpg)$/.test(name);
 function node(tag,attrs={}){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n;}
 function point(position,space){
  if(!map||!position?.every(Number.isFinite)||position.length!==3)return null;
  if(!space||space.interior||space.world!==map.space.world)return null;
  const {world:w,screen:s,camera:c}=map.projection;
  const dx=(position[0]-w[0][0])/(w[1][0]-w[0][0]),dy=(position[1]-w[0][1])/(w[2][1]-w[0][1]);
  const depth=c[2]-position[2];if(depth<=0)return null;
  const ratio=(c[2]-w[0][2])/depth;
  const x=.5+(s[0][0]+dx*(s[1][0]-s[0][0])+dy*(s[2][0]-s[0][0])-.5)*ratio;
  const y=.5+(s[0][1]+dx*(s[1][1]-s[0][1])+dy*(s[2][1]-s[0][1])-.5)*ratio;
  const [vx,vy,vw,vh]=map.viewport,p=[vx+x*vw,vy+(1-y)*vh];
  const [left,top,width,height]=map.viewBox;
  return p.every(Number.isFinite)&&p[0]>=left&&p[0]<=left+width&&p[1]>=top&&p[1]<=top+height?p:null;
 }
 function portrait(resident,size=44){
  const wrap=document.createElement('span');wrap.className='resident-face';
  Object.assign(wrap.style,{display:'inline-grid',placeItems:'center',width:size+'px',height:size+'px',flexShrink:'0',borderRadius:'50%',overflow:'hidden',border:'1px solid #e0bd7270',background:'#263330'});
  const fallback=()=>{wrap.textContent=(resident?.name||'?').slice(0,1);wrap.title='Portrait not captured or identity unavailable';};fallback();
  const asset=manifest?.portraits?.[String(resident?.id)];
  if(!asset||!Number.isInteger(resident?.baseId)||resident.baseId!==asset.baseId||!validFile(asset.file))return wrap;
  const svg=node('svg',{viewBox:asset.viewBox.join(' '),width:size,height:size,role:'img','aria-label':resident.name+' · captured portrait'});
  const img=node('image',{href:base+asset.file,width:asset.width,height:asset.height});img.onerror=fallback;svg.append(img);wrap.replaceChildren(svg);wrap.title=asset.source;return wrap;
 }
 function renderMap(svg,rows,selected,onSelect,{connected=true,speaker=null}={}){
  if(!map||!validFile(map.file))return false;
  let cache=maps.get(svg);
  if(!cache){
   svg.replaceChildren();cache={markers:new Map(),failed:false};maps.set(svg,cache);
   const img=node('image',{href:base+map.file,width:map.width,height:map.height});
   img.onerror=()=>{cache.failed=true;img.remove();svg.setAttribute('aria-label','Map image unavailable; positions retain aerial calibration');};svg.append(img);
  }
  svg.setAttribute('viewBox',map.viewBox.join(' '));svg.setAttribute('aria-label',cache.failed?'Map image unavailable; positions retain aerial calibration':'Captured Whiterun aerial map with '+(connected?'live':'last observed')+' resident positions');
  const seen=new Set();
  for(const r of rows){
   if(r.loaded===false)continue;
   const p=point(r.position||[r.x,r.y,r.z],r.space);if(!p)continue;
   const chosen=r.id===selected,talking=r.id===speaker;
   seen.add(r.id);let marker=cache.markers.get(r.id);
   if(!marker){marker=node('circle');marker.append(node('title'));cache.markers.set(r.id,marker);svg.append(marker);}
   for(const [k,v] of Object.entries({cx:p[0],cy:p[1],r:chosen?13:9,fill:talking?'#a5ffcb':chosen?'#fff1b5':'#f5bc58',stroke:'#171e20','stroke-width':3,opacity:connected?1:.45,tabindex:connected?0:-1,role:'button','aria-label':r.name+(talking?' · speaking':'')}))marker.setAttribute(k,v);
   marker.style.cursor=connected?'pointer':'default';marker.firstChild.textContent=r.name;
   const select=()=>{if(connected)onSelect(r.id);};marker.onclick=select;marker.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}};
  }
  for(const [id,marker] of cache.markers)if(!seen.has(id)){marker.remove();cache.markers.delete(id);}
  return true;
 }
 function coin(){
  const svg=node('svg',{viewBox:'0 0 24 24',width:18,height:18,role:'img','aria-label':'Septims'});svg.style.verticalAlign='middle';
  svg.append(node('circle',{cx:12,cy:12,r:10,fill:'#9a6928',stroke:'#eacb83','stroke-width':1.5}),node('circle',{cx:12,cy:12,r:7.5,fill:'none',stroke:'#eacb83','stroke-width':.7}));
  const s=node('text',{x:12,y:16,'text-anchor':'middle',fill:'#fff0be','font-family':'Georgia,serif','font-size':13});s.textContent='S';svg.append(s);return svg;
 }
 return {point,portrait,renderMap,coin};
}
if(typeof window!=='undefined')window.residentMedia=createResidentMedia(window.RESIDENT_MEDIA,window.RESIDENT_MEDIA_BASE||'media/');
if(typeof module!=='undefined')module.exports={createResidentMedia};
