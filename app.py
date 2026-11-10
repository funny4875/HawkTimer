import os, sys, json, time, math, threading, urllib.request, re, winsound, random, ssl, truststore
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageSequence
BASE=getattr(sys,'_MEIPASS',os.path.dirname(os.path.abspath(__file__)))
ICON=os.path.join(BASE,'icon.ico' if getattr(sys,'frozen',False) else 'assets/icon.ico')
CONFIG_DIR=os.path.join(os.environ.get('APPDATA',os.path.expanduser('~')),'HawkPomodoro')
CONFIG=os.path.join(CONFIG_DIR,'settings.json')
MESSAGE_FILE=os.path.join(os.path.dirname(sys.executable) if getattr(sys,'frozen',False) else BASE,'message.txt')
DEFAULT={'minutes':25,'seconds':0,'topic':'your-ntfy-topic','notify':True,'sound':True,'topmost':True,'x':None,'y':None,'gif':'','idle_gif':'','messages':['時間到！休息一下。','辛苦了，起來活動一下！','專注完成，該喝水囉！']}
KEY='#ff00ff'
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
def load_frames(path, size):
 frames=[]; durations=[]
 with Image.open(path) as im:
  for frame in ImageSequence.Iterator(im):
   rgba=frame.convert('RGBA'); rgba.thumbnail(size,Image.Resampling.LANCZOS)
   bg=Image.new('RGBA',rgba.size,(255,0,255,255)); bg.alpha_composite(rgba)
   frames.append(ImageTk.PhotoImage(bg.convert('RGB'))); durations.append(max(40,int(frame.info.get('duration',100) or 100)))
 if not frames:raise ValueError('圖片沒有畫格')
 return frames,durations
class App:
 def __init__(self):
  self.cfg=read_config(); self.root=tk.Tk(); self.root.title('HawkTimer 鷹眼計時'); self.root.iconbitmap(ICON);  self.root.overrideredirect(True); self.root.configure(bg=KEY); self.root.wm_attributes('-transparentcolor',KEY); self.root.attributes('-topmost',bool(self.cfg['topmost']))
  x=self.cfg['x']; y=self.cfg['y']; self.root.geometry('360x480'+(f'+{x}+{y}' if x is not None and y is not None and x>=0 and y>=0 else '+100+100'))
  self.running=False; self.end=0; self.remaining=int(self.cfg['minutes'])*60+int(self.cfg.get('seconds',0)); self.alarm=None
  self.canvas=tk.Canvas(self.root,width=360,height=385,bg=KEY,highlightthickness=0); self.canvas.pack()
  self.idle_item=self.canvas.create_image(180,190); self.idle_job=None; self.set_idle(self.cfg.get('idle_gif',''));  self.canvas.bind('<ButtonPress-1>',self.drag_start); self.canvas.bind('<B1-Motion>',self.drag_move); self.canvas.bind('<Button-3>',self.popup)
  box=tk.Frame(self.root,bg='#171927',highlightbackground='#d4ad65',highlightthickness=2); box.pack(fill='x',padx=4)
  self.label=tk.Label(box,font=('Microsoft JhengHei',25,'bold'),fg='#f2d392',bg='#171927'); self.label.pack()
  row=tk.Frame(box,bg='#171927'); row.pack(pady=(0,6))
  self.btn=tk.Button(row,text='開始',width=6,command=self.toggle); self.btn.pack(side='left',padx=2)
  for text,cmd in [('重設',self.reset),('文字檔',self.open_messages),('設定',self.settings),('結束',self.close)]:tk.Button(row,text=text,width=6,command=cmd).pack(side='left',padx=2)
  self.menu=tk.Menu(self.root,tearoff=0)
  for label,cmd in [('設定',self.settings),('開啟文字檔',self.open_messages),('預覽提醒動畫',lambda:self.show_alarm(False)),('測試手機通知',lambda:self.notify(True)),('結束',self.close)]:self.menu.add_command(label=label,command=cmd)
  self.root.bind('<Button-3>',self.popup); self.update_label(); self.root.after(100,self.tick)
 def set_idle(self,path):
  if self.idle_job: self.root.after_cancel(self.idle_job); self.idle_job=None
  try: self.mainframes,self.maindurations=load_frames(path or os.path.join(BASE,'mihawk_idle.gif'),(350,380))
  except Exception as e:
   messagebox.showwarning('常駐動畫載入失敗',f'{e}\n改用預設動畫。',parent=self.root)
   self.mainframes,self.maindurations=load_frames(os.path.join(BASE,'mihawk_idle.gif'),(350,380))
  self.hatframes,self.hatdurations=load_frames(os.path.join(BASE,'mihawk_hat.gif'),(350,380)) if not path else ([],[])
  def animate(index=0, cycles=0, hat=False):
   frames=self.hatframes if hat else self.mainframes
   durations=self.hatdurations if hat else self.maindurations
   self.canvas.itemconfigure(self.idle_item,image=frames[index]);next_index=index+1
   if next_index>=len(frames):
    next_index=0
    if hat: hat=False;cycles=0
    else:
     cycles+=1
     if cycles>=1 and self.hatframes: hat=True
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
 def toggle(self):
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
  minutes=tk.StringVar(value=str(self.cfg['minutes']));seconds=tk.StringVar(value=str(self.cfg.get('seconds',0)));topic=tk.StringVar(value=self.cfg['topic']);gif=tk.StringVar(value=self.cfg['gif']);idle=tk.StringVar(value=self.cfg.get('idle_gif',''));notify=tk.BooleanVar(value=self.cfg['notify']);sound=tk.BooleanVar(value=self.cfg['sound']);top=tk.BooleanVar(value=self.cfg['topmost'])
  for r,(label,var) in enumerate([('專注時間（分鐘）',minutes),('ntfy 主題',topic),('提醒 GIF / 圖片',gif),('常駐 GIF / 圖片',idle)]):
   ttk.Label(f,text=label).grid(row=r,column=0,sticky='w',pady=4);ttk.Entry(f,textvariable=var,width=38).grid(row=r,column=1,sticky='ew')
  ttk.Label(f,text='秒').grid(row=0,column=2,sticky='e');ttk.Entry(f,textvariable=seconds,width=5).grid(row=0,column=3,sticky='w')
  def browse(var):
   p=filedialog.askopenfilename(parent=w,title='選擇 GIF 或圖片',filetypes=[('圖片','*.gif *.png *.jpg *.jpeg *.webp'),('所有檔案','*.*')])
   if p:var.set(p)
  for r,var in [(2,gif),(3,idle)]:
   ttk.Button(f,text='選擇檔案',command=lambda v=var:browse(v)).grid(row=r,column=2,padx=4);ttk.Button(f,text='使用預設',command=lambda v=var:v.set('')).grid(row=r,column=3)
  for r,(label,var) in enumerate([('時間到發送手機通知',notify),('播放電腦提示音',sound),('計時器置頂',top)],4):ttk.Checkbutton(f,text=label,variable=var).grid(row=r,column=0,columnspan=3,sticky='w')
  ttk.Label(f,text='提醒文字（支援換行，以獨立一行 ======== 分隔）').grid(row=7,column=0,columnspan=4,sticky='w',pady=(10,2))
  text=tk.Text(f,width=55,height=7);text.grid(row=8,column=0,columnspan=4)
  try:
   with open(MESSAGE_FILE,encoding='utf-8-sig') as src: content=src.read()
  except FileNotFoundError: content='\n========\n'.join(self.cfg.get('messages') or DEFAULT['messages'])
  except (OSError, UnicodeError) as e: messagebox.showerror('訊息讀取失敗',str(e),parent=w);w.destroy();return
  text.insert('1.0',content)
  def apply():
   try:
    m=int(minutes.get());sec=int(seconds.get());t=topic.get().strip();p=gif.get().strip();idlepath=idle.get().strip();content=text.get('1.0','end-1c');messages=parse_messages(content)
    if not (0<=m<=1440 and 0<=sec<=59 and 1<=m*60+sec<=86400):raise ValueError('請設定 1 秒至 1440 分鐘，秒數請輸入 0 至 59。')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',t):raise ValueError('ntfy 主題格式不正確。')
    if not messages:raise ValueError('請至少輸入一句提醒文字。')
    for image_path in (p,idlepath):
     if image_path:
      with Image.open(image_path) as im: im.seek(0);im.load()
    with open(MESSAGE_FILE,'w',encoding='utf-8') as dest: dest.write(content)
   except Exception as e:messagebox.showerror('設定錯誤',str(e),parent=w);return
   changed=(m,sec)!=(self.cfg['minutes'],self.cfg.get('seconds',0));self.cfg.update(minutes=m,seconds=sec,topic=t,gif=p,idle_gif=idlepath,messages=messages,notify=notify.get(),sound=sound.get(),topmost=top.get());self.root.attributes('-topmost',top.get());self.set_idle(idlepath);self.save()
   if changed:self.reset()
   w.destroy()
  ttk.Button(f,text='儲存',command=apply).grid(row=9,column=3,pady=10)
 def show_alarm(self,actual,message=None):
  if message is None:
   try: message=random.choice(read_messages(self.cfg))
   except (OSError,ValueError,UnicodeError) as e: messagebox.showwarning('訊息讀取失敗',str(e),parent=self.root);return
  if self.alarm and self.alarm.winfo_exists():self.alarm.destroy()
  path=self.cfg['gif'] or os.path.join(BASE,'mihawk_action.gif')
  try:frames,durations=load_frames(path,(350,350))
  except Exception as e:
   messagebox.showwarning('動畫載入失敗',f'{e}\n改用預設動畫。',parent=self.root);frames,durations=load_frames(os.path.join(BASE,'mihawk_action.gif'),(350,350))
  w=tk.Toplevel(self.root);self.alarm=w;self.canvas.itemconfigure(self.idle_item,state='hidden')
  def restore_idle(event):
   if event.widget is w and self.root.winfo_exists():self.canvas.itemconfigure(self.idle_item,state='normal');self.alarm=None
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
  self.root.destroy()
 def run(self):self.root.mainloop()
if __name__=='__main__':App().run()
