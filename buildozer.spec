[app]
title = Trade Sinyal Ultra
package.name = tradesinyal
package.domain = com.tradesinyal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = assets/*,trade_v7.py
version = 7.0

requirements = python3,kivy==2.3.0,numpy,pandas,requests,colorama,certifi,urllib3,charset-normalizer,idna

orientation = portrait
fullscreen = 0
android.minapi = 21
android.ndk = 25b
android.sdk = 34
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.permissions = INTERNET,ACCESS_NETWORK_STATE

log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
warn_on_root = 1
