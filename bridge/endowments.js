function createEndowmentController(platform,now=Date.now){
 const storage=platform().storage||{};
 const issued=storage.whiterunEndowmentIssued||(storage.whiterunEndowmentIssued={});
 const items=['gold','bread','grain'],ids={gold:0xf,bread:0x65c97,grain:0x4b0ba};
 return {
  reset(){for(const key of Object.keys(issued))delete issued[key];},
  step(command){
   const sp=platform(),fail=error=>({done:true,ack:{id:command.id,status:'held',error}});
   const grant=command.grant,before=command.before,after=command.after;
   const expected=command.actor===108149?{gold:100,bread:2,grain:20}:{gold:20,bread:2,grain:0};
   if(command.source!=='founding-resources-v1'||command.id!=='founding-resources-v1-'+command.actor||
      !Number.isInteger(command.actor)||!grant||!before||!after||
      items.some(k=>grant[k]!==expected[k]||!Number.isInteger(before[k])||before[k]<0||before[k]>1000000||after[k]!==before[k]+grant[k]))
    return fail('Invalid bounded starting-resource contract');
   const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
   if(!actor||actor.isDead()||actor.isChild())return fail('Starting-resource resident unavailable');
   const keyword=sp.Keyword?.from(sp.Game.getFormEx(0x13794));
   if(!keyword||typeof actor.hasKeyword!=='function'||!actor.hasKeyword(keyword))return fail('Starting-resource adult classification unavailable');
   const forms=Object.fromEntries(items.map(k=>[k,sp.Game.getFormEx(ids[k])]));
   if(items.some(k=>!forms[k]))return fail('Starting-resource item forms unavailable');
   const actual=Object.fromEntries(items.map(k=>[k,actor.getItemCount(forms[k])]));
   const matches=state=>items.every(k=>actual[k]===state[k]);
   if(matches(after)){delete issued[command.id];return {done:true,ack:{id:command.id,status:'applied',inventory:actual,source:command.source,loaded:actor.is3DLoaded(),scope:'native inventory only; no movement or animation claimed'}};}
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
