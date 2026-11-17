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
 def test_dpapi(self):
  payload='測試'.encode();self.assertEqual(s.protect(s.protect(payload),True),payload)
 def test_multiple_calendars_and_partial_failure(self):
  now=datetime.datetime.now().astimezone()
  with patch.object(s,'account_list',return_value=[('a','a@example.com'),('b','b@example.com')]), patch.object(s,'load_credentials',side_effect=[('a@example.com',object()),ValueError('失效')]),patch.object(s,'build',return_value=Fake()):
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
  if now.hour<8:self.skipTest('summary is scheduled after 08:00 local time')
  ui,messages,notifications=self.make_ui([],mobile=True)
  self.assertEqual(messages[0][0],'未來 7 天行程');self.assertEqual(notifications,[])
 def test_failed_account_is_visible_and_does_not_mark_summary(self):
  ui,messages,_=self.make_ui([],errors=['account failed'])
  self.assertEqual(messages[0][0],'行事曆同步失敗');self.assertEqual(ui.last_summary,'')
