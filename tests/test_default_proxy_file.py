import os,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory() as home:
 os.environ.update(MUSE2API_HOME=home,MUSE2API_PROFILE_ROOT=home,MUSE2API_KEY='fixture-only')
 import app
 path=Path(home)/'proxy.json';proxy={'server':'socks5://127.0.0.1:9999','username':'fixture','password':'fixture'}
 path.write_text(json.dumps(proxy));os.environ['MUSE2API_DEFAULT_PROXY_FILE']=str(path)
 app.add_account(app.AccountRequest(cookies={'hatch_sess':'a'}))
 app.add_account(app.AccountRequest(cookies={'hatch_sess':'b'},proxy=None))
 assert app.store.accounts[-2]['proxy']==proxy
 assert not app.store.accounts[-1].get('proxy')
 print('PASS: omitted proxy inherits private default; explicit null remains direct')
