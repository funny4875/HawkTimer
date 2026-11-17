import os, json, queue, threading, datetime, tkinter as tk
from tkinter import ttk, messagebox, filedialog
import calendar_service as service

class CalendarUI:
 def __init__(self, app):
  self.app=app;self.queue=queue.Queue();self.busy=False;self.seen=set();self.last_summary='';self.last_error_time=None;self.partial_summary_date='';self.state_path=os.path.join(service.DIR,'state.json')
  try:
   with open(self.state_path,encoding='utf-8') as f:
    state=json.load(f);self.last_summary=state.get('summary','');self.seen=set(state.get('seen',[]))
  except (OSError,ValueError):pass
  app.root.after(1000,self.poll);app.root.after(250,self.process)
 def save_state(self):
  os.makedirs(service.DIR,exist_ok=True)
  with open(self.state_path,'w',encoding='utf-8') as f:json.dump({'summary':self.last_summary,'seen':list(self.seen)[-2000:]},f)
 def task(self,kind,fn):
  def work():
   try:self.queue.put((kind,fn(),None))
   except Exception as e:self.queue.put((kind,None,str(e)))
  threading.Thread(target=work,daemon=True).start()
 def settings(self):
  w=tk.Toplevel(self.app.root);w.title('Google Calendar 設定');w.iconbitmap(self.app.root.iconbitmap());w.geometry('570x350')
  f=ttk.Frame(w,padding=12);f.pack(fill='both',expand=True)
  ttk.Label(f,text='先匯入 Google Cloud 桌面應用程式 OAuth JSON，然後逐一登入帳號。',wraplength=540).pack(anchor='w')
  listing=tk.Listbox(f,height=7);listing.pack(fill='both',expand=True,pady=8)
  def refresh():
   listing.delete(0,'end')
   for path,email in service.account_list():listing.insert('end',email)
  refresh()
  row=ttk.Frame(f);row.pack(fill='x')
  def load():
   path=filedialog.askopenfilename(parent=w,title='選擇 OAuth 用戶端設定檔',filetypes=[('JSON','*.json')])
   if path:
    try:service.import_client(path);messagebox.showinfo('匯入完成','OAuth 設定檔已安全儲存。',parent=w)
    except Exception as e:messagebox.showerror('匯入失敗',str(e),parent=w)
  def add():
   if not os.path.exists(os.path.join(service.DIR,'client.dat')):messagebox.showwarning('尚未匯入','請先匯入 OAuth 設定檔。',parent=w);return
   add_btn.config(state='disabled');self.task('add',service.add_account)
  def remove():
   sel=listing.curselection();accounts=service.account_list()
   if sel and sel[0]<len(accounts) and messagebox.askyesno('移除帳號','確定移除本機儲存的 '+accounts[sel[0]][1]+'？',parent=w):
    try:os.remove(accounts[sel[0]][0]);refresh()
    except OSError as e:messagebox.showerror('移除失敗',str(e),parent=w)
  ttk.Button(row,text='匯入 OAuth 設定檔',command=load).pack(side='left',padx=2)
  add_btn=ttk.Button(row,text='新增／重新授權帳號',command=add);add_btn.pack(side='left',padx=2)
  ttk.Button(row,text='移除帳號',command=remove).pack(side='left',padx=2)
  mobile=tk.BooleanVar(value=self.app.cfg.get('calendar_notify',False))
  def set_mobile():self.app.cfg['calendar_notify']=mobile.get();self.app.save()
  ttk.Checkbutton(f,text='行程開始前 10 分鐘也發送手機通知',variable=mobile,command=set_mobile).pack(anchor='w',pady=8)
  ttk.Button(f,text='查詢行程／空閒時段',command=self.query).pack(anchor='w')
  self.settings_window=w;self.refresh_accounts=refresh;self.add_button=add_btn
 def query(self):
  w=tk.Toplevel(self.app.root);w.title('行程與時間區段查詢');w.iconbitmap(self.app.root.iconbitmap());w.geometry('720x500')
  f=ttk.Frame(w,padding=12);f.pack(fill='both',expand=True);now=datetime.datetime.now().astimezone()
  start=tk.StringVar(value=now.strftime('%Y-%m-%d %H:%M'));end=tk.StringVar(value=(now+datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M'))
  ttk.Label(f,text='開始（YYYY-MM-DD HH:MM）').grid(row=0,column=0,sticky='w');ttk.Entry(f,textvariable=start,width=20).grid(row=0,column=1,padx=5)
  ttk.Label(f,text='結束').grid(row=0,column=2);ttk.Entry(f,textvariable=end,width=20).grid(row=0,column=3,padx=5)
  result=tk.Text(f,wrap='word');result.grid(row=2,column=0,columnspan=5,sticky='nsew',pady=10);f.rowconfigure(2,weight=1);f.columnconfigure(3,weight=1)
  def search():
   try:
    a=datetime.datetime.strptime(start.get().strip(),'%Y-%m-%d %H:%M').astimezone();b=datetime.datetime.strptime(end.get().strip(),'%Y-%m-%d %H:%M').astimezone()
    if a>=b:raise ValueError('結束時間必須晚於開始時間。')
    if not service.account_list():raise ValueError('請先在設定中連結帳號。')
   except ValueError as e:messagebox.showwarning('查詢條件',str(e),parent=w);return
   button.config(state='disabled');result.delete('1.0','end');result.insert('end','查詢中…')
   self.task('query',lambda:(w,result,button,service.events_between(a,b)))
  button=ttk.Button(f,text='查詢',command=search);button.grid(row=0,column=4,padx=4)
 def show(self,title,lines):
  w=tk.Toplevel(self.app.root);w.title(title);w.iconbitmap(self.app.root.iconbitmap());w.attributes('-topmost',True);w.geometry('700x420')
  text=tk.Text(w,wrap='word',font=('Microsoft JhengHei',12));scroll=ttk.Scrollbar(w,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);text.insert('1.0',lines);text.configure(state='disabled')
 def poll(self):
  if not self.busy and service.account_paths():
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
     w,result,button,(events,errors)=value
     if not w.winfo_exists():continue
     button.config(state='normal');result.delete('1.0','end')
     result.insert('end',(('此區段有行程：\n\n'+'\n'.join(map(service.describe,events))) if events else ('無法確認空閒。' if errors else '此區段沒有行程。'))+('\n\n部分帳號查詢失敗：\n'+'\n'.join(errors) if errors else ''))
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
  self.app.root.after(250,self.process)
