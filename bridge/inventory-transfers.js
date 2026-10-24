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
