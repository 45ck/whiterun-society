function createEndowmentController(platform,now=Date.now,options={}){
 const storage=platform().storage||{};
 const issued=storage.whiterunEndowmentIssued||(storage.whiterunEndowmentIssued={});
 const items=['gold','bread','grain'],catalog=options.catalog;
 return {
  reset(){for(const key of Object.keys(issued))delete issued[key];},
  step(command){
   const sp=platform(),fail=error=>({done:true,ack:{id:command.id,status:'held',error}});
   const grant=command.grant,before=command.before,after=command.after;
   const keys=typeof catalog?.itemIds==='function'?catalog.itemIds().slice().sort():[];
   const expected=command.actor===108149?{gold:100,bread:2,grain:20}:{gold:20,bread:2,grain:0};
   if(command.source!=='founding-resources-v1'||command.id!=='founding-resources-v1-'+command.actor||
      !Number.isInteger(command.actor)||!grant||Object.keys(grant).sort().join('|')!==[...items].sort().join('|')||
      !items.every(k=>keys.includes(k))||![before,after].every(v=>v&&Object.keys(v).sort().join('|')===keys.join('|')&&keys.every(k=>Number.isSafeInteger(v[k])&&v[k]>=0&&v[k]<=2147483647))||
      items.some(k=>grant[k]!==expected[k]||before[k]>1000000)||keys.some(k=>after[k]!==before[k]+(grant[k]||0)))
    return fail('Invalid bounded starting-resource contract');
   const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
   if(!actor||actor.isDead()||actor.isChild())return fail('Starting-resource resident unavailable');
   const keyword=sp.Keyword?.from(sp.Game.getFormEx(0x13794));
   if(!keyword||typeof actor.hasKeyword!=='function'||!actor.hasKeyword(keyword))return fail('Starting-resource adult classification unavailable');
   if(!catalog||typeof catalog.status!=='function'||typeof catalog.resolve!=='function')return fail('Starting-resource catalog required');
   const status=catalog.status(),resolved=catalog.resolve();
   if(status.available!==true||typeof command.catalog_hash!=='string'||command.catalog_hash!==status.catalog_hash||resolved.available!==true||keys.some(k=>!resolved.forms?.[k]))
    return fail('Starting-resource catalog binding or resolved forms unavailable');
   const forms=resolved.forms;
   const actual=Object.fromEntries(keys.map(k=>[k,actor.getItemCount(forms[k])]));
   if(keys.some(k=>!Number.isSafeInteger(actual[k])||actual[k]<0||actual[k]>2147483647))return fail('Starting-resource inventory observation unavailable');
   const matches=state=>keys.every(k=>actual[k]===state[k]);
   if(matches(after)){delete issued[command.id];return {done:true,ack:{id:command.id,status:'applied',inventory:actual,catalog_hash:command.catalog_hash,source:command.source,loaded:actor.is3DLoaded(),scope:'native inventory only; no movement or animation claimed'}};}
   const stages=[{...before}];
   for(const k of items)if(grant[k])stages.push({...stages.at(-1),[k]:after[k]});
   const stage=stages.findIndex(matches);
   if(stage<0)return fail('Unexpected inventory during starting-resource delivery');
   const sent=issued[command.id];
   if(sent&&now()-sent.at>5000)return fail('Starting-resource delivery timed out; no blind retry');
   if(!sent||stage>sent.stage){
    const next=items.find(k=>stages[stage][k]!==stages[stage+1][k]);
    issued[command.id]={stage,at:now()};actor.addItem(forms[next],grant[next],true);
   }
   return {done:false};
  }
 };
}
if(typeof module!=='undefined')module.exports={createEndowmentController};
