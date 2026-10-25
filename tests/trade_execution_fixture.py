"""Authored test-only trade witnesses. Real controller interop has its own suite."""
import copy
from economy_catalog import catalog_hash
from market_policy import policy_hash
from trade_execution import IDENTITY


def native_trade_status(epoch='trade-test'):
    return {'available':True,'protocol':2,'epoch':epoch,'catalog_hash':catalog_hash(),'market_policy_hash':policy_hash()}


def trade_ack(command):
    ack={'id':command['id'],'protocol':2,'status':'applied','accepted':True,
         **{key:copy.deepcopy(command[key]) for key in IDENTITY}}
    if command['phase']=='arm':
        ack.update(phase='armed',permit='permit-'+command['trade_id'],inventory=copy.deepcopy(command['before']),
                   effects_issued=False,no_effects_issued=True,legs=[])
    else:
        ack.update(phase='complete',permit=command['permit'],inventory=copy.deepcopy(command['after']),
                   effects_issued=True,no_effects_issued=False,legs=[
            {'leg':name,'item':item,'amount':amount,'issued':True,'observed':True,'debit_observed':True,'credit_observed':True}
            for name,item,amount in [('goods',command['commodity'],command['quantity']),('payment','gold',command['cost'])]])
    return ack


def qualify_trade_observation(observation):
    observation['trade_execution']=native_trade_status()
    for row in observation.get('residents',[]):
        row.setdefault('baseId',row['id']+100000);row.setdefault('isPerson',True)
    return observation


def arm_trade(world,observation,bind):
    """Fixture explicit arm and checkpoint binding; never synthesize delivery."""
    command=world.pending(observation['session'])
    if command and command.get('kind')=='bind_checkpoint':bind();command=world.pending(observation['session'])
    if command and command.get('kind')=='inventory_trade' and command.get('phase')=='arm':
        observation['ack']=trade_ack(command);world.observe(observation);bind()
    return world.pending(observation['session'])
