import os, sys, json, time, math, threading, urllib.request, re, winsound, random, ssl, truststore, queue, pystray
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageSequence
BASE=getattr(sys,'_MEIPASS',os.path.dirname(os.path.abspath(__file__)))
ICON=os.path.join(BASE,'icon.ico' if getattr(sys,'frozen',False) else 'assets/icon.ico')
CONFIG_DIR=os.path.join(os.environ.get('APPDATA',os.path.expanduser('~')),'HawkPomodoro')
CONFIG=os.path.join(CONFIG_DIR,'settings.json')
MESSAGE_FILE=os.path.join(os.path.dirname(sys.executable) if getattr(sys,'frozen',False) else BASE,'message.txt')
DEFAULT={'minutes':25,'seconds':0,'topic':'your-ntfy-topic','notify':True,'sound':True,'topmost':True,'x':None,'y':None,'gif':'','idle_gif':'','window_scale':100,'character_scale':100,'messages':['時間到！休息一下。','辛苦了，起來活動一下！','專注完成，該喝水囉！']}
KEY='#ff00ff'
APP_VERSION='1.2.0'
RELEASE_API='https://api.github.com/repos/funny4875/HawkTimer/releases/latest'
def read_config():
 try:
  with open(CONFIG,encoding='utf-8') as f: d=json.load(f)
  return {**DEFAULT,**{k:v for k,v in d.items() if k in DEFAULT}}
 except (OSError,ValueError,TypeError):return DEFAULT.copy()
def parse_messages(content):
 parts=re.split(r'(?m)^[ \t]*========[ \t]*\r?$',content)
 return [part.strip('\r\n') for part in parts if part.strip()]
def read_messages(cfg):
 try:
  with open(MESSAGE_FILE,encoding='utf-8-sig') as f: messages=parse_messages(f.read())
  if not messages: raise ValueError('message.txt 沒有任何訊息')
  return messages
 except FileNotFoundError:
  messages=cfg.get('messages') or DEFAULT['messages']
  with open(MESSAGE_FILE,'w',encoding='utf-8') as f: f.write('\n========\n'.join(messages)+'\n')
  return messages

def send_notification(topic, message):
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',topic):raise ValueError('主題格式不正確')
 req=urllib.request.Request('https://ntfy.sh/'+topic,data=message.encode('utf-8'),headers={'Priority':'5','Title':'Pomodoro','Cache':'no','Content-Type':'text/plain; charset=utf-8'},method='POST')
 with urllib.request.urlopen(req,timeout=12,context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as response:
  if response.status!=200:raise RuntimeError('HTTP '+str(response.status))
def version_tuple(value):
 match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',value or '')
 return tuple(map(int,match.groups())) if match else None

def get_latest_release():
 req=urllib.request.Request(RELEASE_API,headers={'Accept':'application/vnd.github+json','User-Agent':'HawkTimer/'+APP_VERSION})
 with urllib.request.urlopen(req,timeout=10,context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as response:
  data=json.load(response)
 version=version_tuple(data.get('tag_name'))
 if not version or data.get('draft') or data.get('prerelease'):raise ValueError('GitHub 版本資訊無效')
 tag='v'+'.'.join(map(str,version));filename='HawkTimer-'+'.'.join(map(str,version))+'-x64.msi'
 expected='https://github.com/funny4875/HawkTimer/releases/download/'+tag+'/'+filename
 if version<=version_tuple(APP_VERSION):return None
 if not any(asset.get('name')==filename and asset.get('browser_download_url')==expected for asset in data.get('assets',[])):
  raise ValueError('新版本尚未提供預期的 MSI 安裝檔')
 return ('.'.join(map(str,version)),expected)

def load_frames(path, size, upscale=False):
 frames=[]; durations=[]
 with Image.open(path) as im:
  for frame in ImageSequence.Iterator(im):
   rgba=frame.convert('RGBA')
   if upscale:
    factor=min(size[0]/rgba.width,size[1]/rgba.height);rgba=rgba.resize((max(1,round(rgba.width*factor)),max(1,round(rgba.height*factor))),Image.Resampling.LANCZOS)
   else:rgba.thumbnail(size,Image.Resampling.LANCZOS)
   bg=Image.new('RGBA',rgba.size,(255,0,255,255)); bg.alpha_composite(rgba)
   frames.append(ImageTk.PhotoImage(bg.convert('RGB'))); durations.append(max(40,int(frame.info.get('duration',100) or 100)))
 if not frames:raise ValueError('圖片沒有畫格')
 return frames,durations
class App:
 def __init__(self):
  self.cfg=read_config(); self.root=tk.Tk(); self.root.title('HawkTimer 鷹眼計時'); self.root.iconbitmap(ICON);  self.root.overrideredirect(True); self.root.configure(bg=KEY); self.root.wm_attributes('-transparentcolor',KEY); self.root.attributes('-topmost',bool(self.cfg['topmost']))
  x=self.cfg['x']; y=self.cfg['y']; self.root.geometry('360x480'+(f'+{x}+{y}' if x is not None and y is not None and x>=0 and y>=0 else '+100+100'))
  self.running=False; self.end=0; self.remaining=int(self.cfg['minutes'])*60+int(self.cfg.get('seconds',0)); self.alarm=None
  self.tray_icon=None;self.tray_hidden=False;self.tray_starting=False;self.tray_events=queue.Queue()
  self.update_events=queue.Queue();self.update_checking=False;self.pending_update=None
  self.canvas=tk.Canvas(self.root,width=360,height=385,bg=KEY,highlightthickness=0); self.canvas.pack()
  self.idle_item=self.canvas.create_image(180,190); self.idle_job=None; self.set_idle(self.cfg.get('idle_gif',''));  self.canvas.bind('<ButtonPress-1>',self.drag_start); self.canvas.bind('<B1-Motion>',self.drag_move); self.canvas.bind('<Button-3>',self.popup)
  box=tk.Frame(self.root,bg='#171927',highlightbackground='#d4ad65',highlightthickness=2); box.pack(fill='x',padx=4)
  self.label=tk.Label(box,font=('Microsoft JhengHei',25,'bold'),fg='#f2d392',bg='#171927',cursor='hand2'); self.label.pack();self.label.bind('<Button-1>',self.edit_time);self.edit_entry=None
  row=tk.Frame(box,bg='#171927'); row.pack(pady=(0,6))
  self.btn=tk.Button(row,text='開始',width=5,command=self.toggle); self.btn.pack(side='left',padx=2)
  for text,cmd in [('重設',self.reset),('文字檔',self.open_messages),('設定',self.settings),('縮小',self.minimize_to_tray),('結束',self.close)]:tk.Button(row,text=text,width=5,command=cmd).pack(side='left',padx=2)
  self.menu=tk.Menu(self.root,tearoff=0)
  for label,cmd in [('縮小至系統匣',self.minimize_to_tray),('設定',self.settings),('檢查更新',lambda:self.check_updates(True)),('開啟文字檔',self.open_messages),('預覽提醒動畫',lambda:self.show_alarm(False)),('測試手機通知',lambda:self.notify(True)),('結束',self.close)]:self.menu.add_command(label=label,command=cmd)
  self.update_window_size();self.root.bind('<Button-3>',self.popup); self.update_label(); self.root.after(100,self.tick);self.root.after(100,self.process_tray_events);self.root.after(100,self.process_update_events);self.root.after(2000,self.check_updates)
 def check_updates(self,manual=False):
  if self.update_checking:return
  self.update_checking=True
  def worker():
   try:self.update_events.put(('result',manual,get_latest_release()))
   except Exception as error:self.update_events.put(('error',manual,str(error)))
  threading.Thread(target=worker,daemon=True).start()
 def process_update_events(self):
  try:
   while True:
    kind,manual,result=self.update_events.get_nowait();self.update_checking=False
    if kind=='error':
     if manual:messagebox.showwarning('檢查更新失敗','目前無法檢查更新：'+result,parent=self.root)
    elif result:self.pending_update=result
    elif manual:messagebox.showinfo('檢查更新',f'目前已是最新版本（{APP_VERSION}）。',parent=self.root)
  except queue.Empty:pass
  if self.pending_update and not self.tray_hidden and not self.tray_starting and not (self.alarm and self.alarm.winfo_exists()) and self.root.winfo_ismapped():
   version,url=self.pending_update;self.pending_update=None
   if messagebox.askyesno('發現新版 HawkTimer',f'目前版本：{APP_VERSION}\n最新版本：{version}\n\n是否下載新版 MSI？\n下載後請先關閉 HawkTimer，再開啟安裝檔。',parent=self.root):
    try:os.startfile(url)
    except OSError as error:messagebox.showerror('無法開啟下載',str(error),parent=self.root)
  self.root.after(250,self.process_update_events)
 def minimize_to_tray(self):
  if self.tray_hidden or self.tray_starting:return
  if self.edit_entry is not None:self.cancel_time_edit()
  try:
   with Image.open(ICON) as source:tray_image=source.convert('RGBA').copy()
   self.tray_starting=True
   def action(name):
    def callback(icon,item):self.tray_events.put((name,icon))
    return callback
   icon=pystray.Icon('HawkTimer',tray_image,'HawkTimer 鷹眼計時',pystray.Menu(pystray.MenuItem('顯示計時器',action('show'),default=True),pystray.MenuItem('結束程式',action('exit'))))
   self.tray_icon=icon
   def setup(instance):
    try:instance.visible=True;self.tray_events.put(('ready',instance))
    except Exception as e:self.tray_events.put(('error',(instance,str(e))))
   icon.run_detached(setup=setup)
  except Exception as e:
   self.tray_starting=False;self.tray_icon=None;messagebox.showerror('無法縮小至系統匣',str(e),parent=self.root)
 def process_tray_events(self):
  try:
   while True:
    event,data=self.tray_events.get_nowait()
    if event=='error':
     icon,error=data
     if icon is self.tray_icon:
      self.tray_starting=False;self.tray_icon=None;icon.stop();messagebox.showerror('無法縮小至系統匣',error,parent=self.root)
    elif data is self.tray_icon:
     if event=='ready':self.tray_starting=False;self.tray_hidden=True;self.root.withdraw()
     elif event=='show':self.restore_from_tray()
     elif event=='exit':self.close();return
  except queue.Empty:pass
  self.root.after(100,self.process_tray_events)
 def restore_from_tray(self):
  self.tray_hidden=False
  icon=self.tray_icon;self.tray_icon=None
  if icon:icon.stop()
  if self.alarm and self.alarm.winfo_exists():self.alarm.lift()
  else:self.root.deiconify();self.root.lift()
 def update_window_size(self):
  window_factor=self.cfg.get('window_scale',100)/100
  figure_factor=self.cfg.get('character_scale',100)/100
  width=max(320,round(360*window_factor),round(350*figure_factor)+10)
  height=max(round(385*window_factor),round(380*figure_factor)+5)
  self.canvas.configure(width=width,height=height);self.canvas.coords(self.idle_item,width//2,height//2)
  self.root.geometry(f'{width}x{height+95}')
 def set_idle(self,path):
  if self.idle_job: self.root.after_cancel(self.idle_job); self.idle_job=None
  factor=self.cfg.get('character_scale',100)/100;size=(round(350*factor),round(380*factor))
  try: self.mainframes,self.maindurations=load_frames(path or os.path.join(BASE,'mihawk_idle.gif'),size,upscale=True)
  except Exception as e:
   messagebox.showwarning('常駐動畫載入失敗',f'{e}\n改用預設動畫。',parent=self.root)
   self.mainframes,self.maindurations=load_frames(os.path.join(BASE,'mihawk_idle.gif'),size,upscale=True)
  self.hatframes,self.hatdurations=load_frames(os.path.join(BASE,'mihawk_hat.gif'),size,upscale=True) if not path else ([],[])
  def animate(index=0, cycles=0, hat=False):
   frames=self.hatframes if hat else self.mainframes
   durations=self.hatdurations if hat else self.maindurations
   self.canvas.itemconfigure(self.idle_item,image=frames[index]);next_index=index+1
   if next_index>=len(frames):
    next_index=0
    if hat: hat=False;cycles=0
    else:
     cycles+=1
     if cycles>=2 and self.hatframes: hat=True
   self.idle_job=self.root.after(durations[index],lambda:animate(next_index,cycles,hat))
  animate()
 def open_messages(self):
  try:
   if not os.path.exists(MESSAGE_FILE):read_messages(self.cfg)
   os.startfile(MESSAGE_FILE)
  except (OSError,ValueError,UnicodeError) as e:messagebox.showerror('無法開啟文字檔',str(e),parent=self.root)
 def drag_start(self,e):self.drag=(e.x_root-self.root.winfo_x(),e.y_root-self.root.winfo_y())
 def drag_move(self,e):self.root.geometry(f'+{max(0,e.x_root-self.drag[0])}+{max(0,e.y_root-self.drag[1])}')
 def popup(self,e):self.menu.tk_popup(e.x_root,e.y_root); return 'break'
 def save(self):
  self.cfg['x']=self.root.winfo_x(); self.cfg['y']=self.root.winfo_y(); os.makedirs(CONFIG_DIR,exist_ok=True); tmp=CONFIG+'.tmp'
  with open(tmp,'w',encoding='utf-8') as f:json.dump(self.cfg,f,ensure_ascii=False,indent=2)
  os.replace(tmp,CONFIG)
 def update_label(self):
  s=max(0,math.ceil(self.remaining)); self.label.config(text=f'{s//60:02d}:{s%60:02d}')
 def edit_time(self,event=None):
  if self.edit_entry is not None:return
  self.edit_was_running=self.running;self.edit_previous_text=self.btn.cget('text')
  if self.running:
   self.remaining=max(0,self.end-time.monotonic());self.running=False;self.btn.config(text='繼續')
  current=max(0,math.ceil(self.remaining));self.label.pack_forget()
  self.edit_entry=tk.Entry(self.label.master,font=('Microsoft JhengHei',23,'bold'),justify='center',width=8,fg='#f2d392',bg='#303346',insertbackground='white')
  self.edit_entry.insert(0,f'{current//60:02d}:{current%60:02d}');self.edit_entry.pack(before=self.btn.master)
  self.edit_entry.bind('<Return>',self.apply_time_edit);self.edit_entry.bind('<Escape>',self.cancel_time_edit);self.btn.config(text='確定',command=self.apply_time_edit)
  self.edit_entry.focus_set();self.edit_entry.selection_range(0,'end')
 def apply_time_edit(self,event=None):
  if self.edit_entry is None:return
  value=self.edit_entry.get().strip();match=re.fullmatch(r'(\d{1,4}):(\d{1,2})',value)
  if not match or int(match.group(2))>59 or not 1<=int(match.group(1))*60+int(match.group(2))<=86400:
   self.edit_entry.focus_set();messagebox.showwarning('時間格式錯誤','請輸入 分:秒，例如 25:00 或 0:30，範圍為 1 秒至 1440 分鐘。',parent=self.root);return 'break'
  minutes,seconds=map(int,match.groups());self.cfg.update(minutes=minutes,seconds=seconds)
  entry=self.edit_entry;self.edit_entry=None;entry.destroy();self.label.pack(before=self.btn.master);self.btn.config(command=self.toggle);self.reset()
  try:self.save()
  except OSError as e:messagebox.showwarning('設定儲存失敗',str(e),parent=self.root)
  return 'break'
 def cancel_time_edit(self,event=None):
  if self.edit_entry is None:return
  entry=self.edit_entry;self.edit_entry=None;entry.destroy();self.label.pack(before=self.btn.master);self.btn.config(command=self.toggle);self.update_label()
  if self.edit_was_running:self.toggle()
  else:self.btn.config(text=self.edit_previous_text)
  return 'break'
 def toggle(self):
  if self.edit_entry is not None:return
  if self.running:self.remaining=max(0,self.end-time.monotonic());self.running=False;self.btn.config(text='繼續')
  else:
   if self.remaining<=0:self.remaining=int(self.cfg['minutes'])*60+int(self.cfg.get('seconds',0))
   self.end=time.monotonic()+self.remaining;self.running=True;self.btn.config(text='暫停')
  self.update_label()
 def reset(self):self.running=False;self.remaining=int(self.cfg['minutes'])*60+int(self.cfg.get('seconds',0));self.btn.config(text='開始');self.update_label()
 def tick(self):
  if self.running:
   self.remaining=max(0,self.end-time.monotonic());self.update_label()
   if self.remaining<=0:
    self.running=False;self.btn.config(text='開始')
    try: message=random.choice(read_messages(self.cfg))
    except (OSError, ValueError, UnicodeError) as e:
     messagebox.showwarning('訊息讀取失敗',str(e),parent=self.root); message=random.choice(self.cfg.get('messages') or DEFAULT['messages'])
    self.show_alarm(True,message)
    if self.cfg['notify']:self.notify(False,message)
  self.root.after(100,self.tick)
 def notify(self,manual,message=None):
  if message is None:
   try: message=random.choice(read_messages(self.cfg))
   except (OSError, ValueError, UnicodeError) as e: messagebox.showwarning('訊息讀取失敗',str(e),parent=self.root);return
  topic=self.cfg['topic']
  def worker():
   try:
    send_notification(topic,message)
    if manual:self.root.after(0,lambda:messagebox.showinfo('手機通知','已送到伺服器，請確認手機是否響鈴。',parent=self.root))
   except Exception as e:
    msg=str(e);self.root.after(0,lambda:messagebox.showwarning('手機通知失敗',msg,parent=self.root))
  threading.Thread(target=worker,daemon=True).start()
 def settings(self):
  w=tk.Toplevel(self.root);w.title('HawkTimer 設定');w.iconbitmap(ICON);w.transient(self.root);w.attributes('-topmost',True);w.resizable(False,False)
  f=ttk.Frame(w,padding=15);f.grid()
  minutes=tk.StringVar(value=str(self.cfg['minutes']));seconds=tk.StringVar(value=str(self.cfg.get('seconds',0)));topic=tk.StringVar(value=self.cfg['topic']);gif=tk.StringVar(value=self.cfg['gif']);idle=tk.StringVar(value=self.cfg.get('idle_gif',''));window_scale=tk.StringVar(value=str(self.cfg.get('window_scale',100)));character_scale=tk.StringVar(value=str(self.cfg.get('character_scale',100)));notify=tk.BooleanVar(value=self.cfg['notify']);sound=tk.BooleanVar(value=self.cfg['sound']);top=tk.BooleanVar(value=self.cfg['topmost'])
  for r,(label,var) in enumerate([('專注時間（分鐘）',minutes),('ntfy 主題',topic),('提醒 GIF / 圖片',gif),('常駐 GIF / 圖片',idle)]):
   ttk.Label(f,text=label).grid(row=r,column=0,sticky='w',pady=4);ttk.Entry(f,textvariable=var,width=38).grid(row=r,column=1,sticky='ew')
  ttk.Label(f,text='秒').grid(row=0,column=2,sticky='e');ttk.Entry(f,textvariable=seconds,width=5).grid(row=0,column=3,sticky='w')
  def browse(var):
   p=filedialog.askopenfilename(parent=w,title='選擇 GIF 或圖片',filetypes=[('圖片','*.gif *.png *.jpg *.jpeg *.webp'),('所有檔案','*.*')])
   if p:var.set(p)
  for r,var in [(2,gif),(3,idle)]:
   ttk.Button(f,text='選擇檔案',command=lambda v=var:browse(v)).grid(row=r,column=2,padx=4);ttk.Button(f,text='使用預設',command=lambda v=var:v.set('')).grid(row=r,column=3)
  for r,label,var,low,high in [(4,'視窗大小（%）',window_scale,85,160),(5,'人物大小（%）',character_scale,50,150)]:
   ttk.Label(f,text=label).grid(row=r,column=0,sticky='w',pady=4);ttk.Spinbox(f,from_=low,to=high,increment=5,textvariable=var,width=8).grid(row=r,column=1,sticky='w')
  for r,(label,var) in enumerate([('時間到發送手機通知',notify),('播放電腦提示音',sound),('計時器置頂',top)],6):ttk.Checkbutton(f,text=label,variable=var).grid(row=r,column=0,columnspan=3,sticky='w')
  ttk.Label(f,text='提醒文字（支援換行，以獨立一行 ======== 分隔）').grid(row=9,column=0,columnspan=4,sticky='w',pady=(10,2))
  text=tk.Text(f,width=55,height=7);text.grid(row=10,column=0,columnspan=4)
  try:
   with open(MESSAGE_FILE,encoding='utf-8-sig') as src: content=src.read()
  except FileNotFoundError: content='\n========\n'.join(self.cfg.get('messages') or DEFAULT['messages'])
  except (OSError, UnicodeError) as e: messagebox.showerror('訊息讀取失敗',str(e),parent=w);w.destroy();return
  text.insert('1.0',content)
  def apply():
   try:
    m=int(minutes.get());sec=int(seconds.get());ws=int(window_scale.get());cs=int(character_scale.get());t=topic.get().strip();p=gif.get().strip();idlepath=idle.get().strip();content=text.get('1.0','end-1c');messages=parse_messages(content)
    if not (0<=m<=1440 and 0<=sec<=59 and 1<=m*60+sec<=86400):raise ValueError('請設定 1 秒至 1440 分鐘，秒數請輸入 0 至 59。')
    if not 85<=ws<=160 or not 50<=cs<=150:raise ValueError('視窗大小須為 85 至 160%，人物大小須為 50 至 150%。')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',t):raise ValueError('ntfy 主題格式不正確。')
    if not messages:raise ValueError('請至少輸入一句提醒文字。')
    for image_path in (p,idlepath):
     if image_path:
      with Image.open(image_path) as im: im.seek(0);im.load()
    with open(MESSAGE_FILE,'w',encoding='utf-8') as dest: dest.write(content)
   except Exception as e:messagebox.showerror('設定錯誤',str(e),parent=w);return
   changed=(m,sec)!=(self.cfg['minutes'],self.cfg.get('seconds',0));self.cfg.update(minutes=m,seconds=sec,topic=t,gif=p,idle_gif=idlepath,window_scale=ws,character_scale=cs,messages=messages,notify=notify.get(),sound=sound.get(),topmost=top.get());self.root.attributes('-topmost',top.get());self.update_window_size();self.set_idle(idlepath);self.save()
   if changed:self.reset()
   w.destroy()
  ttk.Button(f,text='儲存',command=apply).grid(row=11,column=3,pady=10)
 def show_alarm(self,actual,message=None):
  if message is None:
   try: message=random.choice(read_messages(self.cfg))
   except (OSError,ValueError,UnicodeError) as e: messagebox.showwarning('訊息讀取失敗',str(e),parent=self.root);return
  if self.alarm and self.alarm.winfo_exists():self.alarm.destroy()
  path=self.cfg['gif'] or os.path.join(BASE,'mihawk_action.gif')
  try:frames,durations=load_frames(path,(350,350))
  except Exception as e:
   messagebox.showwarning('動畫載入失敗',f'{e}\n改用預設動畫。',parent=self.root);frames,durations=load_frames(os.path.join(BASE,'mihawk_action.gif'),(350,350))
  w=tk.Toplevel(self.root);self.alarm=w;self.root.withdraw()
  def restore_idle(event):
   if event.widget is w and self.root.winfo_exists():
    self.alarm=None
    if not self.tray_hidden:self.root.deiconify()
  w.bind('<Destroy>',restore_idle);w.overrideredirect(True);w.configure(bg=KEY);w.wm_attributes('-transparentcolor',KEY);w.attributes('-topmost',True)
  height=min(w.winfo_screenheight()-30, max(440, 400+sum(max(1,math.ceil(len(line)/18)) for line in message.split('\n'))*25));x=max(0,w.winfo_screenwidth()-380);y=max(0,(w.winfo_screenheight()-height)//2);w.geometry(f'360x{height}+{x}+{y}')
  c=tk.Canvas(w,width=360,height=height,bg=KEY,highlightthickness=0);c.pack();item=c.create_image(180,175,image=frames[0]);c.create_rectangle(8,355,352,height-2,fill='#171927',outline='#d4ad65',width=2)
  textframe=tk.Frame(w,bg='#171927');c.create_window(18,365,anchor='nw',window=textframe,width=324,height=height-400)
  text=tk.Text(textframe,wrap='word',font=('Microsoft JhengHei',14,'bold'),fg='white',bg='#171927',relief='flat',borderwidth=0,highlightthickness=0,cursor='arrow');scroll=ttk.Scrollbar(textframe,orient='vertical',command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(side='left',fill='both',expand=True);text.configure(state='disabled')
  c.create_text(180,height-16,text='點擊圖片關閉提醒',fill='#e5cf9c',font=('Microsoft JhengHei',10));c.bind('<Button-1>',lambda e:w.destroy());w.bind('<Escape>',lambda e:w.destroy())
  def typewrite(i=0):
   if not w.winfo_exists():return
   if i<len(message):
    text.configure(state='normal');text.insert('end',message[i]);text.configure(state='disabled');text.see('end');w.after(90,lambda:typewrite(i+1))
  def animate(i=0):
   if not w.winfo_exists():return
   c.itemconfigure(item,image=frames[i]);w.after(durations[i],lambda:animate((i+1)%len(frames)))
  w.frames=frames;animate();typewrite()
  if actual and self.cfg['sound']:
   def beep():
    for freq in (660,880,660):winsound.Beep(freq,300);time.sleep(.08)
   threading.Thread(target=beep,daemon=True).start()
 def close(self):
  try:self.save()
  except OSError as e:messagebox.showwarning('設定儲存失敗',str(e),parent=self.root)
  if self.alarm and self.alarm.winfo_exists():self.alarm.destroy()
  if self.tray_icon:self.tray_icon.stop();self.tray_icon=None
  self.root.destroy()
 def run(self):self.root.mainloop()
if __name__=='__main__':App().run()
