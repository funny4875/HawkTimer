import time
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlsplit

FIRST=' /html/body/div[2]/div/div[1]/div[2]/div[1]/div/div/div[2]/div/div[1]/div[2]/div'.strip()
SECOND='//*[@id="YPCqFe"]/div/div/div/div[9]/div/div[5]/div[1]/div[1]/span/span/button/div'

def calendar_ready(driver):
 # Never interact with Google account sign-in, verification or permission pages.
 if urlsplit(driver.current_url).hostname!='calendar.google.com':return False
 for dialog in driver.find_elements(By.CSS_SELECTOR,'[role="dialog"]'):
  if not dialog.is_displayed():continue
  for button in dialog.find_elements(By.CSS_SELECTOR,'button,[role="button"]'):
   label=(button.get_attribute('aria-label') or button.text or '').strip().lower()
   if label in ('關閉','关闭','close','稍後再說','稍后再说','not now','dismiss','略過','略过','skip','不用了','不用，謝謝','no thanks','知道了','got it') and button.is_displayed() and button.is_enabled():
    button.click();return False
 return True

def obtain_ical(ready=None,driver_factory=None):
 options=webdriver.ChromeOptions();options.add_argument('--start-maximized')
 options.add_experimental_option('detach',True)
 driver=None;success=False
 try:
  driver=(driver_factory or ChromeWebDriver)(options=options)
  driver.get('https://calendar.google.com/calendar/u/0/r/settings')
  if ready:ready()
  wait=WebDriverWait(driver,300,poll_frequency=0.5)
  wait.until(calendar_ready)
  driver.get('https://calendar.google.com/calendar/u/0/r/settings')
  wait.until(calendar_ready)
  first=wait.until(EC.element_to_be_clickable((By.XPATH,FIRST)))
  time.sleep(1);first.click()
  second=wait.until(EC.element_to_be_clickable((By.XPATH,SECOND)))
  button=second.find_element(By.XPATH,'./ancestor-or-self::button[1]')
  label=' '.join(str(button.get_attribute(x) or '') for x in ('aria-label','title','textContent')).lower()
  if not any(word in label for word in ('複製','copy','复制')):
   raise ValueError('找不到可確認的「複製到剪貼簿」按鈕，請在 Chrome 中手動複製非公開 iCal 網址。')
  time.sleep(1);second.click();success=True
 finally:
  if driver:
   try:
    if success:driver.quit()
    else:driver.service.stop()
   except Exception:pass
