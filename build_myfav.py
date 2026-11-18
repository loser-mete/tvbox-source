#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「我的精选」影视仓单仓配置 myfav.json

数据来源：
  1. probe_sites.json —— update.py 探活的直链站点结果（按可用性）
  2. 内置精选列表 —— 全网优质采集站（多源交叉验证 + 实测）
  3. 垂直专项源 —— 动漫/少儿等需要 spider 的完整配置（放 urls 订阅）
  4. 直播 —— 国内镜像的 m3u/txt

分组（group 字段，影视仓按此分标签页）：
  🔥影视精选 / 📺短剧专区 / ⚡备用线路
零脚本、零 csp_ —— 影视仓原生直连，不会「接口无效」。
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
CURATED = [
    # ===== 🔥 影视精选（探活可用 + 老牌稳定）=====
    ("🎬魔都资源",   "https://www.mdzyapi.com/api.php/provide/vod/?ac=list", "🔥影视精选", 1),
    ("🎬天涯资源",   "https://ty.tyyszy5.com/api.php/provide/vod/?ac=list",  "🔥影视精选", 1),
    ("🎬非凡资源",   "https://ffzy.tv/api.php/provide/vod/",                "🔥影视精选", 1),
    ("🎬360资源",    "https://360zy.com/api.php/provide/vod/",              "🔥影视精选", 1),
    ("🎬极速资源",   "https://jszyapi.com/api.php/provide/vod/at/json",     "🔥影视精选", 1),
    ("🎬闪电资源",   "https://sdzyapi.com/api.php/provide/vod/?ac=list",    "🔥影视精选", 1),
    ("🎬无尽资源",   "https://api.wujinapi.me/api.php/provide/vod/?ac=list","🔥影视精选", 1),
    ("🎬CK资源",     "https://ckzy.me/api.php/provide/vod/?ac=list",        "🔥影视精选", 1),
    ("🎬光速资源",   "https://api.guangsuapi.com/api.php/provide/vod/from/guangsu/m3u8", "🔥影视精选", 1),
    ("🎬黑木耳",     "https://json02.heimuer.xyz/api.php/provide/vod/",     "🔥影视精选", 1),
    ("🎬创享资源",   "https://ys.cxkjg.cn/api/provide/vod/",                "🔥影视精选", 1),
    ("🎬优质资源",   "https://api.yyzy-tv.vip/inc/apijson.php",             "🔥影视精选", 1),
    ("🎬百度资源",   "https://api.apibdzy.com/api.php/provide/vod/?ac=list","🔥影视精选", 1),
    ("🎬鱼乐资源",   "https://api.yulecj.com/api.php/provide/vod/?ac=list", "🔥影视精选", 1),
    ("🎬卧龙资源",   "https://collect.wolongzyw.com/api.php/provide/vod/",  "🔥影视精选", 0),
    # ===== 📺 短剧专区 =====
    ("📺淘片短剧",   "https://taopianapi.com/cjapi/mc/vod/json.html",       "📺短剧专区", 1),
    ("📺淘片线路",   "https://taopianapi.com/cjapi/mc10/vod/xml.html",      "📺短剧专区", 0),
    # ===== ⚡ 备用线路（多源交叉收录，本机网络超时但口碑稳定）=====
    ("⚡电影天堂",   "https://caiji.dyttzyapi.com/api.php/provide/vod/",    "⚡备用线路", 0),
    ("⚡量子资源",   "https://cj.lziapi.com/api.php/provide/vod/",          "⚡备用线路", 0),
    ("⚡暴风资源",   "https://bfzyapi.com/api.php/provide/vod/",            "⚡备用线路", 0),
    ("⚡爱坤资源",   "https://ikunzyapi.com/api.php/provide/vod/",          "⚡备用线路", 0),
    ("⚡新浪资源",   "https://api.xinlangapi.com/api.php/provide/vod/",     "⚡备用线路", 0),
    ("⚡天空资源",   "https://m3u8.tiankongapi.com/api.php/provide/vod/",   "⚡备用线路", 0),
    ("⚡索尼资源",   "https://suoniapi.com/api.php/provide/vod/",           "⚡备用线路", 0),
    ("⚡ vn 资源",    "https://api.wujinapi.net/api.php/provide/vod/",       "⚡备用线路", 0),
]

# 垂直专项源：完整配置，影视仓加载时自带 spider，能正确解析
# 放在 urls 里影视仓会合并为一个个独立"源"标签页
SUBS = [
    {"name": "🌈动漫专线", "url": "https://www.yingm.cc/dm/dm.json", "type": 1},
    {"name": "🧒少儿频道", "url": "https://jihulab.com/ymz1231/xymz/-/raw/main/ymshaoer", "type": 1},
    {"name": "📺短剧专线", "url": "http://box.ufuzi.com/tv/qq/%E7%9F%AD%E5%89%A7%E9%A2%91%E9%81%93/api.json", "type": 1},
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
    seen = set()
    for name, api, group, searchable in CURATED:
        if api in seen:
            continue
        seen.add(api)
        site = {
            "key": name.replace("🎬", "").replace("📺", "").replace("⚡", "").strip(),
            "name": name,
            "type": 1,
            "api": api,
            "searchable": searchable,
            "quickSearch": 0,
            "filterable": 1 if searchable else 0,
            "group": group,
        }
        sites.append(site)

    # urls 订阅（dict 格式，影视仓/FongMi 通用）
    urls = {}
    for s in SUBS:
        urls[s["name"]] = s["url"]

    cfg = {
        "urls": urls,
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
    print("  站点 %d 个（本次探活可用 %d）:" % (len(sites), verified))
    for g, n in gc.items():
        print("    %s: %d" % (g, n))
    print("  订阅源 %d 个: %s" % (len(urls), ", ".join(s["name"] for s in SUBS)))
    print("  直播源 %d 个（国内镜像）" % len(LIVES))
    print("  顶层字段:", list(cfg.keys()))


if __name__ == "__main__":
    main()
