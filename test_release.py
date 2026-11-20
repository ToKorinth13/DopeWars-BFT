"""Release gates covering the complete command set and client failure cases."""
import copy,json,secrets,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from game import Game,new_game,RuleError,DRUGS,DURATIONS,WEAPONS
from lan import Server,rpc,PROTOCOL
request_uuid=uuid.uuid4

class EngineReleaseTests(unittest.TestCase):
 def test_strict_inputs_and_no_partial_mutation(self):
  g=new_game(seed=91);before=copy.deepcopy(g.s);rng=g.rng.getstate()
  for action,args in [('bag',{'tier':True}),('weapon',{'tier':1.0}),('buy',{'drug':'hash','qty':True}),('sell',{'drug':'missing','qty':1}),('buy',{'drug':'hash','qty':1,'cash':1}),('travel',{'city':'Odense','district':False})]:
   with self.assertRaises(RuleError):g.execute(action,**args)
   self.assertEqual(g.s,before);self.assertEqual(g.rng.getstate(),rng)
 def test_all_police_outcomes(self):
  for choice in ['fight','run','surrender','explain']:
   for roll in [0,.999]:
    g=new_game(seed=12);g.execute('buy',drug='hash',qty=2);g.s.update(police=True,green_card=True,weapon=3,health=100,clean=500)
    with patch.object(g.rng,'random',return_value=roll):g.execute('police',choice=choice)
    self.assertFalse(g.s['police']);self.assertEqual(g.s['clean'],500)
    if choice=='explain':self.assertFalse(g.s['green_card']);self.assertEqual(g.s['health'],100)
    if choice=='surrender' or roll>.9:self.assertEqual(g.used,0)
 def test_queue_cap_atomic_and_future_excluded(self):
  g=new_game(seed=12);g.s['black']=100000
  for _ in range(128):g.execute('wash',amount=10,tier=0)
  before=copy.deepcopy(g.s)
  with self.assertRaises(RuleError):g.execute('wash',amount=10,tier=0)
  self.assertEqual(g.s,before);self.assertEqual(g.score,-5500)
 def test_invariants_are_active_without_asserts(self):
  g=new_game();g.s['bag']=True
  with self.assertRaises(RuleError):g.check()
 def test_cost_basis_partial_sale_and_empty_stock(self):
  g=new_game(seed=12);g.s['black']=10000;market=g.s['markets'][g.s['city']][0]
  market['hash']=100;g.execute('buy',drug='hash',qty=2);market['hash']=200;g.execute('buy',drug='hash',qty=2)
  g.execute('sell',drug='hash',qty=1);self.assertEqual(g.s['cost']['hash'],450)
  g.execute('sell',drug='hash',qty=3);self.assertEqual(g.s['cost']['hash'],0)

class FullLanParity(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=Server(Path(self.tmp.name),port=0,bind='127.0.0.1');self.invite=self.server.invite('127.0.0.1');self.token=secrets.token_hex(32);self.other=secrets.token_hex(32)
  self.send('join',name='Owner',owner=self.server.session.s['owner']);self.send('join',token=self.other,name='Other');self.send('ready');self.send('ready',token=self.other);self.send('start')
  self.key=__import__('hashlib').sha256(self.token.encode()).hexdigest()
 def tearDown(self):self.server.close();self.tmp.cleanup()
 def send(self,op,token=None,**args):
  r=rpc(self.invite,dict(op=op,token=token or self.token,request_id=request_uuid().hex,**args));self.assertTrue(r['ok'],r);return r['view']
 def test_all_game_commands_identical_over_real_tls(self):
  from types import SimpleNamespace
  p=self.server.session.s['players'][self.key];p['state'].update(black=200000,clean=100000,health=50)
  local=self.server.session.game(p);seen=set();other_before=self.send('poll',token=self.other)['state']
  def execute(action,**args):
   revision=p['revision']
   with patch('game.uuid.uuid4',return_value=SimpleNamespace(hex='aabbccddeeff00112233445566778899')):
    local.execute(action,**args);self.send('command',revision=revision,action=action,args=args)
   self.assertEqual(p['state'],local.s,action);self.assertEqual(p['rng'],local.rng.getstate(),action);seen.add(action)
  execute('bank',kind='borrow',amount=1000)
  for kind in ['repay_black','repay_clean','to_black']:execute('bank',kind=kind,amount=100)
  execute('bag',tier=2);execute('weapon',tier=3);execute('heal')
  execute('buy',drug='hash',qty=30);execute('sell',drug='hash',qty=5)
  execute('hire',city='Aarhus',tier=2);mid=local.s['mules'][0]['id'];execute('dispatch',mid=mid,drug='hash',qty=5)
  execute('asset',tier=0);aid=local.s['assets'][0]['id'];execute('fund',aid=aid,amount=1000);execute('wash',amount=1000,tier=2)
  # Force the same policy encounter on both authoritative and local states.
  p['state']['police']=True;local.s['police']=True
  execute('police',choice='surrender')
  execute('travel',city='Randers',district=1)
  for _ in range(6):execute('wait')
  execute('dismiss',mid=mid);execute('sell_asset',aid=aid);execute('finish')
  self.assertEqual(seen,{'bank','bag','weapon','heal','buy','sell','hire','dispatch','asset','fund','wash','police','travel','wait','dismiss','sell_asset','finish'})
  self.assertEqual(self.send('poll',token=self.other)['state'],other_before)
 def test_slow_tls_peer_does_not_block_other_players(self):
  import socket,time
  sock=socket.create_connection(('127.0.0.1',self.server.port));start=time.monotonic()
  try:self.send('poll');self.assertLess(time.monotonic()-start,2)
  finally:sock.close()
 def test_poll_is_read_only(self):
  before=copy.deepcopy(self.server.session.s)
  for _ in range(4):self.send('poll')
  self.assertEqual(before,self.server.session.s)
 def test_31_lan_days_have_events_zero_spread_and_independent_opponent(self):
  p=self.server.session.s['players'][self.key];other=copy.deepcopy(self.send('poll',token=self.other)['state'])
  markets=controls=0
  for day in range(1,32):
   v=self.send('poll');cash=v['state']['black'];price=v['state']['markets'][v['state']['city']][v['state']['district']]['hash']
   if cash>=price:
    self.send('command',revision=p['revision'],action='buy',args=dict(drug='hash',qty=1))
    v=self.send('command',revision=p['revision'],action='sell',args=dict(drug='hash',qty=1))
    self.assertEqual(v['state']['black'],cash)
   for event in v['state']['day_events']:
    if event['kind']=='market':
     markets+=1;self.assertEqual(v['state']['markets'][v['state']['city']][v['state']['district']][event['drug']],event['price'])
    else:controls+=1
   if day<31:self.send('command',revision=p['revision'],action='wait',args={})
  self.assertGreaterEqual(markets,7);self.assertGreaterEqual(controls,5)
  self.assertEqual(self.send('poll',token=self.other)['state'],other)
 def test_restart_preserves_private_order(self):
  p=self.server.session.s['players'][self.key];p['state']['black']=5000
  self.send('command',revision=0,action='wash',args=dict(amount=1000,tier=0))
  private=copy.deepcopy(p['state']);self.server.close();self.server=Server(Path(self.tmp.name),port=0,bind='127.0.0.1');self.invite=self.server.invite('127.0.0.1')
  p=self.server.session.s['players'][self.key];self.assertEqual(p['state'],private);self.assertNotIn('ready',self.send('poll')['state']['washing'][0])

if __name__=='__main__':unittest.main()
