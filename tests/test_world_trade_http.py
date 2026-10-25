"""Actual HTTP parsing/route responses over an in-memory socket, no listener."""
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import economy_catalog
import market_policy
import server
import test_lineage
from catalog_fixture import native_catalog
from trade_execution_fixture import native_trade_status


class FinishedRequests(Exception):pass


class MemorySocket:
    def __init__(self,data):self.input=io.BytesIO(data);self.output=io.BytesIO()
    def makefile(self,mode,*args):
        if mode!='rb':raise AssertionError('Unexpected socket mode')
        return self.input
    def sendall(self,data):self.output.write(data)


class WorldTradeHTTPTests(unittest.TestCase):
    setUp=test_lineage.LineageTests.setUp
    tearDown=test_lineage.LineageTests.tearDown
    bind=test_lineage.LineageTests.bind

    def post(self,payload):
        requests=[('/heartbeat',self.obs),('/world/trade',payload)];responses=[]
        class MemoryServer:
            def __init__(inner,address,handler):inner.handler=handler
            def handle_request(inner):
                if not requests:raise FinishedRequests()
                path,body=requests.pop(0);encoded=json.dumps(body).encode()
                head=(f'POST {path} HTTP/1.0\r\nHost: 127.0.0.1:17899\r\nAuthorization: Bearer fixture-token\r\n'
                      f'X-Society-Session: a\r\nContent-Type: application/json\r\nContent-Length: {len(encoded)}\r\n\r\n').encode()
                connection=MemorySocket(head+encoded);inner.handler(connection,('127.0.0.1',1),inner)
                raw=connection.output.getvalue();headers,body=raw.split(b'\r\n\r\n',1)
                responses.append((int(headers.split(b' ',2)[1]),json.loads(body)))
            def server_close(inner):pass
        runtime=Path(self.temp.name)/'http-fixture'
        with patch.object(server,'LocalServer',MemoryServer),patch.object(server,'TimelineEconomy',return_value=self.world),\
             patch.object(server.secrets,'token_hex',return_value='fixture-token'),patch('builtins.print'),\
             patch('sys.argv',['server','--runtime',str(runtime),'--port','17899']):
            with self.assertRaises(FinishedRequests):server.main()
        self.assertEqual(responses[0][0],200,responses)
        return responses[-1]

    def test_explicit_fourth_commodity_reaches_real_trade_engine_as_ore(self):
        catalog=copy.deepcopy(economy_catalog.ECONOMY_CATALOG)
        catalog['commodities'].append({'id':'ore','label':'Ore','native':{'plugin':'Skyrim.esm','local_form_id':388,'record_type':'MISC'},'currency':False,'provenance':'HTTP boundary test fixture'})
        with patch.object(economy_catalog,'ECONOMY_CATALOG',economy_catalog.validate_catalog(catalog)):
            policy=copy.deepcopy(market_policy.MARKET_POLICY);policy['catalog_hash']=economy_catalog.catalog_hash()
            row=copy.deepcopy(policy['goods'][1]);row.update(commodity='ore',legacy_retail_capability=None,reserve_mode='seller_choice');policy['goods'].append(row)
            with patch.object(market_policy,'MARKET_POLICY',market_policy.validate_policy(policy)):
                self.obs['economy_catalog']=native_catalog();self.obs['trade_execution']=native_trade_status()
                self.obs['residents'][0]['inventory']['ore']=0;self.obs['residents'][1]['inventory']['ore']=5
                status,body=self.post({'id':'ore-http','buyer':108186,'seller':108149,'quantity':2,'unit_price':3,'commodity':'ore'})
                self.assertEqual(status,202,body);command=body['command']
                self.assertEqual(command['commodity'],'ore');self.assertEqual(command['quantity'],2)
                self.assertEqual(command['after']['buyer']['ore'],2)
                self.assertEqual(command['after']['buyer']['bread'],command['before']['buyer']['bread'])
                self.assertEqual(command['after']['seller']['bread'],command['before']['seller']['bread'])
                self.assertEqual(body['consent']['payload']['source_kind'],'operator')

    def test_unknown_commodity_rejected_without_bread_reservation(self):
        status,body=self.post({'id':'unknown-http','buyer':108186,'seller':108149,'commodity':'unregistered'})
        self.assertEqual(status,400,body);self.assertIn('market policy',body['error'])
        self.assertIsNone(self.world.active['pending']);self.assertIsNone(self.world.transition)

    def test_omitted_commodity_preserves_explicit_legacy_bread_default(self):
        status,body=self.post({'id':'bread-http','buyer':108186,'seller':108149})
        self.assertEqual(status,202,body);self.assertEqual(body['command']['commodity'],'bread')

    def test_unknown_fields_rejected_instead_of_silently_using_defaults(self):
        status,body=self.post({'id':'typo-http','buyer':108186,'seller':108149,'commmodity':'ore'})
        self.assertEqual(status,400,body);self.assertIn('fields',body['error'])
        self.assertIsNone(self.world.active['pending'])

    def test_malformed_commodity_rejected_before_trade_admission(self):
        status,body=self.post({'id':'bad-http','buyer':108186,'seller':108149,'commodity':None})
        self.assertEqual(status,400,body);self.assertIn('commodity',body['error'])
        self.assertIsNone(self.world.active['pending'])
