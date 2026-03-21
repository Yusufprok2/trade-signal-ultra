[app]
title = Trade Sinyal Ultra
package.name = tradesinyal
package.domain = com.tradesinyal
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = trade_v7.py
version = 8.0

requirements = python3,kivy==2.3.0,numpy,pandas,requests,colorama,certifi

orientation = portrait
fullscreen = 0
android.minapi = 21
android.ndk = 27c
android.sdk = 34
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a
android.allow_backup = True
android.permissions = INTERNET,ACCESS_NETWORK_STATE

[buildozer]
log_level = 2
