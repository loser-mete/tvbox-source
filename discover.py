#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知名影视仓源发现器
============================================================
从 discovery_seeds.json 里的「知名影视仓源」出发，展开其内部结构，
提取可用的候选源地址，写入 discovered.json 供 update.py 并入源池。

发现什么（"合适源地址"的判定）：
  1. 直播订阅 lives：http(s) 的 m3u/txt/iptv 地址（相对路径 ./、proxy://、
     带 token 的付费地址、drpy 脚本 .py/.js 一律排除），探活后频道数达标才收。
  2. 苹果CMS 直链 sites：api 含 /api.php/provide/vod 的 HTTP 接口，
     零 jar 依赖，探活返回合法 vod JSON 才收。
  3. 完整配置子地址：多仓清单 urls 里指向完整配置的 http(s) 地址，
     探活能解析出 sites 才收。

设计原则：
  - 只用标准库，复用 update.py 的 http_get / parse_jsonc / parse_live_channels
  - 只"发现与验证"，真正是否纳入由 update.py 的探活+剔除+降级逻辑决定
  - discovered.json 带来源标记，便于 health.json 区分手工源与发现源
  - 失败种子不影响其他种子；整体异常不覆盖已有 discovered.json
"""
import json
import os
import sys
import re
from urllib.parse import urlsplit, urlunsplit
from concurrent.futures import ThreadPoolExecutor, as_completed

import update as U

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS_FILE = os.path.join(BASE_DIR, "discovery_seeds.json")
OUT = os.path.join(BASE_DIR, "discovered.json")

# 明确排除：非 http(s)、相对路径、代理协议、脚本、带鉴权参数
BAD_URL_PREFIX = ("proxy://", "./", "/", "cl://", "file://")
SCRIPT_EXT = (".py", ".js")
# 付费/鉴权/占位参数（常见于"会员线路"，非公开可用）
BAD_PARAM_RE = re.compile(r"([?&](token|key|auth|vip|password|pwd)=)", re.I)
# 名字含"会员/付费/赞助"的多为账号共享线路，不符合公开订阅定位，排除
BAD_LIVE_NAME_RE = re.compile(r"(会员|付费|赞助|vip|过期)", re.I)


def log(msg):
    U.log("[发现] " + msg)


def punycode(url):
    """中文域名转 punycode，否则 urllib 会 UnicodeEncodeError。"""
    try:
        sp = urlsplit(url)
    except Exception:
        return url
    host = sp.netloc
    try:
        host.encode("ascii")
        return url
    except UnicodeEncodeError:
        parts = host.split(".")
        host = ".".join(
            p.encode("idna").decode("ascii") if any(ord(c) > 127 for c in p) else p
            for p in parts
        )
        return urlunsplit((sp.scheme, host, sp.path, sp.query, sp.fragment))


def is_http(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def good_candidate_url(url):
    """通用可用性预判：排除明显的非独立/非公开地址。"""
    if not is_http(url):
        return False
    if BAD_PARAM_RE.search(url):
        return False
    path = urlsplit(url).path.lower()
    if path.endswith(SCRIPT_EXT):  # drpy/py 脚本，依赖运行环境，非独立源
        return False
    return True


def good_live_url(url):
    """直播订阅地址预判。"""
    if not good_candidate_url(url):
        return False
    if url.startswith(BAD_URL_PREFIX):
        return False
    # 排除明显不是订阅的地址（图片、页面锚点）
    if re.search(r"\.(png|jpg|jpeg|gif|webp)(\?|$)", url, re.I):
        return False
    return True


def good_direct_api(api):
    """苹果CMS V10 直链接口预判。"""
    if not good_candidate_url(api):
        return False
    # 只收 provide/vod 标准接口；drpy/py 脚本与云盘直链排除
    if "provide/vod" not in api.lower():
        return False
    return True


def load_seeds():
    with open(SEEDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_seed(seed, timeout):
    """展开一个种子，返回 (candidate_lives, candidate_directs, candidate_configs, note)。

    candidate_* 元素为 {name, url, from}（direct 用 api 字段）。
    """
    name = seed.get("name", "?")
    url = seed.get("url", "")
    ok, text, info = U.http_get(punycode(url), timeout=timeout, max_bytes=2 * 1024 * 1024)
    if not ok:
        return [], [], [], "探活失败:%s" % (info.get("error") or info.get("status"))

    try:
        data = U.parse_jsonc(text)
    except Exception as e:
        return [], [], [], "解析失败:%s" % str(e)[:50]

    if not isinstance(data, dict):
        return [], [], [], "顶层非对象"

    lives, directs, configs = [], [], []

    # 1) 完整配置子地址（多仓清单 urls）
    suburls = data.get("urls")
    if isinstance(suburls, list):
        for u in suburls:
            if isinstance(u, dict) and good_candidate_url(u.get("url", "")):
                configs.append({"name": u.get("name") or name, "url": u["url"], "from": name})

    # 2) 直播订阅（排除会员/付费/赞助类账号共享线路）
    for lv in (data.get("lives") or []):
        if not isinstance(lv, dict):
            continue
        if BAD_LIVE_NAME_RE.search(str(lv.get("name", ""))):
            continue
        if good_live_url(lv.get("url", "")):
            lives.append({"name": lv.get("name") or name, "url": lv["url"], "from": name})

    # 3) 苹果CMS 直链站点
    for s in (data.get("sites") or []):
        if isinstance(s, dict) and good_direct_api(s.get("api", "")):
            directs.append({"name": s.get("name") or name, "api": s["api"], "from": name})

    return lives, directs, configs, ""


def verify_live(c, min_channels, max_channels, timeout):
    ok, text, info = U.http_get(punycode(c["url"]), timeout=timeout, max_bytes=4 * 1024 * 1024)
    if not ok:
        return None
    head = (text or "")[:200].lower()
    if "<html" in head or "<!doctype" in head:
        return None
    fmt = "m3u" if "#extm3u" in head else "txt"
    channels = U.parse_live_channels(text, fmt)
    # 过小=不可信；过大=会让 all.m3u 膨胀拖慢客户端，均排除
    if len(channels) < min_channels or len(channels) > max_channels:
        return None
    return {"name": c["name"], "url": c["url"], "from": c["from"],
            "fmt": fmt, "channels": len(channels)}


def verify_direct(c, timeout):
    ok, text, info = U.http_get(punycode(c["api"]), timeout=timeout, max_bytes=512 * 1024)
    if not ok:
        return None
    head = (text or "")[:200].lower()
    if "<html" in head or "<!doctype" in head:
        return None
    try:
        data = U.parse_jsonc(text)
    except Exception:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        return None
    return {"name": c["name"], "api": c["api"], "from": c["from"], "count": len(data["list"])}


def verify_config(c, timeout, min_bytes):
    ok, text, info = U.http_get(punycode(c["url"]), timeout=timeout, max_bytes=2 * 1024 * 1024)
    if not ok:
        return None
    cok, sites, lives, msg = U.parse_config_source(text, min_bytes)
    if not cok or not sites:
        return None
    return {"name": c["name"], "url": c["url"], "from": c["from"], "sites": len(sites)}


def dedup(items, key):
    seen = set()
    out = []
    for it in items:
        k = it.get(key, "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def main():
    log("开始从知名影视仓源发现候选地址 ...")
    seeds_conf = load_seeds()
    seeds = seeds_conf.get("seeds", [])
    st = seeds_conf.get("settings", {})
    timeout = int(st.get("timeout", 12))
    max_workers = int(st.get("max_workers", 10))
    min_channels = int(st.get("min_live_channels", 3))
    max_channels = int(st.get("max_channels_per_source", 1500))
    max_total_channels = int(st.get("max_discovered_channels_total", 6000))
    max_lives = int(st.get("max_lives", 40))
    max_direct = int(st.get("max_direct", 40))
    max_configs = int(st.get("max_configs", 20))

    # 1) 并发展开种子
    all_lives, all_directs, all_configs, seed_notes = [], [], [], []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(expand_seed, s, timeout): s for s in seeds}
        for fut in as_completed(futs):
            s = futs[fut]
            try:
                lives, directs, configs, note = fut.result()
            except Exception as e:
                lives, directs, configs, note = [], [], [], "异常:%s" % str(e)[:60]
            all_lives.extend(lives)
            all_directs.extend(directs)
            all_configs.extend(configs)
            seed_notes.append({"name": s.get("name"), "url": s.get("url"), "note": note or "OK"})

    cand_lives = dedup(all_lives, "url")
    cand_directs = dedup(all_directs, "api")
    cand_configs = dedup(all_configs, "url")
    log("种子 %d 个：候选直播 %d / 直链 %d / 完整配置 %d（去重后）" %
        (len(seeds), len(cand_lives), len(cand_directs), len(cand_configs)))

    # 2) 并发验证候选
    good_lives, good_directs, good_configs = [], [], []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fl = {ex.submit(verify_live, c, min_channels, max_channels, timeout): c for c in cand_lives}
        for fut in as_completed(fl):
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                good_lives.append(r)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fd = {ex.submit(verify_direct, c, timeout): c for c in cand_directs}
        for fut in as_completed(fd):
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                good_directs.append(r)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fc = {ex.submit(verify_config, c, timeout, 300): c for c in cand_configs}
        for fut in as_completed(fc):
            try:
                r = fut.result()
            except Exception:
                r = None
            if r:
                good_configs.append(r)

    # 频道数从少到多取（小源优先，保证来源多样性：虎牙/体育/B站等特色源不会被大清单挤掉），
    # 同时设全局频道预算，避免所有大清单叠加把 all.m3u 撑爆。
    good_lives.sort(key=lambda x: x["channels"])
    budget_lives = []
    spent = 0
    for lv in good_lives:
        if len(budget_lives) >= max_lives or spent >= max_total_channels:
            break
        budget_lives.append(lv)
        spent += lv["channels"]
    good_lives = budget_lives
    good_directs.sort(key=lambda x: (x["from"], x["name"]))
    good_configs.sort(key=lambda x: (x["from"], x["name"]))
    good_directs = good_directs[:max_direct]
    good_configs = good_configs[:max_configs]

    log("验证通过：直播 %d / 直链 %d / 完整配置 %d（直播频道预算 %d/%d）" %
        (len(good_lives), len(good_directs), len(good_configs),
         sum(x["channels"] for x in good_lives), max_total_channels))

    result = {
        "generated_at": U.now_cn().strftime("%Y-%m-%d %H:%M:%S UTC+8"),
        "seed_count": len(seeds),
        "seeds": seed_notes,
        "stats": {
            "live_ok": len(good_lives),
            "direct_ok": len(good_directs),
            "config_ok": len(good_configs),
        },
        "lives": good_lives,
        "direct_sites": good_directs,
        "configs": good_configs,
    }
    U.atomic_write(OUT, json.dumps(result, ensure_ascii=False, indent=2))
    log("已写入 discovered.json（直播 %d / 直链 %d / 完整配置 %d）" %
        (len(good_lives), len(good_directs), len(good_configs)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("致命错误：%s" % e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
