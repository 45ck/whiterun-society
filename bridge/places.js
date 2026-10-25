// Public landmarks from the owned master. Invisible map markers need no 3D mesh.
// Cross-cell coordinates only compare inside the same exterior worldspace.
function validateVenueCatalog(value){
 if(!value||typeof value!=='object'||!Array.isArray(value.venues)||value.venues.length>512||
    typeof value.version!=='string'||! /^[A-Za-z0-9_-]{1,64}$/.test(value.version)||
    typeof value.knowledge!=='string'||!value.knowledge.trim()||value.knowledge.length>500)throw Error('Invalid venue catalogue');
 const ids=new Set();
 for(const v of value.venues){
  if(!v||!Number.isInteger(v.id)||v.id<=0||v.id>0xffffffff||ids.has(v.id)||
     !['public_place','rest_bench'].includes(v.kind)||typeof v.name!=='string'||!v.name.trim()||v.name.length>120||
     typeof v.provenance!=='string'||!v.provenance.trim()||v.provenance.length>500||
     v.access!==(v.kind==='rest_bench'?'inspected_unowned':'public')||
     (v.editor_id!==undefined&&(typeof v.editor_id!=='string'||v.editor_id.length>120)))throw Error('Invalid venue catalogue entry');
  ids.add(v.id);
 }
 return JSON.parse(JSON.stringify(value));
}
function configuredVenueCatalog(value){
 return validateVenueCatalog(value===undefined?(typeof WHITERUN_VENUE_CATALOG!=='undefined'?WHITERUN_VENUE_CATALOG:require('../config/places.json')):value);
}
function venueSpace(ref){
 try{const cell=ref?.getParentCell?.(),world=ref?.getWorldSpace?.();if(!cell)return null;
  const cellId=cell.getFormID?.(),worldId=world?.getFormID?.(),interior=cell.isInterior?.();
  return {cell:Number.isInteger(cellId)&&cellId>0?cellId:null,interior:typeof interior==='boolean'?interior:null,world:Number.isInteger(worldId)&&worldId>0?worldId:null};
 }catch(_){return null;}
}
function createPlaceObserver(platform,catalog){
 const configured=configuredVenueCatalog(catalog),sites=configured.venues.filter(v=>v.kind==='public_place');
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
    const result={...site,available:false,eligible_actors:[],position:null,space:null,catalog_version:configured.version,
     source:configured.knowledge};
    try{
     const target=sp.ObjectReference.from(sp.Game.getFormEx(site.id));
     if(!target||target.getFormID()!==site.id||!space(target)||target.isDisabled()!==false)return result;
     const position=[target.getPositionX(),target.getPositionY(),target.getPositionZ()];
     if(!position.every(Number.isFinite))return result;
     result.position=position;result.space=venueSpace(target);result.available=true;
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
if(typeof module!=='undefined')module.exports={createPlaceObserver,validateVenueCatalog,configuredVenueCatalog,venueSpace};
