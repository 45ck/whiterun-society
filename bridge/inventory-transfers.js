// Embedded by the deployer; receives a getter because native bindings may refresh.
function createInventoryTransfers(platform, now=Date.now, options={}) {
  const issued=new Map();
  const catalog=options.catalog;
  const itemIds=()=>typeof catalog?.itemIds==='function'?catalog.itemIds().slice().sort():[];
  const validInventory=(value,keys)=>value&&typeof value==='object'&&Object.keys(value).sort().join('|')===keys.join('|')&&keys.every(k=>Number.isSafeInteger(value[k])&&value[k]>=0&&value[k]<=2147483647);
  function resolveForms(command,keys){
    if(!catalog||typeof catalog.status!=='function'||typeof catalog.resolve!=='function')return null;
    const status=catalog.status();
    if(status.available!==true||typeof command.catalog_hash!=='string'||command.catalog_hash!==status.catalog_hash)return null;
    const resolved=catalog.resolve();
    if(resolved.available!==true||keys.some(key=>!resolved.forms?.[key]))return null;
    return Object.fromEntries(keys.map(key=>[key,resolved.forms[key]]));
  }
  const equal=(a,b,keys)=>['buyer','seller'].every(role=>keys.every(item=>a[role][item]===b[role][item]));
  function read(buyer,seller,forms) {
    const inventory=actor=>Object.fromEntries(Object.entries(forms).map(([key,form])=>[key,actor.getItemCount(form)]));
    return {buyer:inventory(buyer),seller:inventory(seller)};
  }
  return {
    reset(){issued.clear();},
    consume(command) {
      const sp=platform(),fail=error=>({done:true,ack:{id:command.id,status:'held',error}});
      const before=command.before,after=command.after,keys=itemIds();
      if(!['gold','bread'].every(k=>keys.includes(k))||!validInventory(before,keys)||!validInventory(after,keys)||
         before.bread<1||keys.some(k=>after[k]!==before[k]-(k==='bread'?1:0)))return fail('Invalid complete food-use contract');
      const actor=sp.Actor.from(sp.Game.getFormEx(command.actor));
      if(!actor||!actor.is3DLoaded()||actor.isDead()||actor.isChild()||typeof actor.equipItem!=='function')return fail('Food-use actor unavailable');
      const forms=resolveForms(command,keys);
      if(!forms)return fail('Food-use catalog binding or resolved forms unavailable');
      const {bread,gold}=forms;
      const actual=Object.fromEntries(keys.map(k=>[k,actor.getItemCount(forms[k])]));
      if(!validInventory(actual,keys))return fail('Food-use inventory observation unavailable');
      const matches=expected=>keys.every(k=>actual[k]===expected[k]);
      if(matches(after)){
        issued.delete(command.id);
        return {done:true,ack:{id:command.id,status:'applied',inventory:actual,catalog_hash:command.catalog_hash,mechanism:'native_equip_food'}};
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
      const commodity=command.commodity||'bread',keys=itemIds();
      if(!['bread','grain'].includes(commodity)||command.buyer===command.seller||!Number.isInteger(command.quantity)||command.quantity<1||command.quantity>10||!Number.isInteger(command.cost)||command.cost<1||command.cost>1000)return fail('Invalid commodity trade contract');
      if(!['gold',commodity].every(k=>keys.includes(k))||![command.before,command.after].every(v=>v&&Object.keys(v).sort().join(',')==='buyer,seller'&&['buyer','seller'].every(r=>validInventory(v[r],keys))))return fail('Invalid complete trade inventory contract');
      const expected=JSON.parse(JSON.stringify(command.before));
      expected.buyer.gold-=command.cost;expected.seller.gold+=command.cost;
      expected.buyer[commodity]+=command.quantity;expected.seller[commodity]-=command.quantity;
      if(expected.buyer.gold<0||expected.seller[commodity]<0||!equal(expected,command.after,keys))return fail('Unconserved trade contract');
      // Resolve every native handle on this frame, including the item forms.
      const buyer=sp.Actor.from(sp.Game.getFormEx(command.buyer));
      const seller=sp.Actor.from(sp.Game.getFormEx(command.seller));
      if (!buyer || !seller || !buyer.is3DLoaded() || !seller.is3DLoaded()) return fail('Actor unloaded');
      if (buyer.isDead() || seller.isDead() || buyer.isChild() || seller.isChild()) return fail('Invalid actor state');
      const forms=resolveForms(command,keys);
      if(!forms)return fail('Trade catalog binding or resolved forms unavailable');
      const gold=forms.gold,goods=forms[commodity],actual=read(buyer,seller,forms);
      if(!['buyer','seller'].every(role=>validInventory(actual[role],keys)))return fail('Trade inventory observation unavailable');
      if (equal(actual,command.after,keys)) {
        issued.delete(command.id);
        return {done:true,ack:{id:command.id,status:'applied',inventory:actual,catalog_hash:command.catalog_hash}};
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
