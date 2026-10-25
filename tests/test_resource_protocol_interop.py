"""Real service checkpoints exchange actual JS-controller receipts over JSON.

Only native actor/form APIs are fake. No game, speech, provider, or service port
is started; the persistent Node process owns the native live-witness journal.
"""
import copy
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from lineage import TimelineEconomy
from resource_manifest import load_manifest,manifest_hash

ROOT=Path(__file__).resolve().parents[1]
HARNESS=r"""
const readline=require('node:readline');
const {createEconomyCatalogController}=require('./bridge/economy-catalog.js');
const {createEndowmentController}=require('./bridge/endowments.js');
const catalogManifest=require('./config/economy-catalog.json'),manifest=require('./config/resource-manifest.json');
const actorId=901,baseId=1901,session='resource-interop';
let clock=100,stock={gold:7,bread:1,grain:3},pending=[],calls=[];
const byId=new Map(),byMapping=new Map(),keyword={getFormID:()=>0x13794};
for(const item of catalogManifest.commodities){
 const form={item:item.id,getFormID:()=>item.native.local_form_id,getType:()=>({MISC:32,ALCH:46,INGR:30})[item.native.record_type]};
 byId.set(form.getFormID(),form);byMapping.set(item.native.plugin.toLowerCase()+':'+item.native.local_form_id,form);
}
const actor={getFormID:()=>actorId,getActorBase:()=>({getFormID:()=>baseId}),
 isDead:()=>false,isChild:()=>false,is3DLoaded:()=>true,hasKeyword:value=>value===keyword,
 getItemCount:form=>stock[form.item],addItem(form,amount){const call={item:form.item,amount};calls.push(call);pending.push(call);}};
const platform={Actor:{from:value=>value===actor?actor:null},Keyword:{from:value=>value===keyword?keyword:null},
 Game:{getFormEx:id=>id===actorId?actor:id===0x13794?keyword:byId.get(id),
 getFormFromFile:(id,file)=>byMapping.get(file.toLowerCase()+':'+id)}};
const catalog=createEconomyCatalogController(()=>platform,catalogManifest);
const controller=createEndowmentController(()=>platform,()=>clock,{catalog,manifest,session:()=>session});
function state(result){return {result,resource_import:controller.status(),economy_catalog:catalog.status(),
 stock:{...stock},calls:calls.map(row=>({...row})),queued:pending.length,actor:actorId,baseId,session};}
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
 try{const request=JSON.parse(line);clock++;
  let result=null;
  if(request.op==='step')result=controller.step(request.command);
  else if(request.op==='apply'){for(const leg of pending)stock[leg.item]+=leg.amount;pending=[];}
  else if(request.op==='reset')controller.reset();
  else if(request.op==='external_stock')stock={...request.stock};
  else if(request.op!=='state')throw Error('Unknown fixture operation');
  console.log(JSON.stringify(state(result)));
 }catch(error){console.log(JSON.stringify({harness_error:String(error.stack||error)}));}
});
"""


class NativeResourceProcess:
    def __init__(self):
        executable=shutil.which('node')
        if not executable:raise RuntimeError('Node is required for resource protocol interoperation tests')
        self.process=subprocess.Popen([executable,'-e',HARNESS],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
        self.reader=ThreadPoolExecutor(max_workers=1)

    def request(self,op,**payload):
        self.process.stdin.write(json.dumps({'op':op,**payload})+'\n');self.process.stdin.flush()
        try:line=self.reader.submit(self.process.stdout.readline).result(timeout=5)
        except TimeoutError:
            self.process.kill();raise AssertionError('Native fixture response exceeded five seconds') from None
        if not line:raise AssertionError('Native fixture exited: '+self.process.stderr.read())
        result=json.loads(line)
        if 'harness_error' in result:raise AssertionError(result['harness_error'])
        return result

    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        self.reader.shutdown(wait=True)
        self.process.stdout.close();self.process.stderr.close()


class ResourceProtocolInteropTests(unittest.TestCase):
    def setUp(self):
        self.native=NativeResourceProcess();self.addCleanup(self.native.close)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.world=TimelineEconomy(Path(self.temp.name)/'interop.sqlite');self.addCleanup(self.world.db.close)
        self.manifest=load_manifest();self.digest=manifest_hash(self.manifest)
        view=self.native.request('state');self.actor=view['actor']
        self.obs={'session':view['session'],'checkpoint':0,'ready':True,'gameDays':4.,
            'resource_import':view['resource_import'],'economy_catalog':view['economy_catalog'],
            'residents':[{'id':self.actor,'baseId':view['baseId'],'name':'Observed test recipient','isPerson':True,
                          'x':0,'y':0,'z':0,'inventory':view['stock']}]}
        self.world.observe(self.obs);self.world.bootstrap(self.obs);self.bind()
        self.world.initialize_population('observed-census','interop-seed',self.obs);self.bind()

    def bind(self):
        for _ in range(8):
            if not self.world.transition:
                self.assertIsNone(self.world.error);return
            self.obs['checkpoint']=self.world.transition['next'];self.obs.pop('ack',None)
            self.world.observe(self.obs)
        self.fail('Checkpoint transition did not settle')

    def observe_native(self,view,ack=True):
        self.obs['resource_import']=view['resource_import'];self.obs['economy_catalog']=view['economy_catalog']
        self.obs['residents'][0]['inventory']=copy.deepcopy(view['stock'])
        if ack and view.get('result',{}):self.obs['ack']=view['result']['ack']
        else:self.obs.pop('ack',None)
        self.world.observe(self.obs)

    def prepare(self):
        self.world.plan_endowment(self.actor,self.obs,self.manifest['id'],self.digest)
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint');self.bind()
        command=self.world.pending(self.obs['session']);self.assertEqual(command['phase'],'arm')
        return command

    def arm(self):
        command=self.prepare();view=self.native.request('step',command=command)
        self.assertEqual(view['calls'],[]);self.assertEqual(view['result']['ack']['phase'],'armed')
        self.observe_native(view)
        # A real native arm receipt still cannot expose delivery before its saved checkpoint binds.
        self.assertEqual(self.world.pending(self.obs['session'])['kind'],'bind_checkpoint');self.bind()
        delivery=self.world.pending(self.obs['session']);self.assertEqual(delivery['phase'],'deliver')
        self.assertEqual(delivery['permit'],view['result']['ack']['permit'])
        return command,delivery

    def assert_conserved(self,program):
        for item,capacity in program['capacity'].items():
            self.assertEqual(capacity,program['available'][item]+program['reserved'][item]+program['delivered'][item])
            self.assertEqual(program['remaining'][item],capacity-program['delivered'][item])

    def test_native_arm_then_observed_legs_settle_once_with_real_receipt_and_complete_accounts(self):
        arm,delivery=self.arm();grant=delivery['grant']
        for _ in range(8):
            view=self.native.request('step',command=delivery)
            if view['result']['done']:break
            self.assertLessEqual(view['queued'],1)
            self.native.request('apply')
        else:self.fail('Native delivery failed to finish within bounded legs')
        self.assertEqual(view['result']['ack']['phase'],'complete')
        self.assertEqual(view['stock'],delivery['after'])
        self.assertEqual(len(view['calls']),len([value for value in grant.values() if value]))
        self.observe_native(view);self.bind()
        program=self.world.active['town']['resource_program'];self.assert_conserved(program)
        self.assertEqual(program['reserved'],dict.fromkeys(grant,0));self.assertEqual(program['delivered'],grant)
        self.assertEqual(len(program['grants']),1);self.assertEqual(len(program['deliveries']),1)
        memories=[m for m in self.world.active['people'][str(self.actor)]['memories'] if m['kind']=='starting_resources_received']
        self.assertEqual(len(memories),1);self.assertEqual(memories[0]['resources'],grant)
        snapshot=copy.deepcopy(self.world.active)
        replay=self.native.request('step',command=delivery)
        self.assertEqual(replay['result'],view['result']);self.assertEqual(replay['calls'],view['calls'])
        self.observe_native(replay);self.assertIsNone(self.world.transition);self.assertEqual(self.world.active,snapshot)
        self.assertTrue(self.world.plan_endowment(self.actor,self.obs,self.manifest['id'],self.digest)['duplicate'])
        self.assertEqual(self.world.active,snapshot);self.assertEqual(self.world.state(),[])
        self.assertEqual(self.world.active.get('production',[]),[])

    def assert_cold_reset_quarantines(self,partial):
        arm,delivery=self.arm()
        if partial:
            first=self.native.request('step',command=delivery)
            self.assertFalse(first['result']['done']);self.assertEqual(len(first['calls']),1)
            applied=self.native.request('apply');self.assertNotEqual(applied['stock'],delivery['before'])
            self.assertNotEqual(applied['stock'],delivery['after'])
        reset=self.native.request('reset');self.assertNotEqual(reset['resource_import']['epoch'],delivery['delivery_epoch'])
        rejected=self.native.request('step',command=delivery)
        self.assertEqual(rejected['result']['ack']['status'],'held')
        self.assertIsNone(rejected['result']['ack']['effects_issued'])
        self.observe_native(rejected);self.bind()
        self.assertIsNone(self.world.pending(self.obs['session']))
        program=self.world.active['town']['resource_program'];self.assert_conserved(program)
        self.assertEqual(program['reserved'],delivery['grant']);self.assertEqual(program['delivered'],dict.fromkeys(delivery['grant'],0))
        self.assertEqual(program['grants'],{});self.assertEqual(self.world.active['pending']['status'],'held')
        self.assertFalse(any(m['kind']=='starting_resources_received' for m in self.world.active['people'][str(self.actor)]['memories']))
        # Unrelated changes which happen to produce expected balances are not a delivery witness.
        self.native.request('external_stock',stock=delivery['after'])
        again=self.native.request('step',command=delivery)
        self.assertEqual(again['result']['ack']['status'],'held')
        self.assertEqual(len(again['calls']),int(partial))
        self.observe_native(again);self.assertIsNone(self.world.transition)
        self.assertEqual(self.world.active['town']['resource_program'],program)

    def test_cold_native_reset_before_first_write_cannot_replay_or_credit_unrelated_after_state(self):
        self.assert_cold_reset_quarantines(False)

    def test_cold_native_reset_after_partial_delivery_retains_reservation_without_replay(self):
        self.assert_cold_reset_quarantines(True)


if __name__=='__main__':unittest.main()
