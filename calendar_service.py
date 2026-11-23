import os, json, base64, ctypes, uuid, datetime, threading
from ctypes import wintypes
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import httplib2
from google_auth_httplib2 import AuthorizedHttp
import urllib.request, urllib.parse, urllib.error, ssl, truststore
import icalendar, recurring_ical_events

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
 user=build('oauth2','v2',http=AuthorizedHttp(cred,http=httplib2.Http(timeout=20)),cache_discovery=False).userinfo().get().execute()
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

def feed_paths():
 if not os.path.isdir(DIR):return []
 return [os.path.join(DIR,x) for x in sorted(os.listdir(DIR)) if x.startswith('feed-') and x.endswith('.dat')]
def feed_list():
 result=[]
 for path in feed_paths():
  try:
   feed=read_private(path);result.append((path,feed_name(feed['url'])))
  except Exception:result.append((path,'無法讀取的日曆'))
 return result
def feed_name(url):
 parsed=urllib.parse.urlsplit(url.strip())
 if parsed.scheme!='https' or parsed.hostname!='calendar.google.com' or parsed.username or parsed.password or parsed.port not in (None,443) or not parsed.path.startswith('/calendar/ical/'):
  raise ValueError('請貼上 Google 日曆的 HTTPS iCal 網址。')
 parts=parsed.path.split('/')
 if len(parts)<5 or not parts[3]:raise ValueError('網址中找不到日曆帳號或識別碼。')
 identifier=urllib.parse.unquote(parts[3]).strip()
 if not identifier or any(ord(c)<32 for c in identifier):raise ValueError('網址中的日曆識別碼無效。')
 return identifier

def add_feed(url):
 url=url.strip();name=feed_name(url)
 for path,_ in feed_list():
  if read_private(path).get('url')==url:raise ValueError('此 iCal 網址已經加入。')
 path=os.path.join(DIR,'feed-'+uuid.uuid4().hex+'.dat')
 write_private(path,{'name':name,'url':url});return path
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def feed_events(path,start,end):
 feed=read_private(path);url=feed['url'];feed['name']=feed_name(url);parsed=urllib.parse.urlsplit(url)
 if parsed.scheme!='https' or parsed.hostname!='calendar.google.com' or parsed.username or parsed.password or parsed.port not in (None,443) or not parsed.path.startswith('/calendar/ical/'):
  raise ValueError('網址格式不正確。')
 opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
 try:
  with opener.open(urllib.request.Request(url,headers={'User-Agent':'HawkTimer/iCal'}),timeout=20) as response:
   data=response.read(10*1024*1024+1)
 except urllib.error.HTTPError as e:
  if e.code in (403,404):raise ValueError('無法讀取此網址（HTTP %s）。請確認是否使用「非公開網址 (iCal 格式)」。'%e.code) from None
  raise ValueError('無法讀取日曆（HTTP %s）。'%e.code) from None
 except (urllib.error.URLError,TimeoutError,OSError):raise ValueError('無法連接 Google 日曆，請檢查網路。') from None
 if len(data)>10*1024*1024:raise ValueError('日曆資料超過 10 MB。')
 try:
  cal=icalendar.Calendar.from_ical(data)
  if cal.name!='VCALENDAR':raise ValueError('不是日曆資料')
  entries=recurring_ical_events.of(cal).between(start,end)
  results=[]
  for item in entries:
   if item.name!='VEVENT' or str(item.get('STATUS','')).upper()=='CANCELLED':continue
   begin=item.decoded('DTSTART');finish=item.decoded('DTEND',None)
   all_day=isinstance(begin,datetime.date) and not isinstance(begin,datetime.datetime)
   if all_day:
    finish=finish or (begin+datetime.timedelta(days=1))
    begin=datetime.datetime.combine(begin,datetime.time.min).astimezone();finish=datetime.datetime.combine(finish,datetime.time.min).astimezone()
   else:
    if begin.tzinfo is None:begin=begin.astimezone()
    begin=begin.astimezone();finish=(finish or begin).astimezone()
   if begin>=end or finish<=start:continue
   ident=str(item.get('UID',''))+'|'+begin.isoformat()
   results.append({'id':os.path.basename(path)+'|'+ident,'account':feed['name'],'calendar':feed['name'],'title':str(item.get('SUMMARY','（無標題）')),'start':begin,'end':finish,'all_day':all_day})
  return results
 except Exception as e:raise ValueError('日曆資料解析失敗：'+type(e).__name__) from None

_events_lock=threading.Lock()
def events_between(start,end):
 with _events_lock:return _events_between(start,end)
def _events_between(start,end):
 results=[];errors=[]
 for path,email in account_list():
  try:
   email,cred=load_credentials(path); service=build('calendar','v3',http=AuthorizedHttp(cred,http=httplib2.Http(timeout=20)),cache_discovery=False)
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
 for path,name in feed_list():
  try:results.extend(feed_events(path,start,end))
  except Exception as e:errors.append(name+': '+str(e))
 return sorted(results,key=lambda e:e['start']),errors
def describe(event):
 def date_text(value):return value.strftime('%m/%d')+'('+'一二三四五六日'[value.weekday()]+')'
 start=event['start'];end=event['end']
 if event['all_day']:
  span=date_text(start) if start.date()==end.date() else date_text(start)+' ~'+date_text(end)
 elif start.date()!=end.date():span=date_text(start)+' ~'+date_text(end)
 else:span=date_text(start)+start.strftime('%H:%M')+'~'+end.strftime('%H:%M')
 return span+'  '+event['title']
