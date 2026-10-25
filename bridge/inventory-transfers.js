// Embedded by the deployer; receives a getter because native bindings may refresh.
function createInventoryTransfers(platform, now=Date.now) {
  const issued=new Map();
  const equal=(a,b,keys)=>['buyer','seller'].every(role=>keys.every(item=>a[role][item]===b[role][item]));
  function read(buyer,seller,forms) {
    const inventory=actor=>Object.fromEntries(Object.entries(forms).map(([key,form])=>[key,actor.getItemCount(form)]));
    return {buyer:inventory(buyer),seller:inventory(seller)};
  }
  return {
    reset(){issued.clear();},
    consume(command) {
      const sp=platform(),fail=error=>({done:true,ack:{id:command.id,status:'held',error}});
      const before=command.before,after=command.after;
      if(!before||!after||!['gold','bread'].every(k=>Number.isInteger(before[k])&&before[k]>=0&&Number.isInteger(after[k])&&after[k]>=0)||
         before.bread<1||after.bread!==before.bread-1||after.gold!==before.gold)return fail('Invalid food-use contract');
      const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
      if(!actor||!actor.is3DLoaded()||actor.isDead()||actor.isChild()||typeof actor.equipItem!=='function')return fail('Food-use actor unavailable');
      const bread=sp.Game.getFormEx(0x65c97),gold=sp.Game.getFormEx(0xf);
      if(!bread||!gold)return fail('Food-use forms unavailable');
      const actual={gold:actor.getItemCount(gold),bread:actor.getItemCount(bread)};
      const matches=expected=>actual.gold===expected.gold&&actual.bread===expected.bread;
      if(matches(after)){
        issued.delete(command.id);
        return {done:true,ack:{id:command.id,status:'applied',inventory:actual,mechanism:'native_equip_food'}};
      }
      if(!matches(before))return fail('Unexpected inventory during consumption');
      const sent=issued.get(command.id);
      if(sent&&now()-sent.at>5000)return fail('Native food use timed out; no repeated attempt');
      if(!sent){issued.set(command.id,{leg:'consume',at:now()});actor.equipItem(bread,false,true);}
      return {done:false};
    },
    step(command) {
      const sp=platform();
      const fail=error=>({done:true,ack:{id:command.id,status:'held',error}});
      const commodity=command.commodity||'bread',keys=commodity==='grain'?['gold','bread','grain']:['gold','bread'];
      if(!['bread','grain'].includes(commodity)||command.buyer===command.seller||!Number.isInteger(command.quantity)||command.quantity<1||command.quantity>10||!Number.isInteger(command.cost)||command.cost<1||command.cost>1000)return fail('Invalid commodity trade contract');
      if(![command.before,command.after].every(v=>v&&Object.keys(v).sort().join(',')==='buyer,seller'&&['buyer','seller'].every(r=>v[r]&&Object.keys(v[r]).sort().join(',')===[...keys].sort().join(',')&&keys.every(k=>Number.isInteger(v[r][k])&&v[r][k]>=0))))return fail('Invalid trade inventory contract');
      const expected=JSON.parse(JSON.stringify(command.before));
      expected.buyer.gold-=command.cost;expected.seller.gold+=command.cost;
      expected.buyer[commodity]+=command.quantity;expected.seller[commodity]-=command.quantity;
      if(expected.buyer.gold<0||expected.seller[commodity]<0||!equal(expected,command.after,keys))return fail('Unconserved trade contract');
      // Resolve every native handle on this frame, including the item forms.
      const buyer=sp.Actor.from(sp.Game.getFormEx(command.buyer));
      const seller=sp.Actor.from(sp.Game.getFormEx(command.seller));
      if (!buyer || !seller || !buyer.is3DLoaded() || !seller.is3DLoaded()) return fail('Actor unloaded');
      if (buyer.isDead() || seller.isDead() || buyer.isChild() || seller.isChild()) return fail('Invalid actor state');
      const ids={gold:0xf,bread:0x65c97,grain:0x4b0ba};
      const forms=Object.fromEntries(keys.map(k=>[k,sp.Game.getFormEx(ids[k])]));
      if(Object.values(forms).some(f=>!f))return fail('Trade forms unavailable');
      const gold=forms.gold,goods=forms[commodity],actual=read(buyer,seller,forms);
      if (equal(actual,command.after,keys)) {
        issued.delete(command.id);
        return {done:true,ack:{id:command.id,status:'applied',inventory:actual}};
      }
      const goodsOnly=JSON.parse(JSON.stringify(command.before));
      goodsOnly.buyer[commodity]=command.after.buyer[commodity];goodsOnly.seller[commodity]=command.after.seller[commodity];
      const sent=issued.get(command.id);
      if (sent && now()-sent.at>5000) return fail('Inventory transfer timed out; reconciliation required');
      if (equal(actual,goodsOnly,keys)) {
        if (!sent || sent.leg==='goods') {
          issued.set(command.id,{leg:'gold',at:now()});
          buyer.removeItem(gold,command.cost,true,seller);
        }
        return {done:false};
      }
      if (equal(actual,command.before,keys)) {
        if (!sent) {
          issued.set(command.id,{leg:'goods',at:now()});
          seller.removeItem(goods,command.quantity,true,buyer);
        }
        return {done:false};
      }
      return fail('Observed inventory differs from all allowed transfer states');
    }
  };
}
if (typeof module!=='undefined') module.exports={createInventoryTransfers};
