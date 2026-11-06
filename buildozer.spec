[app]
title = FloatUI
package.name = floatui
package.domain = app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

requirements = python3,kivy,requests,urllib3,certifi,chardet,idna,pyjnius,android,cloudscraper,python-socketio[client]

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,WAKE_LOCK
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
presplash_color = #0b0f14

[buildozer]
log_level = 2
warn_on_root = 1
