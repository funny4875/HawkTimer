APP_VERSION="1.4.7"
DISPLAY_VERSION=f"v{APP_VERSION}（測試版）"

def window_title(title):
 return f"{title}  {DISPLAY_VERSION}"

class VersionedMessageBox:
 def __init__(self, module):self.module=module
 def __getattr__(self, name):
  function=getattr(self.module,name)
  def show(title, *args, **kwargs):return function(window_title(title),*args,**kwargs)
  return show
