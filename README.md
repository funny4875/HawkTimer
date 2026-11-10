<p align="center"><img src="assets/icon.png" alt="HawkTimer 圖示" width="160"></p>

# HawkTimer 鷹眼計時

Windows 透明桌面蕃茄鐘，時間到時播放 GIF 與提醒文字，並可透過 ntfy 發送 Android 通知。

## 功能

- 透明背景及置頂計時視窗，可拖曳角色移動，右鍵開啟選單；常駐角色可替換 GIF。
- 設定專注時間（最短 1 秒）、電腦提示音與 ntfy 通知；設定和視窗位置會自動保存。
- 支援選擇 GIF 或圖片作為提醒動畫；每次隨機選取一則自訂文字，逐字顯示。
- 手機持續響鈴需在 Android ntfy 的訂閱通知設定中啟用。

## 安裝

前往 [Releases](https://github.com/funny4875/HawkTimer/releases) 下載 MSI，安裝後可從桌面或開始選單啟動。程式安裝於 `%LOCALAPPDATA%\HawkTimer`，`message.txt` 位於同一資料夾。MSI 未經數位簽章。

## 從原始碼執行

需要 Windows、Python 3.10 以上。於專案資料夾執行：

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

開啟設定，將 ntfy 主題改為手機訂閱的主題。主題預設值僅供示範，未受保護的 ntfy 主題只要知道名稱便可能被讀取或發布；請勿傳送私人資訊。設定儲存於 `%APPDATA%\HawkPomodoro\settings.json`，倒數進度不會保存。計時需保持程式及電腦運行，手機通知需連網。

程式使用 Windows 信任存放區驗證 HTTPS 憑證。內附角色動圖為 AI 生成的同人素材；角色權利屬原權利人。
## 自訂提醒文字

編輯程式所在資料夾的 `message.txt`（UTF-8 編碼），用單獨一行 `========` 分隔訊息；同一則訊息可以包含多行。程式每次時間到時重新讀取檔案，隨機挑選一則，畫面與 ntfy 發送相同內容。也可以在設定視窗編輯並儲存，或按「文字檔」開啟編輯。提醒框會依內容加長，超出螢幕時可捲動。訊息過長時可能超出 ntfy 的訊息長度限制。首次啟動若沒有文字檔，會使用原有設定建立。
