import os, json, base64, ctypes, uuid, datetime, threading
from ctypes import wintypes
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES=['https://www.googleapis.com/auth/calendar.readonly','https://www.googleapis.com/auth/userinfo.email','openid']
DIR=os.path.join(os.environ['APPDATA'],'HawkPomodoro','calendar')
class Blob(ctypes.Structure):
 _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_byte))]
def protect(data, decrypt=False):
 buf=ctypes.create_string_buffer(data); inp=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte))); out=Blob()
 crypt=ctypes.windll.crypt32; kernel=ctypes.windll.kernel32
 fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
 if not fn(ctypes.byref(inp),None,None,None,None,1,ctypes.byref(out)): raise ctypes.WinError()
 try:return ctypes.string_at(out.pbData,out.cbData)
 finally:kernel.LocalFree(out.pbData)
_write_lock=threading.Lock()
def write_private(path,obj):
 with _write_lock:_write_private(path,obj)
def _write_private(path,obj):
 os.makedirs(DIR,exist_ok=True)
 data=protect(json.dumps(obj,ensure_ascii=False).encode('utf-8'))
 tmp=path+'.tmp'
 with open(tmp,'wb') as f:f.write(data)
 os.replace(tmp,path)
def read_private(path):
 with open(path,'rb') as f:return json.loads(protect(f.read(),True).decode('utf-8'))
def import_client(path):
 with open(path,encoding='utf-8-sig') as f: data=json.load(f)
 client=data.get('installed')
 if not isinstance(client,dict) or not all(client.get(k) for k in ('client_id','client_secret','auth_uri','token_uri')):raise ValueError('請選擇 Google Cloud 的桌面應用程式 OAuth 用戶端 JSON。')
 if client['auth_uri']!='https://accounts.google.com/o/oauth2/auth' or client['token_uri']!='https://oauth2.googleapis.com/token':raise ValueError('OAuth 設定檔的 Google 授權網址不正確。')
 write_private(os.path.join(DIR,'client.dat'),data)
def account_paths():
 if not os.path.isdir(DIR):return []
 return [os.path.join(DIR,x) for x in sorted(os.listdir(DIR)) if x.startswith('account-') and x.endswith('.dat')]
def account_list():
 result=[]
 for path in account_paths():
  try:result.append((path,read_private(path)['email']))
  except Exception:result.append((path,'無法讀取的帳號'))
 return result
def add_account():
 config=read_private(os.path.join(DIR,'client.dat'))
 flow=InstalledAppFlow.from_client_config(config,SCOPES,autogenerate_code_verifier=True)
 cred=flow.run_local_server(port=0,open_browser=True,access_type='offline',prompt='consent',timeout_seconds=180)
 user=build('oauth2','v2',credentials=cred,cache_discovery=False).userinfo().get().execute()
 email=user['email']
 existing=next((p for p,e in account_list() if e.lower()==email.lower()),None)
 write_private(existing or os.path.join(DIR,'account-'+uuid.uuid4().hex+'.dat'),{'email':email,'credential':json.loads(cred.to_json())})
 return email
def load_credentials(path):
 account=read_private(path); c=Credentials.from_authorized_user_info(account['credential'],SCOPES)
 if not c.valid and c.refresh_token:
  c.refresh(Request());account['credential']=json.loads(c.to_json());write_private(path,account)
 if not c.valid:raise ValueError('授權已失效，請重新連結帳號。')
 return account['email'],c
_events_lock=threading.Lock()
def events_between(start,end):
 with _events_lock:return _events_between(start,end)
def _events_between(start,end):
 results=[];errors=[]
 for path,email in account_list():
  try:
   email,cred=load_credentials(path); service=build('calendar','v3',credentials=cred,cache_discovery=False)
   calendars=[]; token=None
   while True:
    page=service.calendarList().list(pageToken=token).execute();calendars.extend(page.get('items',[]));token=page.get('nextPageToken')
    if not token:break
   for cal in calendars:
    token=None
    while True:
     page=service.events().list(calendarId=cal['id'],timeMin=start.isoformat(),timeMax=end.isoformat(),singleEvents=True,orderBy='startTime',showDeleted=False,pageToken=token).execute()
     for ev in page.get('items',[]):
      if ev.get('status')=='cancelled':continue
      a=ev['start'];b=ev['end'];all_day='date' in a
      if all_day:
       begin=datetime.datetime.combine(datetime.date.fromisoformat(a['date']),datetime.time.min).astimezone();finish=datetime.datetime.combine(datetime.date.fromisoformat(b['date']),datetime.time.min).astimezone()
      else:
       begin=datetime.datetime.fromisoformat(a['dateTime'].replace('Z','+00:00')).astimezone();finish=datetime.datetime.fromisoformat(b['dateTime'].replace('Z','+00:00')).astimezone()
      results.append({'id':email+'|'+cal['id']+'|'+ev['id'],'account':email,'calendar':cal.get('summary',''),'title':ev.get('summary','（無標題）'),'start':begin,'end':finish,'all_day':all_day})
     token=page.get('nextPageToken')
     if not token:break
  except Exception as e:errors.append(email+': '+str(e))
 return sorted(results,key=lambda e:e['start']),errors
def describe(event):
 start=event['start'].strftime('%m/%d %H:%M');end=event['end'].strftime('%m/%d %H:%M')
 return f"{start}－{end}  {event['title']}（{event['account']}）"+(' [全天]' if event['all_day'] else '')
