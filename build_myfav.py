#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「我的精选」影视仓单仓配置 myfav.json

数据来源：
  1. probe_sites.json —— update.py 探活的直链站点结果（按可用性）
  2. 内置精选列表 —— 全网优质采集站（多源交叉验证 + 实测）
  3. 直播 —— 国内镜像的 m3u/txt

分组（group 字段，影视仓按此分标签页）：
  🔥影视精选 / 🌈动漫专区 / 📺短剧专区 / 🧒少儿儿童 / ⚡备用线路

重要设计决策：
  不使用任何 csp_/drpy.js 专项源。原因：这类站点依赖各自 spider.jar，
  被影视仓作为单仓配置的 urls 订阅合并时，只用主配置的 spider，导致站点全废
  （用户实测「单项专线打不开」）。而综合采集站本身内置动漫/短剧/儿童分类标签，
  filterable=1 即可在站内切换，能力更全也更稳。
  全部站点为 HTTP 直链、零 spider 依赖 —— 影视仓原生支持，不会「接口无效」。
"""
import json
import os
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 探活结果（可选）：存在则用于统计"本次可用数"，不存在也不影响生成。
# 注意：采集站 API 面向国内，GitHub Actions 在境外探活会超时，故清单本身保持静态精选，
# 失效剔除由本地实测后更新 CURATED 列表完成，不依赖 CI 探活。
PROBE_FILE = os.path.join(BASE_DIR, "probe_sites.json")
OUT = os.path.join(BASE_DIR, "myfav.json")

# ---------------------------------------------------------------------------
# 精选站点库：全网优质苹果CMS采集站，均为 HTTP 直链（type=1 标准 JSON 接口）
# 每条: (显示名, api, group, searchable)
# 质量依据：多源交叉收录 + 探活验证 + 长期维护口碑
# ---------------------------------------------------------------------------
# 分组依据：实测每个直链站 ?ac=list 返回的内置分类。
# 综合采集站本身都有「电影/剧集/动漫/短剧/综艺」分类标签，站内切换即可，
# 因此同一个站可归入多个内容分组（影视仓允许同名站不同 key 重复出现）。
# 全部为 HTTP 直链、零 spider 依赖 —— 影视仓原生支持，不会「接口无效」。
CURATED = [
    # ===== 🔥 影视精选（综合最强、分类最全，实测可用）=====
    ("🎬魔都资源",   "https://www.mdzyapi.com/api.php/provide/vod/?ac=list", "🔥影视精选", 1),
    ("🎬天涯资源",   "https://ty.tyyszy5.com/api.php/provide/vod/?ac=list",  "🔥影视精选", 1),
    ("🎬非凡资源",   "https://ffzy.tv/api.php/provide/vod/",                "🔥影视精选", 1),
    ("🎬360资源",    "https://360zy.com/api.php/provide/vod/",              "🔥影视精选", 1),
    ("🎬极速资源",   "https://jszyapi.com/api.php/provide/vod/at/json",     "🔥影视精选", 1),
    ("🎬闪电资源",   "https://sdzyapi.com/api.php/provide/vod/?ac=list",    "🔥影视精选", 1),
    ("🎬无尽资源",   "https://api.wujinapi.me/api.php/provide/vod/?ac=list","🔥影视精选", 1),
    ("🎬光速资源",   "https://api.guangsuapi.com/api.php/provide/vod/from/guangsu/m3u8", "🔥影视精选", 1),
    ("🎬优质资源",   "https://api.yyzy-tv.vip/inc/apijson.php",             "🔥影视精选", 1),
    ("🎬百度资源",   "https://api.apibdzy.com/api.php/provide/vod/?ac=list","🔥影视精选", 1),
    ("🎬创享资源",   "https://ys.cxkjg.cn/api/provide/vod/",                "🔥影视精选", 1),
    ("🎬黑木耳",     "https://json02.heimuer.xyz/api.php/provide/vod/",     "🔥影视精选", 0),

    # ===== 🌈 动漫专区（实测内置动漫分类最多）=====
    ("🌈魔都动漫",   "https://www.mdzyapi.com/api.php/provide/vod/?ac=list", "🌈动漫专区", 0),
    ("🌈天涯动漫",   "https://ty.tyyszy5.com/api.php/provide/vod/?ac=list",  "🌈动漫专区", 0),
    ("🌈闪电动漫",   "https://sdzyapi.com/api.php/provide/vod/?ac=list",    "🌈动漫专区", 0),
    ("🌈无尽动漫",   "https://api.wujinapi.me/api.php/provide/vod/?ac=list","🌈动漫专区", 0),
    ("🌈百度动漫",   "https://api.apibdzy.com/api.php/provide/vod/?ac=list","🌈动漫专区", 0),

    # ===== 📺 短剧专区（实测内置短剧分类）=====
    ("📺淘片短剧",   "https://taopianapi.com/cjapi/mc/vod/json.html",       "📺短剧专区", 1),
    ("📺魔都短剧",   "https://www.mdzyapi.com/api.php/provide/vod/?ac=list", "📺短剧专区", 0),
    ("📺360短剧",    "https://360zy.com/api.php/provide/vod/",              "📺短剧专区", 0),
    ("📺极速短剧",   "https://jszyapi.com/api.php/provide/vod/at/json",     "📺短剧专区", 0),

    # ===== 🧒 少儿 / 儿童（无尽站实测有「儿童儿歌」分类）=====
    ("🧒无尽儿童",   "https://api.wujinapi.me/api.php/provide/vod/?ac=list","🧒少儿儿童", 0),

    # ===== ⚡ 备用线路（多源交叉收录，本机网络超时但口碑稳定）=====
    ("⚡电影天堂",   "https://caiji.dyttzyapi.com/api.php/provide/vod/",    "⚡备用线路", 0),
    ("⚡量子资源",   "https://cj.lziapi.com/api.php/provide/vod/",          "⚡备用线路", 0),
    ("⚡暴风资源",   "https://bfzyapi.com/api.php/provide/vod/",            "⚡备用线路", 0),
    ("⚡爱坤资源",   "https://ikunzyapi.com/api.php/provide/vod/",          "⚡备用线路", 0),
    ("⚡新浪资源",   "https://api.xinlangapi.com/api.php/provide/vod/",     "⚡备用线路", 0),
    ("⚡天空资源",   "https://m3u8.tiankongapi.com/api.php/provide/vod/",   "⚡备用线路", 0),
    ("⚡索尼资源",   "https://suoniapi.com/api.php/provide/vod/",           "⚡备用线路", 0),
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
    # 读取探活结果，标记哪些站点实测可用
    probe_ok_urls = set()
    if os.path.exists(PROBE_FILE):
        try:
            with open(PROBE_FILE, "r", encoding="utf-8") as f:
                for r in json.load(f):
                    if r.get("ok"):
                        probe_ok_urls.add(r["api"].rstrip("/"))
        except Exception:
            pass

    sites = []
    seen = set()  # 按 (name, group) 去重：同一 api 可归入不同内容分组
    for name, api, group, searchable in CURATED:
        ident = (name, group)
        if ident in seen:
            continue
        seen.add(ident)
        site = {
            "key": name.replace("🎬", "").replace("📺", "").replace("🌈", "")
                       .replace("🧒", "").replace("⚡", "").strip() + "@" + group,
            "name": name,
            "type": 1,
            "api": api,
            "searchable": searchable,
            "quickSearch": 0,
            "filterable": 1,
            "group": group,
        }
        sites.append(site)

    # 不依赖任何 spider 专项源。分类能力由各直链站内置的分类标签提供。
    cfg = {
        "urls": {},
        "sites": sites,
        "lives": LIVES,
        "wallpaper": "https://api.dujin.org/bing/1920.php",
    }

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # 统计
    from collections import Counter
    gc = Counter(s["group"] for s in sites)
    verified = sum(1 for s in sites if s["api"].rstrip("/") in probe_ok_urls)
    print("生成 %s" % OUT)
    print("  站点 %d 条（本次探活可用 %d 条）:" % (len(sites), verified))
    for g, n in gc.items():
        print("    %s: %d" % (g, n))
    print("  订阅源 0（已移除全部 spider 专项源，零依赖）")
    print("  直播源 %d 个（国内镜像）" % len(LIVES))
    print("  顶层字段:", list(cfg.keys()))


if __name__ == "__main__":
    main()
