"""Integration-only browser smoke test for independently submitted scheduling controls."""
import base64,json,os,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine import MuseEngine

def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

with tempfile.TemporaryDirectory(prefix='muse-scheduling-ui-') as home:
    home=Path(home);port=free_port();cdp_port=free_port()
    fixture=home/'fixture_app.py'
    fixture.write_text('''import sys,time\nimport app as module\nfor n in range(5):module.store.add_account({'hatch_sess':'fixture-'+str(n)},'QA-'+str(n+1))\nmodule.store.update_account(module.store.accounts[0]['id'],video_cooldown_until=time.time()+900)\nmodule._check_update_sync=lambda *a,**k:{'local_version':'1.6.10','remote_version':'1.6.10','local_sha':'fixture','remote_sha':'fixture','up_to_date':True,'has_update':False,'repo_url':'https://github.com/ALight777/muse2api','repo_ref':'codex/alight','managed_deployment':True,'recent_commits':[]}\napp=module.app\n''')
    env={**os.environ,'PYTHONPATH':str(ROOT),'MUSE2API_HOME':str(home),'MUSE2API_PROFILE_ROOT':str(home/'server-profile'),'MUSE2API_KEY':'qa-only'}
    log=(home/'server.log').open('w')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','fixture_app:app','--app-dir',str(home),'--host','127.0.0.1','--port',str(port),'--lifespan','off','--no-access-log'],env=env,stdout=log,stderr=log)
    cfg=SimpleNamespace(chromium=shutil.which('chromium') or shutil.which('google-chrome'),cdp_port=cdp_port,home_dir=str(Path.home()),extra_path='',profile_dir=str(home/'browser'),data_dir=str(home),download_dir=str(home/'downloads'))
    Path(cfg.download_dir).mkdir();engine=MuseEngine(cfg)
    try:
        engine.start();engine.page=engine._open_page();page=engine.page
        def wait(expression):
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                try:
                    if page.js(expression):return
                except Exception:pass
                time.sleep(.1)
            raise AssertionError('UI did not reach expected state: '+expression)
        page.send('Page.navigate',{'url':f'http://127.0.0.1:{port}'})
        wait("!!document.querySelector('#key')")
        page.js("document.querySelector('#key').value='qa-only';saveKey()")
        wait("document.querySelector('#schedulerSummary').textContent.includes('可用账号 5')")
        page.js("(async()=>{document.querySelector('#schedulerMode').value='auto';document.querySelector('#schedulerAuto').value='3';await saveScheduler();return true})()")
        wait("document.querySelector('#schedulerSummary').textContent.includes('生效上限 3')")
        page.js("(async()=>{document.querySelector('#generationQueueTimeout').value='0';await saveGenerationQueue();return true})()")
        page.js("(async()=>{document.querySelector('#videoHealthSeconds').value='0';await saveVideoHealth();return true})()")
        wait("document.querySelector('#videoHealthSummary').textContent.includes('5')")
        page.send('Page.reload',{})
        wait("document.querySelector('#schedulerMode').value==='auto' && document.querySelector('#generationQueueTimeout').value==='0' && document.querySelector('#videoHealthSeconds').value==='0'")
        page.js("(async()=>{document.querySelector('#videoHealthSeconds').value='900';await saveVideoHealth();return true})()")
        wait("!!document.querySelector('#videoCooldowns button')")
        page.js("document.querySelector('#videoCooldowns button').click()")
        wait("document.querySelector('#videoHealthSummary').textContent.includes('5') && !document.querySelector('#videoCooldowns button')")
        page.js("(async()=>{document.querySelector('#schedulerMode').value='manual';document.querySelector('#schedulerManual').value='2';await saveScheduler();return true})()")
        wait("document.querySelector('#schedulerSummary').textContent.includes('生效上限 2')")
        page.js('toggleRepoPanel()');wait("document.querySelector('#btnRepoPull').disabled")
        page.js("document.querySelector('#langSel').value='en';setLang('en')")
        wait("document.querySelector('#schedulerPanel').innerText.includes('Concurrency mode')")
        out=Path(os.environ.get('QA_ARTIFACT_DIR',home));out.mkdir(parents=True,exist_ok=True)
        page.js("document.querySelector('#schedulerPanel').scrollIntoView({block:'start'})")
        (out/'scheduler-integrated.png').write_bytes(base64.b64decode(page.send('Page.captureScreenshot',{'format':'png'})['data']))
        print('PASS: all three independent panels save, persist across reload, update routing state, reset cooldown and retain managed-version controls in Chinese/English')
    finally:
        engine.stop();server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
        log.close()
