// Embedded by the deployer; receives a getter because native bindings may refresh.
function createInventoryTransfers(platform, now=Date.now) {
  const issued=new Map();
  const equal=(a,b)=>['buyer','seller'].every(role=>['gold','bread'].every(item=>a[role][item]===b[role][item]));
  function read(buyer,seller,gold,bread) {
    return {buyer:{gold:buyer.getItemCount(gold),bread:buyer.getItemCount(bread)},
            seller:{gold:seller.getItemCount(gold),bread:seller.getItemCount(bread)}};
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
      // Resolve every native handle on this frame, including the item forms.
      const buyer=sp.Actor.from(sp.Game.getFormEx(command.buyer));
      const seller=sp.Actor.from(sp.Game.getFormEx(command.seller));
      if (!buyer || !seller || !buyer.is3DLoaded() || !seller.is3DLoaded()) return fail('Actor unloaded');
      if (buyer.isDead() || seller.isDead() || buyer.isChild() || seller.isChild()) return fail('Invalid actor state');
      const gold=sp.Game.getFormEx(0xf),bread=sp.Game.getFormEx(0x65c97);
      const actual=read(buyer,seller,gold,bread);
      if (equal(actual,command.after)) {
        issued.delete(command.id);
        return {done:true,ack:{id:command.id,status:'applied',inventory:actual}};
      }
      const goodsOnly={buyer:{gold:command.before.buyer.gold,bread:command.after.buyer.bread},
                      seller:{gold:command.before.seller.gold,bread:command.after.seller.bread}};
      const sent=issued.get(command.id);
      if (sent && now()-sent.at>5000) return fail('Inventory transfer timed out; reconciliation required');
      if (equal(actual,goodsOnly)) {
        if (!sent || sent.leg==='goods') {
          issued.set(command.id,{leg:'gold',at:now()});
          buyer.removeItem(gold,command.cost,true,seller);
        }
        return {done:false};
      }
      if (equal(actual,command.before)) {
        if (!sent) {
          issued.set(command.id,{leg:'goods',at:now()});
          seller.removeItem(bread,command.quantity,true,buyer);
        }
        return {done:false};
      }
      return fail('Observed inventory differs from all allowed transfer states');
    }
  };
}
if (typeof module!=='undefined') module.exports={createInventoryTransfers};
