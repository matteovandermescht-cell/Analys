import threading
import time
import re
import json
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.utils import platform
import requests
import socketio

ANDROID = platform == "android"
if ANDROID:
    from android import mActivity
    from android.permissions import request_permissions, Permission
    from jnius import autoclass, PythonJavaClass, java_method

# =====================================================================
# TARGET CONFIG (Vom User auszufüllen)
# =====================================================================
TARGET_URL = "https://DEINE-ZIEL-DOMAIN-HIER"
AUTH_TOKEN = "DEIN_TOKEN_HIER"
COOKIE_STR = "DEIN_COOKIE_HIER"
USER_ID = "DEINE_USER_ID_HIER"

STATUS = {"wins": 0, "losses": 0, "profit": 0.0, "running": False}

# =====================================================================
# NATIVE ANDROID OVERLAY
# =====================================================================
class Runnable(PythonJavaClass):
    __javainterfaces__ = ["java/lang/Runnable"]
    __javacontext__ = "app"
    def __init__(self, fn): super().__init__(); self.fn = fn
    @java_method("()V")
    def run(self):
        try: self.fn()
        except: pass

class TouchListener(PythonJavaClass):
    __javainterfaces__ = ["android/view/View$OnTouchListener"]
    __javacontext__ = "app"
    def __init__(self, wm, lp):
        super().__init__()
        self.wm = wm; self.lp = lp
        self.sx = 0; self.sy = 0; self.tx = 0; self.ty = 0
    @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
    def onTouch(self, v, e):
        a = e.getAction()
        if a == 0:
            self.sx = int(self.lp.x); self.sy = int(self.lp.y)
            self.tx = int(e.getRawX()); self.ty = int(e.getRawY())
            return True
        if a == 2:
            dx = int(e.getRawX()) - self.tx
            dy = int(e.getRawY()) - self.ty
            self.lp.x = self.sx - dx
            self.lp.y = self.sy + dy
            mActivity.runOnUiThread(Runnable(lambda: self.wm.updateViewLayout(v, self.lp)))
            return True
        return False

class Overlay:
    def __init__(self):
        self.wm = None; self.tv = None; self.active = False
    def show(self):
        if not ANDROID or self.active: return
        try:
            Settings = autoclass("android.provider.Settings")
            if not Settings.canDrawOverlays(mActivity):
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                i = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
                i.setData(Uri.parse("package:" + mActivity.getPackageName()))
                mActivity.startActivity(i)
                return

            Ctx = autoclass("android.content.Context")
            WM = autoclass("android.view.WindowManager")
            LP = autoclass("android.view.WindowManager$LayoutParams")
            Grav = autoclass("android.view.Gravity")
            Pix = autoclass("android.graphics.PixelFormat")
            TV = autoclass("android.widget.TextView")
            Col = autoclass("android.graphics.Color")

            self.wm = mActivity.getSystemService(Ctx.WINDOW_SERVICE)
            self.lp = LP(LP.WRAP_CONTENT, LP.WRAP_CONTENT, LP.TYPE_APPLICATION_OVERLAY,
                         LP.FLAG_NOT_FOCUSABLE | LP.FLAG_NOT_TOUCH_MODAL, Pix.TRANSLUCENT)
            self.lp.gravity = Grav.TOP | Grav.START
            self.lp.x = 50; self.lp.y = 150

            self.tv = TV(mActivity)
            self.tv.setText("FloatUI\\nBereit")
            self.tv.setTextSize(14.0)
            self.tv.setTextColor(Col.WHITE)
            self.tv.setBackgroundColor(Col.argb(220, 20, 26, 34))
            self.tv.setPadding(30, 30, 30, 30)
            self.tv.setOnTouchListener(TouchListener(self.wm, self.lp))

            mActivity.runOnUiThread(Runnable(lambda: self.wm.addView(self.tv, self.lp)))
            self.active = True
        except Exception as e:
            print("Overlay Error:", e)

    def update(self, txt):
        if self.active and self.tv:
            mActivity.runOnUiThread(Runnable(lambda: self.tv.setText(txt)))

OVERLAY = Overlay()

# =====================================================================
# BACKGROUND LOGIC
# =====================================================================
class Worker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
    def run(self):
        STATUS["running"] = True
        s = requests.Session()
        s.headers.update({"Cookie": COOKIE_STR, "x-csrf-token": AUTH_TOKEN, "User-Agent": "Mozilla/5.0"})
        
        sio = socketio.Client(reconnection=True)
        
        @sio.event
        def connect():
            sio.emit("authenticate", AUTH_TOKEN)
            
        @sio.on("new game")
        def on_new(data):
            if not STATUS["running"]: return
            gid = data.get("game_id") or data.get("id")
            if not gid: return
            # Hier kann Logik eingefügt werden, um dem Spiel beizutreten
            pass

        @sio.on("game played")
        def on_played(data):
            gid = data.get("game_id") or data.get("game")
            ws = data.get("winner_side")
            ss = data.get("starter_side")
            sid = str(data.get("starter_id", ""))
            pid = str(data.get("player_id", ""))
            
            if ws is not None and ss is not None:
                won = (sid if ws == ss else pid) == USER_ID
                if won: STATUS["wins"] += 1
                else: STATUS["losses"] += 1
                STATUS["profit"] += (10 if won else -10) # Platzhalter-Wert

        try:
            sio.connect(TARGET_URL, socketio_path="/chat-ws/socket.io", transports=["polling", "websocket"])
            while STATUS["running"]:
                time.sleep(1)
            sio.disconnect()
        except Exception as e:
            print("Worker Error:", e)
        finally:
            STATUS["running"] = False

# =====================================================================
# KIVY UI
# =====================================================================
class MainUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=20, **kw)
        
        self.add_widget(Label(text="FloatUI", font_size="24sp", size_hint_y=None, height=50))
        
        self.lbl = Label(text="Status: IDLE", size_hint_y=None, height=30)
        self.add_widget(self.lbl)

        btn_start = Button(text="START", size_hint_y=None, height=50, background_color=(0.2, 0.8, 0.2, 1))
        btn_start.bind(on_press=self.start)
        self.add_widget(btn_start)

        btn_ov = Button(text="Overlay anzeigen", size_hint_y=None, height=50)
        btn_ov.bind(on_press=lambda x: OVERLAY.show())
        self.add_widget(btn_ov)
        
        btn_stop = Button(text="STOP", size_hint_y=None, height=50, background_color=(0.8, 0.2, 0.2, 1))
        btn_stop.bind(on_press=self.stop)
        self.add_widget(btn_stop)

        Clock.schedule_interval(self.tick, 1)

    def start(self, _):
        if not STATUS["running"]:
            Worker().start()
            self.lbl.text = "Status: LÄUFT"

    def stop(self, _):
        STATUS["running"] = False
        self.lbl.text = "Status: GESTOPPT"

    def tick(self, _dt):
        if OVERLAY.active:
            txt = f"W:{STATUS['wins']} L:{STATUS['losses']}\\nProfit: {STATUS['profit']:+.2f}"
            OVERLAY.update(txt)

class FloatApp(App):
    def build(self):
        if ANDROID:
            request_permissions([Permission.INTERNET, Permission.SYSTEM_ALERT_WINDOW])
        return MainUI()

if __name__ == "__main__":
    FloatApp().run()
