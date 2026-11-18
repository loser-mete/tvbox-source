#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「我的精选」影视仓单仓配置 myfav.json

数据来源：
  1. csp_picked.json —— 从 xiaosa(api.json) 精选的 csp 站点（含苹果APP AppDrama）
  2. csp_extras.json  —— xiaosa 的 parses/rules/flags/ads（播放解析 + 去广告）
  3. 内置直链站点库  —— 苹果CMS V10 直链（HTTP，零 jar 依赖，做兜底）
  4. 直播 —— 国内镜像的 m3u/txt

关键格式教训（2026-11-18 血泪总结）：
  A. 顶层绝对不能有 urls 字段！影视仓看到 urls 会当「多仓清单」解析 -> 「接口无效」。
  B. csp_ 站点（含苹果站 AppDrama）天生依赖 spider.jar，无法做成直链。
     之前把 213 个 csp 站点塞进 config.json 却不带 spider 字段 -> 影视仓报「jar加载失败」。
     正确做法（照 xiaosa/wex.json 能打开的格式）：顶层用 spider 字段指向一个
     **真实可下载、md5 匹配**的 jar；本仓库已内置 spider.jar，spider 字段用 ghfast/raw 镜像。
  C. 混合策略：csp 精选站（体验好、有苹果/短剧/动漫）+ 直链站（零依赖兜底），
     即使某天 jar 加载失败，直链站仍可用，不至于全军覆没。
  D. 必须排除依赖 ./py/、./json/ 外部脚本的站点（本仓库没这些文件，会失效）。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSP_FILE = os.path.join(BASE_DIR, "csp_picked.json")
EXTRAS_FILE = os.path.join(BASE_DIR, "csp_extras.json")
OUT = os.path.join(BASE_DIR, "myfav.json")

# spider.jar：本仓库已把 jar 放在与 myfav.json 同一目录（仓库根目录），
# md5 = decb609b673019e18512dc3a96b6a252（已实测校验）。
# 完全复刻用户提供的可打开源 xiaosa 的写法：相对路径 ./spider.jar;md5;md5值。
# 影视仓/FongMi 的 JarLoader 会相对配置 URL 目录解析该路径并做 md5 校验；
# 用 raw 地址加载配置 -> jar 从 raw 取，用 ghfast 镜像地址加载 -> jar 走镜像，自动同步。
JAR_MD5 = "decb609b673019e18512dc3a96b6a252"
JAR_PATH = "./spider.jar"

# 直链兜底站点（苹果CMS V10 标准接口，零 jar 依赖）
DIRECT_SITES = [
    ("🎬光速资源", "https://api.guangsuapi.com/api.php/provide/vod/", "🔥影视精选", 1),
    ("🎬极速资源", "https://jszyapi.com/api.php/provide/vod/", "🔥影视精选", 1),
    ("🎬无尽资源", "https://api.wujinapi.com/api.php/provide/vod/", "🔥影视精选", 1),
    ("🎬百度资源", "https://api.apibdzy.com/api.php/provide/vod/", "🔥影视精选", 1),
    ("🎬360资源",  "https://360zy.com/api.php/provide/vod/", "🔥影视精选", 1),
    ("🎬魔都资源", "https://www.mdzyapi.com/api.php/provide/vod/?ac=list", "🔥影视精选", 1),
    ("🎬天涯资源", "https://ty.tyyszy5.com/api.php/provide/vod/?ac=list", "🔥影视精选", 1),
    ("🎬闪电资源", "https://sdzyapi.com/api.php/provide/vod/?ac=list", "🔥影视精选", 1),
    ("📺淘片短剧", "https://taopianapi.com/cjapi/mc/vod/json.html", "📺短剧专区", 1),
    ("⚡量子资源", "http://cj.lziapi.com/api.php/provide/vod/", "⚡备用线路", 0),
    ("⚡非凡资源", "http://cj.ffzyapi.com/api.php/provide/vod/", "⚡备用线路", 0),
    ("⚡暴风资源", "https://bfzyapi.com/api.php/provide/vod/", "⚡备用线路", 0),
    ("⚡红牛资源", "https://www.hongniuzy2.com/api.php/provide/vod/", "⚡备用线路", 0),
]

LIVES = [
    {"name": "📡 APTV", "type": 0,
     "url": "https://ghfast.top/https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
     "epg": "https://epg.v1.mk/json?ch={name}&date={date}"},
    {"name": "📡 天幕直播", "type": 0,
     "url": "https://ghfast.top/https://raw.githubusercontent.com/TianmuTNT/iptv/main/iptv.txt",
     "epg": "https://epg.v1.mk/json?ch={name}&date={date}"},
    {"name": "📡 大嘴巴IPTV", "type": 0,
     "url": "https://ghfast.top/https://raw.githubusercontent.com/big-mouth-cn/tv/main/iptv-ok.m3u",
     "epg": "https://epg.v1.mk/json?ch={name}&date={date}"},
]


def main():
    # 1) csp 精选站
    with open(CSP_FILE, "r", encoding="utf-8") as f:
        csp_sites = json.load(f)

    # 2) 播放解析 / 去广告规则
    extras = {}
    if os.path.exists(EXTRAS_FILE):
        with open(EXTRAS_FILE, "r", encoding="utf-8") as f:
            extras = json.load(f)

    # 3) 直链兜底站
    direct = []
    for name, api, group, searchable in DIRECT_SITES:
        direct.append({
            "key": name.strip("🎬📺⚡") + "@直链",
            "name": name,
            "type": 1,
            "api": api,
            "searchable": searchable,
            "quickSearch": 0,
            "filterable": 1,
            "group": group + "·直链",
        })

    sites = csp_sites + direct

    # 4) 组装单仓配置 —— 顶层无 urls！带 spider 指向内置 jar
    cfg = {
        "spider": "%s;md5;%s" % (JAR_PATH, JAR_MD5),
        "wallpaper": "https://api.dujin.org/bing/1920.php",
        "sites": sites,
        "lives": LIVES,
    }
    for k in ("parses", "rules", "flags", "ads"):
        if extras.get(k):
            cfg[k] = extras[k]

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    from collections import Counter
    gc = Counter(s.get("group", "") for s in sites)
    print("生成 %s" % OUT)
    print("  spider:", cfg["spider"])
    print("  站点 %d 条 (csp %d + 直链 %d):" % (len(sites), len(csp_sites), len(direct)))
    for g, n in sorted(gc.items()):
        print("    %s: %d" % (g, n))
    print("  解析 %d / 规则 %d / 广告 %d" % (len(cfg.get("parses", [])), len(cfg.get("rules", [])), len(cfg.get("ads", []))))
    print("  直播 %d / 顶层字段: %s" % (len(LIVES), list(cfg.keys())))


if __name__ == "__main__":
    main()
