// Public landmarks from the owned master. Invisible map markers need no 3D mesh.
// Cross-cell coordinates only compare inside the same exterior worldspace.
function createPlaceObserver(platform){
 const sites=[{id:0x2be1b,name:'Whiterun market',editorId:'WhiterunMarketplaceMarker'}];
 function space(ref){
  const cell=ref?.getParentCell?.(),world=ref?.getWorldSpace?.();
  return cell&&cell.isInterior()===false&&world?world.getFormID():null;
 }
 return {
  validTarget(actor,target){
   if(!actor||!target||!sites.some(p=>p.id===target.getFormID())||target.isDisabled?.()!==false)return false;
   const a=space(actor),b=space(target);return a!==null&&a===b;
  },
  sense(residents){
   const sp=platform();
   return sites.map(site=>{
    const result={...site,available:false,eligible_actors:[],position:null,
     source:'Owned-game public reference; authored resident map knowledge, not line of sight'};
    try{
     const target=sp.ObjectReference.from(sp.Game.getFormEx(site.id));
     if(!target||!space(target)||target.isDisabled()!==false)return result;
     const position=[target.getPositionX(),target.getPositionY(),target.getPositionZ()];
     if(!position.every(Number.isFinite))return result;
     result.position=position;result.available=true;
     for(const r of residents){if(r.isPerson!==true)continue;
      const actor=sp.Actor.from(sp.Game.getFormEx(r.id));
      if(actor?.is3DLoaded()&&this.validTarget(actor,target))result.eligible_actors.push(r.id);
     }
    }catch(_){} // Unknown spatial identity is never assumed to match.
    return result;
   });
  }
 };
}
if(typeof module!=='undefined')module.exports={createPlaceObserver};
