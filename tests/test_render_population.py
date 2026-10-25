import copy
import json
import re
import unittest
from tools.render_population import render


class PopulationReportTests(unittest.TestCase):
    def test_route_counts_preserve_unknown_including_missing_and_nonboolean_legacy_values(self):
        residents={str(i):{'id':i,'name':str(i),'native_route_supported':value,'native_route_support_basis':'observed_executor_person_v1'}
                   for i,value in enumerate((True,False,None,'false',0),1)}
        residents['6']={'id':6,'name':'</script><img src=x>'}
        evidence={'after':{'society':{'checkpoint':7,'people':{key:{} for key in residents},
            'town':{'counts':{'residents':6,'native_route_supported':99},'residents':residents,'businesses':{}}},
            'bridge':{'observation':{'residents':[]}}}}
        before=copy.deepcopy(evidence)
        html=render(evidence)
        snapshot=json.loads(re.search(r'<script type="application/json" id="snapshot">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(snapshot['counts']['native_route_supported'],1)
        self.assertEqual(snapshot['counts']['native_route_unavailable'],1)
        self.assertEqual(snapshot['counts']['native_route_unknown'],4)
        self.assertEqual([r['native_route_supported'] for r in snapshot['residents']],[True,False,None,None,None,None])
        self.assertEqual(evidence,before)
        self.assertNotIn('</script><img src=x>',html)
        self.assertIn('recorded snapshot, not a live feed',html)

    def test_legacy_route_flags_do_not_gain_observed_executor_provenance(self):
        evidence={'after':{'society':{'checkpoint':7,'people':{'1':{'agency':{'native_route_supported':True}}},
            'town':{'counts':{'residents':1},'residents':{'1':{'id':1,'name':'Resident','native_route_supported':True}},'businesses':{}}},
            'bridge':{'observation':{'residents':[]}}}}
        html=render(evidence)
        snapshot=json.loads(re.search(r'<script type="application/json" id="snapshot">(.*?)</script>',html,re.S).group(1))
        self.assertIsNone(snapshot['residents'][0]['native_route_supported'])
        self.assertEqual(snapshot['counts']['native_route_unknown'],1)


if __name__=='__main__':unittest.main()
