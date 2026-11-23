import os, unittest, datetime
from unittest.mock import patch
import calendar_service as s
class Request:
 def __init__(self,data):self.data=data
 def execute(self):return self.data
class Resource:
 def __init__(self,kind):self.kind=kind
 def list(self,**kw):
  if self.kind=='cal':return Request({'items':[{'id':'one','summary':'工作'},{'id':'two','summary':'私人'}]})
  if kw['calendarId']=='one':return Request({'items':[{'id':'1','summary':'會議','start':{'dateTime':'2026-11-17T10:00:00+08:00'},'end':{'dateTime':'2026-11-17T11:00:00+08:00'}},{'id':'2','summary':'全天','start':{'date':'2026-11-18'},'end':{'date':'2026-11-19'}}]})
  return Request({'items':[]})
class Fake:
 def calendarList(self):return Resource('cal')
 def events(self):return Resource('event')
class Tests(unittest.TestCase):
 def test_describe_shows_weekday_for_both_dates(self):
  event={'start':datetime.datetime(2026,11,23,23,0),'end':datetime.datetime(2026,11,24,1,0),'title':'測試','account':'測試日曆','all_day':False}
  self.assertIn('11/23（星期一） 23:00－11/24（星期二） 01:00',s.describe(event))
 def test_dpapi(self):
  payload='測試'.encode();self.assertEqual(s.protect(s.protect(payload),True),payload)
 def test_multiple_calendars_and_partial_failure(self):
  now=datetime.datetime.now().astimezone()
  with patch.object(s,'feed_list',return_value=[]), patch.object(s,'account_list',return_value=[('a','a@example.com'),('b','b@example.com')]), patch.object(s,'load_credentials',side_effect=[('a@example.com',object()),ValueError('失效')]),patch.object(s,'build',return_value=Fake()):
   events,errors=s.events_between(now,now+datetime.timedelta(days=7))
  self.assertEqual([x['title'] for x in events],['會議','全天']);self.assertTrue(events[1]['all_day']);self.assertIn('b@example.com',errors[0])
if __name__=='__main__':unittest.main()

class SchedulerTests(unittest.TestCase):
 def make_ui(self,events,errors=(),mobile=False,summary=''):
  import queue, types, calendar_ui
  ui=calendar_ui.CalendarUI.__new__(calendar_ui.CalendarUI)
  now=datetime.datetime.now().astimezone()
  ui.queue=queue.Queue();ui.queue.put(('poll',(now,(events,list(errors))),None));ui.busy=True;ui.seen=set();ui.last_summary=summary;ui.last_error_time=None;ui.partial_summary_date=''
  messages=[];notifications=[]
  ui.app=types.SimpleNamespace(root=types.SimpleNamespace(after=lambda *args:None),cfg={'calendar_notify':mobile},notify=lambda *args:notifications.append(args))
  ui.show=lambda title,text:messages.append((title,text));ui.save_state=lambda:None
  ui.process();return ui,messages,notifications
 def test_reminder_once_and_optional_mobile(self):
  now=datetime.datetime.now().astimezone();event={'id':'abc','title':'測試','account':'a','calendar':'x','start':now+datetime.timedelta(minutes=9),'end':now+datetime.timedelta(minutes=30),'all_day':False}
  ui,messages,notifications=self.make_ui([event],mobile=True,summary=now.date().isoformat())
  self.assertEqual([x[0] for x in messages],['行程提醒']);self.assertEqual(len(notifications),1)
  ui.queue.put(('poll',(now,([event],[])),None));ui.process();self.assertEqual(len(messages),1)
 def test_summary_never_mobile(self):
  now=datetime.datetime.now().astimezone()
  if (now.hour,now.minute)<(8,20):self.skipTest('summary is scheduled after 08:20 local time')
  ui,messages,notifications=self.make_ui([],mobile=True)
  self.assertEqual(messages[0][0],'未來 30 天行程');self.assertEqual(notifications,[])
 def test_failed_account_is_visible_and_does_not_mark_summary(self):
  ui,messages,_=self.make_ui([],errors=['account failed'])
  self.assertEqual(messages[0][0],'行事曆同步失敗');self.assertEqual(ui.last_summary,'')

class AuthorizationTests(unittest.TestCase):
 def test_independent_accounts_and_replace_existing(self):
  import tempfile, json
  from types import SimpleNamespace
  class Cred:
   def to_json(self):return json.dumps({'refresh_token':'synthetic-token'})
  class Flow:
   def run_local_server(self,**kw):return Cred()
  class Userinfo:
   def __init__(self,email):self.email=email
   def userinfo(self):return self
   def get(self):return self
   def execute(self):return {'email':self.email}
  with tempfile.TemporaryDirectory() as directory, patch.object(s,'DIR',directory), patch.object(s.InstalledAppFlow,'from_client_config',return_value=Flow()), patch.object(s,'AuthorizedHttp',return_value=object()), patch.object(s,'build',side_effect=[Userinfo('a@example.com'),Userinfo('b@example.com'),Userinfo('a@example.com')]):
   s.write_private(os.path.join(directory,'client.dat'),{'installed':{'client_id':'test'}})
   for _ in range(3):s.add_account()
   accounts=s.account_list();self.assertEqual(sorted(email for _,email in accounts),['a@example.com','b@example.com'])
   for path,_ in accounts:
    with open(path,'rb') as stream:self.assertNotIn(b'synthetic-token',stream.read())
    self.assertEqual(s.read_private(path)['credential']['refresh_token'],'synthetic-token')
 def test_network_client_has_timeout(self):
  now=datetime.datetime.now().astimezone()
  with patch.object(s,'feed_list',return_value=[]),patch.object(s,'account_list',return_value=[('a','a@example.com')]),patch.object(s,'load_credentials',return_value=('a@example.com',object())),patch.object(s.httplib2,'Http') as http,patch.object(s,'AuthorizedHttp',return_value=object()),patch.object(s,'build',return_value=Fake()):
   s.events_between(now,now+datetime.timedelta(days=1));http.assert_called_once_with(timeout=20)

class IcalTests(unittest.TestCase):
 def test_recurrence_exclusion_and_encrypted_feed(self):
  import tempfile
  ics=b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nBEGIN:VEVENT\r\nUID:repeat-1\r\nDTSTART:20261117T090000Z\r\nDTEND:20261117T100000Z\r\nRRULE:FREQ=DAILY;COUNT=3\r\nEXDATE:20261118T090000Z\r\nSUMMARY:Daily Test\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:day-1\r\nDTSTART;VALUE=DATE:20261118\r\nDTEND;VALUE=DATE:20261119\r\nSUMMARY:All day\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
  class Resp:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return ics
  class Opener:
   def open(self,*args,**kwargs):return Resp()
  with tempfile.TemporaryDirectory() as d,patch.object(s,'DIR',d),patch.object(s.urllib.request,'build_opener',return_value=Opener()):
   path=s.add_feed('https://calendar.google.com/calendar/ical/test%40example.com/private-abc/basic.ics')
   now=datetime.datetime(2026,11,17,tzinfo=datetime.timezone.utc);events=s.feed_events(path,now,now+datetime.timedelta(days=4))
   self.assertEqual(s.feed_list()[0][1],'test@example.com');self.assertEqual(len(events),3);self.assertEqual(sum(e['title']=='Daily Test' for e in events),2);self.assertEqual(sum(e['all_day'] for e in events),1)
   with open(path,'rb') as f:self.assertNotIn(b'private-abc',f.read())
 def test_invalid_host_rejected(self):
  with self.assertRaises(ValueError):s.add_feed('https://example.org/calendar/ical/test.ics')

class QueryDateTests(unittest.TestCase):
 def test_blank_end_is_calendar_month_with_last_day_clamping(self):
  from calendar_ui import query_dates
  start,end,shown=query_dates('2024-01-31','')
  self.assertEqual((start.date(),shown,end.date()),(datetime.date(2024,1,31),datetime.date(2024,2,29),datetime.date(2024,3,1)))
  start,end,shown=query_dates('2025-12-15','')
  self.assertEqual((shown,end.date()),(datetime.date(2026,1,15),datetime.date(2026,1,16)))
 def test_selected_end_day_is_included_and_same_day_allowed(self):
  from calendar_ui import query_dates
  start,end,shown=query_dates('2026-11-17','2026-11-17')
  self.assertEqual(start.date(),datetime.date(2026,11,17));self.assertEqual(end.date(),datetime.date(2026,11,18))
 def test_invalid_and_reversed_dates(self):
  from calendar_ui import query_dates
  for start,end in [('',''),('2026-02-30',''),('2026-11-17','2026-11-16'),('2026-11-17','9999-12-31')]:
   with self.subTest(start=start,end=end),self.assertRaises(ValueError):query_dates(start,end)


class SummarySettingsTests(unittest.TestCase):
 def test_defaults_and_custom_values(self):
  from calendar_ui import summary_settings
  self.assertEqual(summary_settings({}),(8,20,30))
  self.assertEqual(summary_settings({'calendar_summary_time':'09:45','calendar_summary_days':14}),(9,45,14))
  self.assertEqual(summary_settings({'calendar_summary_time':'25:00','calendar_summary_days':0}),(8,20,30))
