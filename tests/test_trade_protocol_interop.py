"""Actual Python checkpoints and persistent JS trade controller interoperability.

Only actor/form APIs are fixtures. These are not in-game/native deployment claims.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import economy_catalog
import market_policy
import test_resource_protocol_interop as process_fixture
from lineage import TimelineEconomy

ROOT=Path(__file__).resolve().parents[1]
HARNESS=r"""
const readline=require('node:readline');
const {createEconomyCatalogController}=require('./bridge/economy-catalog.js');
const {createInventoryTransfers}=require('./bridge/inventory-transfers.js');
const manifest=JSON.parse(process.argv[1]),marketPolicy=JSON.parse(process.argv[2]);
const session='trade-interop',keys=manifest.commodities.map(c=>c.id);
let clock=100,pending=[],calls=[],stock={buyer:Object.fromEntries(keys.map(k=>[k,k==='gold'?20:0])),seller:Object.fromEntries(keys.map(k=>[k,k==='gold'?7:8]))};
const forms=new Map(),byMapping=new Map(),keyword={getFormID:()=>0x13794};
for(const item of manifest.commodities){const form={item:item.id,getFormID:()=>item.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30})[item.native.record_type]};
 forms.set(form.getFormID(),form);byMapping.set(item.native.plugin.toLowerCase()+':'+item.native.local_form_id,form);}
const actors={};for(const [role,id] of [['buyer',901],['seller',902]])actors[role]={role,getFormID:()=>id,getActorBase:()=>({getFormID:()=>id+1000}),
 isDead:()=>false,isChild:()=>false,is3DLoaded:()=>true,hasKeyword:value=>value===keyword,
 getPositionX:()=>role==='buyer'?0:100,getPositionY:()=>0,getPositionZ:()=>0,getParentCell:()=>({getFormID:()=>50}),
 getItemCount:form=>stock[role][form.item],removeItem(form,amount,silent,recipient){const call={from:role,to:recipient.role,item:form.item,amount};calls.push(call);pending.push(call);}};
const platform={Actor:{from:value=>Object.values(actors).includes(value)?value:null},Keyword:{from:value=>value===keyword?keyword:null},
 Game:{getFormEx:id=>id===901?actors.buyer:id===902?actors.seller:id===0x13794?keyword:forms.get(id),getFormFromFile:(id,file)=>byMapping.get(file.toLowerCase()+':'+id)}};
const catalog=createEconomyCatalogController(()=>platform,manifest);
const controller=createInventoryTransfers(()=>platform,()=>clock,{catalog,marketPolicy,session:()=>session});
function state(result){return {result,trade_execution:controller.status(),economy_catalog:catalog.status(),stock:JSON.parse(JSON.stringify(stock)),calls:[...calls],queued:pending.length,session};}
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{try{
 const req=JSON.parse(line);clock++;let result=null;
 if(req.op==='step')result=controller.step(req.command);
 else if(req.op==='apply'){for(const leg of pending){stock[leg.from][leg.item]-=leg.amount;stock[leg.to][leg.item]+=leg.amount;}pending=[];}
 else if(req.op==='reset')controller.reset();
 else if(req.op==='external_stock')stock=JSON.parse(JSON.stringify(req.stock));
 else if(req.op!=='state')throw Error('Unknown fixture operation');
 console.log(JSON.stringify(state(result)));
}catch(error){console.log(JSON.stringify({harness_error:String(error.stack||error)}));}});
"""


class NativeTradeProcess(process_fixture.NativeResourceProcess):
    def __init__(self,catalog,policy):
        executable=shutil.which('node')
        if not executable:raise RuntimeError('Node is required for trade protocol interop tests')
        self.process=subprocess.Popen([executable,'-e',HARNESS,json.dumps(catalog),json.dumps(policy)],cwd=ROOT,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
        self.reader=ThreadPoolExecutor(max_workers=1)


class TradeInteropBase(unittest.TestCase):
    commodity='grain'
    def setUp(self):
        if self.commodity=='iron':
            catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
            catalog['commodities'].append({'id':'iron','label':'Iron','native':{'plugin':'Skyrim.esm','local_form_id':388,'record_type':'MISC'},'currency':False,'provenance':'Authored interop fixture only'})
            self.enterContext(patch.object(economy_catalog,'ECONOMY_CATALOG',economy_catalog.validate_catalog(catalog)))
            policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=economy_catalog.catalog_hash()
            row=copy.deepcopy(policy['goods'][1]);row.update(commodity='iron',legacy_retail_capability=None,reserve_mode='seller_choice');policy['goods'].append(row)
            self.enterContext(patch.object(market_policy,'MARKET_POLICY',market_policy.validate_policy(policy)))
        self.native=NativeTradeProcess(economy_catalog.ECONOMY_CATALOG,market_policy.MARKET_POLICY);self.addCleanup(self.native.close)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.world=TimelineEconomy(Path(self.temp.name)/'interop.sqlite');self.addCleanup(self.world.db.close)
        view=self.native.request('state')
        self.obs={'session':view['session'],'checkpoint':0,'ready':True,'gameDays':4.,
            'trade_execution':view['trade_execution'],'economy_catalog':view['economy_catalog'],
            'residents':[{'id':actor,'baseId':actor+1000,'name':'Observed '+role,'isPerson':True,'x':100*index,'y':0,'z':0,
                'inventory':view['stock'][role]} for index,(role,actor) in enumerate([('buyer',901),('seller',902)])]}
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        self.world.initialize_population('interop-census','interop-seed',self.obs);self.bind()

    def bind(self):
        for _ in range(8):
            if not self.world.transition:self.assertIsNone(self.world.error);return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None);self.world.observe(self.obs)
        self.fail('Checkpoint loop exceeded limit')

    def observe_native(self,view):
        self.obs['trade_execution']=view['trade_execution'];self.obs['economy_catalog']=view['economy_catalog']
        for role,row in zip(('buyer','seller'),self.obs['residents']):row['inventory']=copy.deepcopy(view['stock'][role])
        if (view.get('result') or {}).get('ack'):self.obs['ack']=view['result']['ack']
        else:self.obs.pop('ack',None)
        self.world.observe(self.obs)

    def arm(self):
        self.world.plan_trade('interop-sale',self.obs,901,902,quantity=2,unit_price=3,commodity=self.commodity)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint');self.bind()
        arm=self.world.pending(self.obs['session']);view=self.native.request('step',command=arm)
        self.assertEqual(view['result']['ack']['phase'],'armed');self.assertEqual(view['calls'],[])
        self.observe_native(view);self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint');self.bind()
        delivery=self.world.pending(self.obs['session']);self.assertEqual(delivery['phase'],'deliver')
        return arm,delivery

    def assert_success(self):
        arm,command=self.arm()
        for _ in range(5):
            view=self.native.request('step',command=command)
            if view['result']['done']:break
            self.assertEqual(view['queued'],1);self.native.request('apply')
        else:self.fail('Trade controller did not finish bounded native legs')
        self.assertEqual(view['result']['ack']['phase'],'complete');self.assertEqual(len(view['calls']),2)
        self.assertEqual(view['stock'],command['after'])
        self.observe_native(view);self.bind()
        self.assertEqual(len(self.world.active['trades']),1);self.assertIsNone(self.world.active['pending'])
        for role,actor in [('buyer',901),('seller',902)]:
            memories=[m for m in self.world.active['people'][str(actor)]['memories'] if m['kind']=='completed_trade']
            self.assertEqual(len(memories),1);self.assertEqual((memories[0]['commodity'],memories[0]['quantity'],memories[0]['gold']),(self.commodity,2,6))
        before=copy.deepcopy(self.world.active)
        again=self.native.request('step',command=command);self.assertEqual(again['result'],view['result'])
        self.assertEqual(len(again['calls']),2);self.observe_native(again);self.assertEqual(self.world.active,before)
        duplicate=self.world.plan_trade('interop-sale',self.obs,901,902,quantity=2,unit_price=3,commodity=self.commodity)
        self.assertEqual(duplicate['status'],'committed');self.assertEqual(self.world.active,before)

    def assert_cold(self,partial):
        _,command=self.arm()
        if partial:
            view=self.native.request('step',command=command);self.assertFalse(view['result']['done']);self.native.request('apply')
        self.native.request('reset');view=self.native.request('step',command=command)
        self.assertEqual(view['result']['ack']['status'],'held');self.assertIsNone(view['result']['ack']['effects_issued'])
        self.observe_native(view);self.bind()
        self.assertEqual(self.world.active['pending']['status'],'held');self.assertEqual(self.world.active['trades'],[])
        self.assertIsNone(self.world.pending(self.obs['session']))
        self.native.request('external_stock',stock=command['after']);again=self.native.request('step',command=command)
        self.assertEqual(again['result']['ack']['status'],'held');self.assertEqual(len(again['calls']),int(partial))
        self.observe_native(again);self.assertIsNone(self.world.transition)
        self.assertTrue(all(not p['memories'] for p in self.world.active['people'].values()))


class TradeProtocolInteropTests(TradeInteropBase):
    def test_native_two_leg_exchange_commits_exactly_once(self):self.assert_success()
    def test_cold_native_reset_before_first_write_cannot_replay(self):self.assert_cold(False)
    def test_cold_native_reset_after_goods_cannot_charge_or_credit(self):self.assert_cold(True)


class FourthCommodityInteropTests(TradeInteropBase):
    commodity='iron'
    def test_fourth_configured_good_uses_actual_catalog_forms_and_native_witnesses(self):self.assert_success()
