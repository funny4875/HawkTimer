import os, json, queue, threading, datetime, tkinter as tk
from tkinter import ttk, messagebox, filedialog
import calendar_service as service
from dateutil.relativedelta import relativedelta

def query_dates(start_text,end_text):
 try:
  start=datetime.date.fromisoformat(start_text.strip())
  end=datetime.date.fromisoformat(end_text.strip()) if end_text.strip() else start+relativedelta(months=1)
  if end<start:raise ValueError('結束日期不可早於開始日期。')
  after_end=end+datetime.timedelta(days=1)
  return (datetime.datetime.combine(start,datetime.time.min).astimezone(),datetime.datetime.combine(after_end,datetime.time.min).astimezone(),end)
 except (ValueError,OverflowError) as error:
  if str(error)=='結束日期不可早於開始日期。':raise
  raise ValueError('請輸入有效日期，格式為 YYYY-MM-DD。') from None

class CalendarUI:
 def __init__(self, app):
  self.app=app;self.queue=queue.Queue();self.busy=False;self.seen=set();self.last_summary='';self.last_error_time=None;self.partial_summary_date='';self.state_path=os.path.join(service.DIR,'state.json')
  try:
   with open(self.state_path,encoding='utf-8') as f:
    state=json.load(f);self.last_summary=state.get('summary','');self.seen=set(state.get('seen',[]))
  except (OSError,ValueError):pass
  app.root.after(1000,self.poll);app.root.after(250,self.process)
 def save_state(self):
  try:
   os.makedirs(service.DIR,exist_ok=True)
   with open(self.state_path,'w',encoding='utf-8') as f:json.dump({'summary':self.last_summary,'seen':list(self.seen)[-2000:]},f)
  except OSError as error:
   messagebox.showwarning('行事曆狀態儲存失敗',str(error),parent=self.app.root)
 def task(self,kind,fn):
  def work():
   try:self.queue.put((kind,fn(),None))
   except Exception as e:self.queue.put((kind,None,str(e)))
  threading.Thread(target=work,daemon=True).start()
 def settings(self):
  w=tk.Toplevel(self.app.root);w.title('Google 日曆設定');w.iconbitmap(self.app.icon_path);w.transient(self.app.root);w.configure(bg='#f4f6fa');w.geometry('670x460');w.minsize(600,410)
  header=tk.Frame(w,bg='#1d2337',padx=22,pady=16);header.pack(fill='x')
  tk.Label(header,text='Google 日曆',font=('Microsoft JhengHei',16,'bold'),fg='#f3d393',bg='#1d2337').pack(anchor='w')
  tk.Label(header,text='使用 iCal 非公開網址加入日曆',font=('Microsoft JhengHei',10),fg='#d8dfeb',bg='#1d2337').pack(anchor='w',pady=(4,0))
  f=ttk.Frame(w,padding=(22,16));f.pack(fill='both',expand=True)
  ttk.Label(f,text='已加入的日曆',font=('Microsoft JhengHei',11,'bold')).pack(anchor='w')
  listing=tk.Listbox(f,height=6,font=('Microsoft JhengHei',11),selectmode='browse',exportselection=False,relief='solid',borderwidth=1,selectbackground='#52658b',activestyle='none');listing.pack(fill='both',expand=True,pady=(8,8))
  def entries():return [('iCal',p,n) for p,n in service.feed_list()]+[('舊版 OAuth',p,n) for p,n in service.account_list()]
  def refresh():
   listing.delete(0,'end')
   for kind,path,name in entries():listing.insert('end',name+'（'+kind+'）')
  refresh()
  row=ttk.Frame(f);row.pack(fill='x')
  def remove():
   selected=listing.curselection();items=entries()
   if not selected or selected[0]>=len(items):messagebox.showinfo('選取日曆','請先選取要刪除的日曆。',parent=w);return
   _,path,name=items[selected[0]]
   if messagebox.askyesno('刪除日曆','確定刪除「'+name+'」在此電腦上的連結？',parent=w):
    try:os.remove(path);refresh()
    except OSError as e:messagebox.showerror('刪除失敗',str(e),parent=w)
  def add_ical():
   dialog=tk.Toplevel(w);dialog.title('新增 Google 日曆');dialog.iconbitmap(self.app.icon_path);dialog.transient(w);dialog.configure(bg='#f4f6fa');dialog.resizable(False,False)
   frame=ttk.Frame(dialog,padding=20);frame.pack(fill='both',expand=True)
   ttk.Label(frame,text='貼上 iCal 非公開網址',font=('Microsoft JhengHei',12,'bold')).grid(row=0,column=0,sticky='w')
   ttk.Label(frame,text='帳號名稱會從網址自動取得；網址會在此電腦加密保存。',wraplength=500).grid(row=1,column=0,sticky='w',pady=(6,10))
   url=tk.StringVar();entry=ttk.Entry(frame,textvariable=url,width=66,show='•');entry.grid(row=2,column=0,sticky='ew');entry.focus_set()
   def save_feed():
    try:service.add_feed(url.get());refresh();dialog.destroy()
    except Exception as e:messagebox.showerror('新增失敗',str(e),parent=dialog)
   buttons=ttk.Frame(frame);buttons.grid(row=3,column=0,sticky='e',pady=(14,0))
   ttk.Button(buttons,text='取消',command=dialog.destroy).pack(side='left',padx=4);ttk.Button(buttons,text='新增日曆',command=save_feed).pack(side='left',padx=4)
   dialog.bind('<Return>',lambda e:save_feed())
  ttk.Button(row,text='＋ 新增 iCal 日曆',command=add_ical).pack(side='left',padx=(0,8))
  ttk.Button(row,text='刪除選取的日曆',command=remove).pack(side='left')
  mobile=tk.BooleanVar(value=self.app.cfg.get('calendar_notify',False))
  def set_mobile():
   try:self.app.cfg['calendar_notify']=mobile.get();self.app.save()
   except OSError as error:messagebox.showwarning('設定儲存失敗',str(error),parent=w)
  ttk.Checkbutton(f,text='行程開始前 10 分鐘也發送手機通知',variable=mobile,command=set_mobile).pack(anchor='w',pady=(14,6))
  ttk.Button(f,text='查詢行程／空閒時段',command=self.query).pack(anchor='w')
 def query(self):
  w=tk.Toplevel(self.app.root);w.title('行程與時間區段查詢');w.iconbitmap(self.app.icon_path);w.geometry('720x500')
  f=ttk.Frame(w,padding=12);f.pack(fill='both',expand=True);today=datetime.date.today()
  start=tk.StringVar(value=today.isoformat());end=tk.StringVar(value='')
  ttk.Label(f,text='開始日期（YYYY-MM-DD）').grid(row=0,column=0,sticky='w');ttk.Entry(f,textvariable=start,width=14).grid(row=0,column=1,padx=5)
  ttk.Label(f,text='結束日期').grid(row=0,column=2);ttk.Entry(f,textvariable=end,width=14).grid(row=0,column=3,padx=5)
  ttk.Label(f,text='結束日期留白時，預設為開始日期的一個月後；查詢包含結束日期當天。').grid(row=1,column=0,columnspan=5,sticky='w',pady=(8,0))
  result=tk.Text(f,wrap='word');result.grid(row=2,column=0,columnspan=5,sticky='nsew',pady=10);f.rowconfigure(2,weight=1);f.columnconfigure(3,weight=1)
  def search():
   try:
    a,b,end_date=query_dates(start.get(),end.get())
    if not service.account_paths() and not service.feed_paths():raise ValueError('請先在設定中新增日曆或連結帳號。')
   except ValueError as e:messagebox.showwarning('查詢條件',str(e),parent=w);return
   span=f'查詢日期：{a.date().isoformat()} 至 {end_date.isoformat()}（包含結束日期）'
   button.config(state='disabled');result.delete('1.0','end');result.insert('end',span+'\n\n查詢中…')
   def fetch():
    try:return (w,result,button,span,service.events_between(a,b))
    except Exception as error:return (w,result,button,span,([], [str(error)]))
   self.task('query',fetch)
  button=ttk.Button(f,text='查詢',command=search);button.grid(row=0,column=4,padx=4)
 def show(self,title,lines):
  w=tk.Toplevel(self.app.root);w.title(title);w.iconbitmap(self.app.icon_path);w.attributes('-topmost',True);w.geometry('700x420')
  text=tk.Text(w,wrap='word',font=('Microsoft JhengHei',12));scroll=ttk.Scrollbar(w,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);text.insert('1.0',lines);text.configure(state='disabled')
 def poll(self):
  if not self.busy and (service.account_paths() or service.feed_paths()):
   self.busy=True
   now=datetime.datetime.now().astimezone();end=now+datetime.timedelta(days=7)
   self.task('poll',lambda:(now,service.events_between(now,end)))
  self.app.root.after(60000,self.poll)
 def process(self):
  try:
   while True:
    kind,value,error=self.queue.get_nowait()
    if kind=='add':
     if hasattr(self,'settings_window') and self.settings_window.winfo_exists():
      self.add_button.config(state='normal');self.refresh_accounts()
     if error:messagebox.showerror('帳號連結失敗',error,parent=self.app.root)
     else:messagebox.showinfo('帳號已連結',value,parent=self.app.root)
    elif kind=='query':
     if error:messagebox.showerror('查詢失敗',error,parent=self.app.root);continue
     w,result,button,span,(events,errors)=value
     if not w.winfo_exists():continue
     button.config(state='normal');result.delete('1.0','end')
     result.insert('end',span+'\n\n'+(('此區段有行程：\n\n'+'\n'.join(map(service.describe,events))) if events else ('無法確認空閒。' if errors else '此區段沒有行程。'))+('\n\n部分帳號查詢失敗：\n'+'\n'.join(errors) if errors else ''))
    elif kind=='poll':
     self.busy=False
     if error:
      now=datetime.datetime.now().astimezone()
      if not self.last_error_time or (now-self.last_error_time).total_seconds()>=3600:
       self.show('行事曆同步失敗',error);self.last_error_time=now
      continue
     _,(events,errors)=value;now=datetime.datetime.now().astimezone()
     if errors and (not self.last_error_time or (now-self.last_error_time).total_seconds()>=3600):
      self.show('行事曆同步失敗','以下帳號無法同步，提醒可能不完整：\n\n'+'\n'.join(errors));self.last_error_time=now
     elif not errors:self.last_error_time=None
     due=[]
     for event in events:
      seconds=(event['start']-now).total_seconds();key=event['id']+'|'+event['start'].isoformat()
      if not event['all_day'] and 0<seconds<=600 and key not in self.seen:
       due.append(event);self.seen.add(key)
     if due:
      msg='行程即將開始：\n\n'+'\n'.join(map(service.describe,due));self.show('行程提醒',msg)
      if self.app.cfg.get('calendar_notify',False):self.app.notify(False,msg)
      self.save_state()
     today=now.date().isoformat()
     if now.hour>=8 and self.last_summary!=today and (not errors or self.partial_summary_date!=today):
      body='\n'.join(map(service.describe,events)) if events else ('目前沒有取得行程。' if errors else '未來 7 天沒有行程。')
      if errors:body+='\n\n部分帳號同步失敗，清單可能不完整。'
      self.show('未來 7 天行程',body)
      if errors:self.partial_summary_date=today
      else:self.last_summary=today;self.save_state()
  except queue.Empty:pass
  finally:self.app.root.after(250,self.process)
