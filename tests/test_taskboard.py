import json, os, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
CLI=Path(__file__).resolve().parents[1]/'skills'/'taskboard'/'scripts'/'taskboard'
HARNESS_VARS=('CODEX_THREAD_ID','CLAUDE_CODE_SESSION_ID','OPENCODE_SESSION_ID','DSH_SESSION_ID','PI_SESSION_ID','ANTIGRAVITY_SESSION_ID','GEMINI_SESSION_ID','HERMES_SESSION_ID','GOOSE_SESSION_ID','OPENCLAW_SESSION_ID','OPENCLAW_SESSION_KEY','QODER_SESSION_ID','CURSOR_SESSION_ID','CURSOR_TRACE_ID','KIRO_SESSION_ID','TASKBOARD_SID','TASKBOARD_HARNESS')
class TaskTest(unittest.TestCase):
 def runcli(self,cwd,*args,env=None,ok=True):
  e=os.environ.copy()
  for k in HARNESS_VARS:e.pop(k,None)
  if env:e.update(env)
  p=subprocess.run([sys.executable,str(CLI),*args],cwd=cwd,env=e,text=True,capture_output=True)
  if ok and p.returncode:self.fail(p.stderr+p.stdout)
  if not ok and not p.returncode:self.fail('unexpected success')
  return p
 def test_task_flow_and_actor_history_without_session_lifecycle(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init');env={'CODEX_THREAD_ID':'real-thread-1'}
   a=self.runcli(d,'add','Build parser').stdout.strip();b=self.runcli(d,'add','Write tests').stdout.strip()
   self.runcli(d,'dep','add',b,'--needs',a)
   self.runcli(d,'doing',a,env=env)
   self.assertIn('IN_PROGRESS',self.runcli(d,'show',a).stdout);self.assertIn('WAITING',self.runcli(d,'show',b).stdout)
   self.runcli(d,'done',a,env=env);self.assertIn('READY',self.runcli(d,'show',b).stdout)
   self.runcli(d,'doing',b,env=env);self.runcli(d,'done',b,env=env)
   self.assertIn('real-thread-1',self.runcli(d,'show',a).stdout)
   self.assertFalse((Path(d)/'.taskboard'/'sessions').exists())
   self.assertIn('task_done', (Path(d)/'.taskboard'/'events.jsonl').read_text())
 def test_handoff_returns_task_to_ready(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init');a=self.runcli(d,'add','A').stdout.strip()
   self.runcli(d,'doing',a,env={'CODEX_THREAD_ID':'sender'})
   self.runcli(d,'handoff',a,'--to','receiver',env={'CODEX_THREAD_ID':'sender'})
   self.assertIn('READY',self.runcli(d,'show',a).stdout)
   self.runcli(d,'doing',a,env={'CODEX_THREAD_ID':'receiver'})
   self.assertIn('IN_PROGRESS',self.runcli(d,'show',a).stdout)
   self.assertIn('receiver',self.runcli(d,'show',a).stdout)
 def test_cycle_and_missing_sid(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init');a=self.runcli(d,'add','A').stdout.strip();b=self.runcli(d,'add','B').stdout.strip()
   self.runcli(d,'dep','add',a,'--needs',b);self.runcli(d,'dep','add',b,'--needs',a,ok=False);self.runcli(d,'doing',a,ok=False)
 def test_sync_preserves_user_content_and_lists_in_progress(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init');a=self.runcli(d,'add','A').stdout.strip();self.runcli(d,'doing',a,env={'CODEX_THREAD_ID':'s1'})
   p=Path(d)/'AGENTS.md';p.write_text('# My rules\n\nKeep this.\n');self.runcli(d,'sync')
   txt=p.read_text();self.assertIn('Keep this.',txt);self.assertIn('In Progress',txt);self.assertIn('ALWAYS load and follow the `taskboard` skill before starting any work',txt);self.assertIn(a,txt)
 def test_custom_harness_identity(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init');p=Path(d)/'.taskboard/config.json';c=json.loads(p.read_text());c['harness_env']['my-harness']=['MY_SID'];p.write_text(json.dumps(c))
   a=self.runcli(d,'add','A').stdout.strip();self.runcli(d,'doing',a,env={'MY_SID':'actual-session'})
   self.assertIn('actual-session',self.runcli(d,'search','actual-session').stdout)
 def test_new_harness_identities(self):
  cases=[
   ('opencode',{'OPENCODE_SESSION_ID':'ses_oc_1'},'ses_oc_1'),
   ('deepseek-harness',{'DSH_SESSION_ID':'dsh_1'},'dsh_1'),
   ('pi',{'PI_SESSION_ID':'pi_1'},'pi_1'),
   ('antigravity',{'ANTIGRAVITY_SESSION_ID':'agy_1'},'agy_1'),
   ('antigravity',{'GEMINI_SESSION_ID':'gem_1'},'gem_1'),
   ('hermes',{'HERMES_SESSION_ID':'hermes_1'},'hermes_1'),
   ('goose',{'GOOSE_SESSION_ID':'goose_1'},'goose_1'),
   ('openclaw',{'OPENCLAW_SESSION_ID':'claw_1'},'claw_1'),
   ('openclaw',{'OPENCLAW_SESSION_KEY':'claw_key_1'},'claw_key_1'),
   ('qoder',{'QODER_SESSION_ID':'qoder_1'},'qoder_1'),
   ('cursor',{'CURSOR_SESSION_ID':'cur_1'},'cur_1'),
   ('cursor',{'CURSOR_TRACE_ID':'cur_tr_1'},'cur_tr_1'),
   ('kiro',{'KIRO_SESSION_ID':'kiro_1'},'kiro_1'),
  ]
  for harness,env,sid in cases:
   with tempfile.TemporaryDirectory() as d:
    self.runcli(d,'init');a=self.runcli(d,'add','A').stdout.strip()
    self.runcli(d,'doing',a,env=env)
    out=self.runcli(d,'show',a).stdout
    self.assertIn(f'{harness}:{sid}',out)
 def test_wait_and_dep_add_wait(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   a=self.runcli(d,'add','Prereq A').stdout.strip()
   b=self.runcli(d,'add','Child B').stdout.strip()
   def finish_a():
    time.sleep(0.15)
    self.runcli(d,'done',a,env={'OPENCODE_SESSION_ID':'oc-1'})
   th=threading.Thread(target=finish_a)
   th.start()
   p=self.runcli(d,'dep','add',b,'--needs',a,'--wait','--timeout','3')
   th.join()
   self.assertIn('Dependency added',p.stdout)
   self.assertIn('Done: '+a,p.stdout)
   self.assertIn('READY',self.runcli(d,'show',b).stdout)
 def test_wait_ready_and_blocked_and_timeout(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   a=self.runcli(d,'add','Prereq A').stdout.strip()
   b=self.runcli(d,'add','Child B').stdout.strip()
   self.runcli(d,'dep','add',b,'--needs',a)
   p_to=self.runcli(d,'wait',b,'--ready','--timeout','0.15',ok=False)
   self.assertIn('timed out',p_to.stderr)
   def finish_a():
    time.sleep(0.15)
    self.runcli(d,'done',a,env={'PI_SESSION_ID':'pi-1'})
   th=threading.Thread(target=finish_a)
   th.start()
   p_ready=self.runcli(d,'wait',b,'--ready','--timeout','3')
   th.join()
   self.assertIn('Ready: '+b,p_ready.stdout)
   c=self.runcli(d,'add','Task C').stdout.strip()
   self.runcli(d,'block',c,'--reason','missing token',env={'DSH_SESSION_ID':'dsh-1'})
   p_blk=self.runcli(d,'wait',c,'--timeout','1',ok=False)
   self.assertIn('blocked: missing token',p_blk.stderr)
 def test_search_bm25f_filters_cjk_fuzzy_and_json(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   a=self.runcli(d,'add','Fix OAuth login pageKey bug').stdout.strip()
   b=self.runcli(d,'add','修复用户登录鉴权问题').stdout.strip()
   c=self.runcli(d,'add','Legacy OAuth cleanup').stdout.strip()
   # Add Markdown body note to task b
   bp=Path(d)/'.taskboard'/'tasks'/(b+'.md')
   bp.write_text(bp.read_text()+'\n需要检查回调地址白名单\n')
   self.runcli(d,'doing',a,env={'OPENCODE_SESSION_ID':'oc-9'})
   self.runcli(d,'block',c,'--reason','waiting vendor key',env={'PI_SESSION_ID':'pi-9'})
   # Multi-word AND + negation
   out=self.runcli(d,'search','oauth','login','-legacy','--tasks-only').stdout
   self.assertIn(a,out);self.assertNotIn(c,out)
   # camelCase split
   self.assertIn(a,self.runcli(d,'search','page','key','--tasks-only').stdout)
   # CJK bigram & Markdown body search
   self.assertIn(b,self.runcli(d,'search','登录','--tasks-only').stdout)
   self.assertIn(b,self.runcli(d,'search','白名单','--tasks-only').stdout)
   # Structured filters without free-text query
   f_out=self.runcli(d,'search','status:BLOCKED','harness:pi').stdout
   self.assertIn(c,f_out);self.assertNotIn(a,f_out)
   # Event JSON keys should not false-match
   self.assertIn('No matches',self.runcli(d,'search','--events-only','--exact','from_sid').stdout)
   # Fuzzy fallback catches typo, --exact rejects it
   self.assertIn(a,self.runcli(d,'search','logni','--tasks-only').stdout)
   self.assertIn('No matches',self.runcli(d,'search','logni','--tasks-only','--exact').stdout)
   # JSON output
   j=json.loads(self.runcli(d,'search','oauth','--json','--limit','2').stdout)
   self.assertEqual(len(j['results']),2)
   self.assertIn('score',j['results'][0])
 def test_auto_sync_on_state_change_and_config_override(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   agents=Path(d)/'AGENTS.md'
   self.assertTrue(agents.exists())
   self.assertIn('ALWAYS load and follow the `taskboard` skill',agents.read_text())
   a=self.runcli(d,'add','Auto sync task').stdout.strip()
   self.assertTrue(a.startswith('t-'))
   self.assertNotIn('\n',a)
   agents=Path(d)/'AGENTS.md'
   self.assertTrue(agents.exists())
   self.assertIn('Ready Tasks',agents.read_text())
   self.assertIn(a,agents.read_text())
   self.runcli(d,'doing',a,env={'OPENCODE_SESSION_ID':'oc-auto'})
   self.assertIn('In Progress',agents.read_text())
   cfg_p=Path(d)/'.taskboard'/'config.json'
   c=json.loads(cfg_p.read_text());c['context_file']=['AGENTS.md','CLAUDE.md'];cfg_p.write_text(json.dumps(c))
   self.runcli(d,'done',a,env={'OPENCODE_SESSION_ID':'oc-auto'})
   claude=Path(d)/'CLAUDE.md'
   self.assertTrue(claude.exists())
   self.assertIn('completed',claude.read_text())
   self.assertIn('completed',agents.read_text())
 def test_global_and_project_config_precedence(self):
  gcfg=CLI.parent/'config.json'
  try:
   gcfg.write_text(json.dumps({'context_file':['GLOBAL.md'],'harness_env':{'global-h':['GLOBAL_SID']}}))
   with tempfile.TemporaryDirectory() as d:
    self.runcli(d,'init')
    a=self.runcli(d,'add','Global cfg task').stdout.strip()
    self.runcli(d,'doing',a,env={'GLOBAL_SID':'g-1'})
    self.assertIn('global-h:g-1',self.runcli(d,'show',a).stdout)
    self.assertTrue((Path(d)/'GLOBAL.md').exists())
    # Project config overrides global context_file while preserving global harness_env
    pcfg=Path(d)/'.taskboard'/'config.json'
    c=json.loads(pcfg.read_text());c['context_file']=['LOCAL.md'];pcfg.write_text(json.dumps(c))
    self.runcli(d,'done',a,env={'GLOBAL_SID':'g-1'})
    self.assertTrue((Path(d)/'LOCAL.md').exists())
  finally:
   gcfg.unlink(missing_ok=True)
 def test_note_and_show_and_done_handoff_notes(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   a=self.runcli(d,'add','Implement auth','--desc','Support JWT and refresh tokens').stdout.strip()
   self.runcli(d,'doing',a,env={'OPENCODE_SESSION_ID':'oc-1'})
   self.runcli(d,'note',a,'Added JWT middleware',env={'OPENCODE_SESSION_ID':'oc-1'})
   self.runcli(d,'handoff',a,'--to','pi-2','--to-harness','pi','--note','Need refresh token tests',env={'OPENCODE_SESSION_ID':'oc-1'})
   self.runcli(d,'doing',a,env={'PI_SESSION_ID':'pi-2'})
   self.runcli(d,'done',a,'--note','All tests passing',env={'PI_SESSION_ID':'pi-2'})
   shown=self.runcli(d,'show',a).stdout
   self.assertIn('Notes:',shown)
   self.assertIn('Support JWT and refresh tokens',shown)
   self.assertIn('Added JWT middleware',shown)
   self.assertIn('Need refresh token tests',shown)
   self.assertIn('All tests passing',shown)
   self.assertIn(a,self.runcli(d,'search','JWT','middleware').stdout)
 def test_bin_wrapper_unblock_list_status_and_guardrails(self):
  bin_cli=Path(__file__).resolve().parents[1]/'bin'/'taskboard'
  with tempfile.TemporaryDirectory() as d:
   e=os.environ.copy()
   for k in HARNESS_VARS:e.pop(k,None)
   p=subprocess.run([sys.executable,str(bin_cli),'--version'],cwd=d,env=e,text=True,capture_output=True)
   self.assertEqual(p.returncode,0);self.assertIn('0.1.0',p.stdout)
   self.runcli(d,'init')
   a=self.runcli(d,'add','Task A').stdout.strip()
   b=self.runcli(d,'add','Task B').stdout.strip()
   self.runcli(d,'dep','add',b,'--needs',a)
   # Ambiguous harness fails without --harness, succeeds with --harness
   amb={'CODEX_THREAD_ID':'c1','OPENCODE_SESSION_ID':'o1'}
   self.assertIn('Ambiguous',self.runcli(d,'doing',a,env=amb,ok=False).stderr)
   self.runcli(d,'doing',a,env=amb,ok=False)
   self.runcli(d,'doing',a,'--harness','opencode',env=amb)
   # Cannot claim WAITING task
   self.runcli(d,'doing',b,env={'PI_SESSION_ID':'p1'},ok=False)
   # Block & unblock task B -> returns to WAITING since A is not DONE
   self.runcli(d,'block',b,'--reason','hold',env={'PI_SESSION_ID':'p1'})
   self.assertIn('BLOCKED',self.runcli(d,'show',b).stdout)
   self.runcli(d,'unblock',b)
   self.assertIn('WAITING',self.runcli(d,'show',b).stdout)
   # Complete A -> B becomes READY; list hides DONE unless --all
   self.runcli(d,'done',a,env={'OPENCODE_SESSION_ID':'o1'})
   self.assertNotIn(a,self.runcli(d,'list').stdout)
   self.assertIn(a,self.runcli(d,'list','--all').stdout)
   self.assertIn('DONE',self.runcli(d,'status').stdout)
   # Cannot claim DONE task
   self.runcli(d,'doing',a,env={'OPENCODE_SESSION_ID':'o1'},ok=False)
   # TASKBOARD_HARNESS + TASKBOARD_SID explicit override
   self.runcli(d,'doing',b,env={'TASKBOARD_HARNESS':'custom-ci','TASKBOARD_SID':'ci-99'})
   self.assertIn('custom-ci:ci-99',self.runcli(d,'show',b).stdout)
   # Path traversal in context_file rejected
   pcfg=Path(d)/'.taskboard'/'config.json'
   c=json.loads(pcfg.read_text());c['context_file']=['../escape.md'];pcfg.write_text(json.dumps(c))
   self.assertIn('inside project root',self.runcli(d,'sync',ok=False).stderr)
 def test_wait_multiple_and_prereq_blocked_and_already_done(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   a=self.runcli(d,'add','A').stdout.strip()
   b=self.runcli(d,'add','B').stdout.strip()
   c=self.runcli(d,'add','C').stdout.strip()
   self.runcli(d,'done',a,env={'PI_SESSION_ID':'p1'})
   # Already DONE returns immediately
   self.assertIn('Done: '+a,self.runcli(d,'wait',a,'--timeout','1').stdout)
   # Wait for multiple tasks concurrently
   def finish_b():
    time.sleep(0.15)
    self.runcli(d,'done',b,env={'PI_SESSION_ID':'p1'})
   th=threading.Thread(target=finish_b);th.start()
   out=self.runcli(d,'wait',a,b,'--timeout','3').stdout
   th.join()
   self.assertIn(f'Done: {a}, {b}',out)
   # wait --ready fails fast if prerequisite becomes BLOCKED
   d_task=self.runcli(d,'add','D').stdout.strip()
   self.runcli(d,'dep','add',d_task,'--needs',c)
   self.runcli(d,'block',c,'--reason','upstream broken',env={'PI_SESSION_ID':'p1'})
   err=self.runcli(d,'wait',d_task,'--ready','--timeout','1',ok=False).stderr
   self.assertIn('upstream broken',err)
 def test_search_or_phrases_limit_and_auto_sync_disable(self):
  with tempfile.TemporaryDirectory() as d:
   self.runcli(d,'init')
   pcfg=Path(d)/'.taskboard'/'config.json'
   c=json.loads(pcfg.read_text());c['auto_sync']=False;pcfg.write_text(json.dumps(c));(Path(d)/'AGENTS.md').unlink(missing_ok=True)
   a=self.runcli(d,'add','Fix OAuth login flow').stdout.strip()
   b=self.runcli(d,'add','Setup Redis cache').stdout.strip()
   d2=self.runcli(d,'add','Login via OAuth callback').stdout.strip()
   # auto_sync: false does not create AGENTS.md, but context/dry-run still prints preview
   self.assertFalse((Path(d)/'AGENTS.md').exists())
   self.assertIn('Shared Task Board',self.runcli(d,'context').stdout)
   self.assertFalse((Path(d)/'AGENTS.md').exists())
   # OR query
   or_out=self.runcli(d,'search','redis','OR','flow','--tasks-only').stdout
   self.assertIn(a,or_out);self.assertIn(b,or_out)
   # Exact quoted phrase
   ph_out=self.runcli(d,'search','"OAuth login"','--tasks-only').stdout
   self.assertIn(a,ph_out);self.assertNotIn(d2,ph_out)
   # Limit truncation & --limit 0
   lim_out=self.runcli(d,'search','oauth','--tasks-only','--limit','1').stdout
   self.assertIn('more matches',lim_out)
   all_out=self.runcli(d,'search','oauth','--tasks-only','--limit','0').stdout
   self.assertNotIn('more matches',all_out);self.assertIn(a,all_out);self.assertIn(d2,all_out)
 def test_version_and_no_lifecycle_commands(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertIn('0.1.0',self.runcli(d,'--version').stdout)
   self.runcli(d,'init')
   for cmd in ('start','stop','start-session','conclude-session'):
    self.runcli(d,cmd,ok=False)
if __name__=='__main__':unittest.main()
