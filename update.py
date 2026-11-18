#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 源自动聚合更新器
============================================================
功能：
  1. 读取 sources.json 中的候选「配置源」和「直播源」
  2. 并发 HTTP 探活：能访问 + 结构合法 => 保留；失效 => 自动剔除
  3. 把有效配置源的 sites 合并去重 -> 一个 config.json（通用 TVBox 格式）
  4. 把有效直播源合并 -> 一个 all.m3u（TVBox lives 直接引用）
  5. 生成 health.json 健康报告（每个源的死活、频道数、耗时）
  6. 保留最近 N 天的历史快照，便于回溯

设计原则：
  - 只用 Python 标准库，GitHub Actions / 任何 Python 3.8+ 环境可直接运行
  - 容错解析 JSONC（注释、尾随逗号、BOM、重复 key），这是影视配置的常态
  - 探活不"下载全量再判断"，够用即停，避免大文件拖慢
  - 聚合结果原子写入（先写临时文件再替换），避免客户端读到半截文件
"""

import json
import os
import re
import sys
import time
import shutil
import tempfile
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(BASE_DIR, "sources.json")
CONFIG_OUT = os.path.join(BASE_DIR, "config.json")
FONGMI_OUT = os.path.join(BASE_DIR, "fongmi.json")
LIVE_M3U_OUT = os.path.join(BASE_DIR, "all.m3u")
LIVE_TXT_OUT = os.path.join(BASE_DIR, "all.txt")
HEALTH_OUT = os.path.join(BASE_DIR, "health.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
HISTORY_DIR = os.path.join(BASE_DIR, "history")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TZ_CN = timezone(timedelta(hours=8))

# 忽略 SSL 校验：部分源证书链不全，探活阶段以"内容是否可用"为准
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def now_cn():
    return datetime.now(TZ_CN)


def log(msg):
    print("[%s] %s" % (now_cn().strftime("%H:%M:%S"), msg), flush=True)


# ----------------------------------------------------------------------------
# HTTP 探活
# ----------------------------------------------------------------------------
def http_get(url, timeout=18, max_bytes=4 * 1024 * 1024, retries=2):
    """返回 (ok:bool, text:str, info:dict)。info 含 status/bytes/ms/error/retryable。

    网络类错误（超时/连接/SSL）会自动重试 retries 次，缓解网络抖动误杀。
    """
    info = {"status": 0, "bytes": 0, "ms": 0, "error": "", "retryable": False}
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    })
    start = datetime.now()
    last_err = ""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                info["status"] = resp.getcode()
                chunks = []
                total = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= max_bytes:
                        break
                raw = b"".join(chunks)
                info["bytes"] = len(raw)
                text = None
                for enc in ("utf-8-sig", "utf-8", "gbk"):
                    try:
                        text = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                if text is None:
                    text = raw.decode("utf-8", errors="ignore")
                info["ms"] = int((datetime.now() - start).total_seconds() * 1000)
                info["error"] = ""
                info["retryable"] = False
                ok = 200 <= info["status"] < 400 and len(raw) > 0
                return ok, text, info
        except urllib.error.HTTPError as e:
            # HTTP 4xx/5xx 是确定性响应，不重试
            info["status"] = e.code
            last_err = "HTTP %s" % e.code
            info["retryable"] = False
            break
        except Exception as e:
            last_err = "%s: %s" % (type(e).__name__, str(e)[:100])
            info["retryable"] = True
            if attempt < retries:
                time.sleep(1.2 * (attempt + 1))
                continue
    info["ms"] = int((datetime.now() - start).total_seconds() * 1000)
    info["error"] = last_err
    return False, "", info


# ----------------------------------------------------------------------------
# JSONC 容错解析（去注释 + 去尾逗号 + BOM）
# ----------------------------------------------------------------------------
def strip_json_comments(s):
    """逐字符扫描，剔除 // 与 /* */ 注释，但保留字符串内的 //（URL 会用到）。"""
    out = []
    i, n = 0, len(s)
    in_str = False
    esc = False
    while i < n:
        c = s[i]
        if in_str:
            # 字符串内的裸换行/回车/制表符是非法的，替换为空格（保住 JSON 合法性）
            if c in "\r\n\t":
                out.append(" ")
            else:
                out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            i += 2
            while i < n and s[i] not in "\r\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_jsonc(text):
    """把 JSONC 解析成 dict；失败抛异常。"""
    cleaned = strip_json_comments(text)
    # 去尾逗号：, } 和 , ] 里的逗号。用循环以处理多重尾逗号。
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    # 剥离字符串外的裸控制字符（部分源含非法 \\x00-\\x1f 导致 json 报错）
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    return json.loads(cleaned)


# ----------------------------------------------------------------------------
# 配置源处理
# ----------------------------------------------------------------------------
def parse_config_source(text, min_bytes):
    """解析一个配置源文本，返回 (ok, sites:list, lives:list, msg)。"""
    if len(text.encode("utf-8", errors="ignore")) < min_bytes:
        return False, [], [], "内容过小"
    try:
        data = parse_jsonc(text)
    except Exception as e:
        return False, [], [], "JSON解析失败(%s)" % str(e)[:60]
    if not isinstance(data, dict):
        return False, [], [], "顶层不是对象"

    sites = data.get("sites") or []
    if isinstance(sites, dict):
        sites = list(sites.values())
    if not isinstance(sites, list):
        sites = []
    # 只保留 dict 形态的站点，且必须有 key/name/api 之一
    valid_sites = []
    for s in sites:
        if isinstance(s, dict) and ("api" in s or "key" in s or "name" in s):
            valid_sites.append(s)

    lives = data.get("lives") or []
    if not isinstance(lives, list):
        lives = []
    valid_lives = [x for x in lives if isinstance(x, dict)]

    if not valid_sites and not valid_lives:
        return False, [], [], "无有效sites/lives"
    return True, valid_sites, valid_lives, ""


def probe_config(item, min_bytes, timeout):
    name = item.get("name", "?")
    url = item.get("url", "")
    ok, text, info = http_get(url, timeout=timeout)
    result = {
        "name": name, "url": url, "kind": "config",
        "ok": False, "sites": 0, "lives": 0,
        "bytes": info["bytes"], "ms": info["ms"],
        "status": info["status"], "reason": "",
        "retryable": info.get("retryable", False),
    }
    if not ok:
        result["reason"] = info["error"] or ("HTTP %s" % info["status"])
        return result, [], []

    # 先尝试多仓结构：只有 urls 且元素为 {url,name} 的二级订阅
    try:
        probe = parse_jsonc(text)
        if isinstance(probe, dict) and set(probe.keys()) <= {"urls"} and isinstance(probe.get("urls"), list):
            sub_urls = []
            for u in probe["urls"]:
                if isinstance(u, dict) and u.get("url", "").startswith(("http://", "https://")):
                    sub_urls.append(u["url"])
            if sub_urls:
                sub_sites = []
                sub_ok = 0
                for su in sub_urls[:20]:  # 限制展开数量，避免爆炸
                    sok, stext, _ = http_get(su, timeout=timeout)
                    if not sok:
                        continue
                    cok, ssites, _, _ = parse_config_source(stext, min_bytes)
                    if cok and ssites:
                        sub_sites.extend(ssites)
                        sub_ok += 1
                if sub_ok:
                    result["ok"] = True
                    result["sites"] = len(sub_sites)
                    result["reason"] = "多仓展开%d/%d" % (sub_ok, len(sub_urls))
                    return result, sub_sites, []
                result["reason"] = "多仓子源全失效"
                return result, [], []
    except Exception:
        pass  # 不是多仓结构，走正常解析

    cok, sites, lives, msg = parse_config_source(text, min_bytes)
    if not cok:
        result["reason"] = msg
        return result, [], []
    result["ok"] = True
    result["sites"] = len(sites)
    result["lives"] = len(lives)
    return result, sites, lives


# ----------------------------------------------------------------------------
# 直播源处理
# ----------------------------------------------------------------------------
def parse_live_channels(text, fmt):
    """从 m3u / txt 中提取频道，返回 [{name,url,logo?,group?}]。"""
    channels = []
    lines = [ln.strip() for ln in text.splitlines()]
    if fmt == "m3u" or (lines and lines[0].upper().startswith("#EXTM3U")):
        cur = {}
        for ln in lines:
            if not ln:
                continue
            if ln.startswith("#EXTINF"):
                cur = {"name": "", "url": "", "logo": "", "group": ""}
                m = re.search(r'group-title="([^"]*)"', ln)
                if m:
                    cur["group"] = m.group(1)
                m = re.search(r'tvg-logo="([^"]*)"', ln)
                if m:
                    cur["logo"] = m.group(1)
                # 名称：tvg-name 优先，否则取逗号后
                m = re.search(r'tvg-name="([^"]*)"', ln)
                if m and m.group(1):
                    cur["name"] = m.group(1)
                else:
                    comma = ln.rfind(",")
                    if comma >= 0:
                        cur["name"] = ln[comma + 1:].strip()
            elif ln.startswith("#"):
                continue
            elif (ln.startswith("http://") or ln.startswith("https://") or ln.startswith("rtmp://")):
                if cur:
                    cur["url"] = ln
                    if cur["name"] and cur["url"]:
                        channels.append(cur)
                    cur = {}
                else:
                    channels.append({"name": "频道%d" % (len(channels) + 1), "url": ln})
    else:
        # txt: 名称,URL
        for ln in lines:
            if not ln or ln.startswith("#"):
                continue
            if "," in ln:
                name, url = ln.split(",", 1)
                name, url = name.strip(), url.strip()
                if url.startswith(("http://", "https://", "rtmp://")):
                    channels.append({"name": name or "频道%d" % (len(channels) + 1), "url": url})
    return channels


def probe_live(item, min_channels, timeout):
    name = item.get("name", "?")
    url = item.get("url", "")
    fmt = item.get("fmt", "m3u")
    ok, text, info = http_get(url, timeout=timeout, max_bytes=8 * 1024 * 1024)
    result = {
        "name": name, "url": url, "kind": "live",
        "ok": False, "channels": 0,
        "bytes": info["bytes"], "ms": info["ms"],
        "status": info["status"], "reason": "",
        "retryable": info.get("retryable", False),
    }
    if not ok:
        result["reason"] = info["error"] or ("HTTP %s" % info["status"])
        return result, []
    channels = parse_live_channels(text, fmt)
    if len(channels) < min_channels:
        result["reason"] = "频道数不足(%d<%d)" % (len(channels), min_channels)
        return result, []
    result["ok"] = True
    result["channels"] = len(channels)
    return result, channels


# ----------------------------------------------------------------------------
# 聚合与写出
# ----------------------------------------------------------------------------
def merge_sites(site_batches):
    """按 api/key+name 去重合并 sites。返回合并后的 list。"""
    seen = set()
    merged = []
    for batch in site_batches:
        for s in batch:
            # 身份标识：优先 api，其次 key，再 name
            ident = str(s.get("api") or s.get("key") or s.get("name") or "").strip()
            ident = re.sub(r"\s+", "", ident)
            if not ident or ident in seen:
                continue
            seen.add(ident)
            merged.append(s)
    return merged


def atomic_write(path, text):
    """原子写：先写同目录临时文件再替换，避免客户端读到半截文件。"""
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def build_config(merged_sites, valid_live_sources, health, generated_at):
    """生成通用 TVBox 配置 dict。"""
    lives = []
    for lv in valid_live_sources:
        entry = {
            "name": lv["name"],
            "type": 0,
            "url": lv["url"],
        }
        if lv.get("epg"):
            entry["epg"] = lv["epg"]
        lives.append(entry)

    cfg = {
        "urls": {},  # 通用格式：urls 留空，主用 sites
        "sites": merged_sites,
        "lives": lives,
        "wallpaper": "https://api.dujin.org/bing/1920.php",
        "_meta": {
            "generated_at": generated_at,
            "site_count": len(merged_sites),
            "live_source_count": len(lives),
            "note": "由 tvbox-source 自动聚合；源健康状态见 health.json",
        },
    }
    return cfg


def build_fongmi_config(sources, generated_at, timeout):
    """生成影视仓/FongMi 专用「配置地址清单」。

    影视仓的「配置地址」期待的格式是：
        {"urls": [{"name": "源名", "url": "完整配置地址"}, ...]}
    每个 url 指向一个带 spider 的完整原始配置（保持原样，不拆解 sites），
    影视仓自己下载解析。这样 csp_ 内置类、jar、drpy 脚本都能正常工作。

    数据来源：
      1. fongmi_seeds.json —— 实测有效的优质种子清单
      2. sources.json 的 configs —— 我们调研的配置源地址
    对每个地址做 URL 级探活，剔除打不开/非配置内容的。
    """
    candidates = []

    # 1) 种子清单
    seed_file = os.path.join(BASE_DIR, "fongmi_seeds.json")
    if os.path.exists(seed_file):
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                seed = json.load(f)
            for item in seed.get("urls", []):
                if item.get("url"):
                    candidates.append({"name": item.get("name", "源"), "url": item["url"]})
        except Exception as e:
            log("  读取种子清单失败: %s" % e)

    # 2) sources.json 的配置源（作为完整地址，而非拆解）
    for it in sources.get("configs", []):
        if it.get("url"):
            candidates.append({"name": it.get("name", "源"), "url": it["url"]})

    # 按 url 去重
    seen = set()
    unique = []
    for c in candidates:
        u = c["url"].strip()
        if not u or u in seen:
            continue
        seen.add(u)
        unique.append({"name": c["name"], "url": u})

    # 并发探活每个完整配置地址
    def check(c):
        ok, text, info = http_get(c["url"], timeout=min(timeout, 12), max_bytes=65536)
        usable = ok and info["bytes"] > 100
        # 排除明显的非配置内容（HTML 错误页等）
        head = text[:200].lower() if text else ""
        if usable and ("<html" in head or "<!doctype" in head):
            usable = False
        return usable, c, info

    urls = []
    dead = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for usable, c, info in ex.map(check, unique):
            if usable:
                urls.append({"name": c["name"], "url": c["url"]})
            else:
                dead.append({"name": c["name"], "url": c["url"],
                             "reason": info.get("error", "") or ("HTTP %s" % info.get("status", 0))})

    result = {"urls": urls}
    return result, len(unique), len(urls), dead


def build_m3u(channels, generated_at):
    lines = ["#EXTM3U", "# Generated by tvbox-source at %s" % generated_at]
    seen = set()
    count = 0
    for ch in channels:
        url = ch.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        name = ch.get("name") or ("频道%d" % (count + 1))
        logo = ch.get("logo", "")
        group = ch.get("group", "")
        attrs = 'group-title="%s" tvg-name="%s"' % (group or "聚合直播", name)
        if logo:
            attrs += ' tvg-logo="%s"' % logo
        lines.append("#EXTINF:-1 %s,%s" % (attrs, name))
        lines.append(url)
        count += 1
    return "\n".join(lines) + "\n", count


def save_history(health, cfg, keep_days):
    """保存当日快照到 history/，并清理过期文件。"""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    day = now_cn().strftime("%Y-%m-%d")
    snapshot = {
        "date": day,
        "health": health,
        "site_count": len(cfg.get("sites", [])),
        "live_count": len(cfg.get("lives", [])),
    }
    atomic_write(os.path.join(HISTORY_DIR, "health-%s.json" % day),
                 json.dumps(snapshot, ensure_ascii=False, indent=2))
    # 清理过期
    cutoff = now_cn() - timedelta(days=keep_days)
    for fn in os.listdir(HISTORY_DIR):
        m = re.match(r"health-(\d{4}-\d{2}-\d{2})\.json$", fn)
        if not m:
            continue
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=TZ_CN)
            if d < cutoff:
                os.unlink(os.path.join(HISTORY_DIR, fn))
        except ValueError:
            pass


# ----------------------------------------------------------------------------
# 状态持久化：连续失败计数，避免网络抖动误杀
# ----------------------------------------------------------------------------
def load_state():
    """state.json: {源url: {"fail_streak": int, "last_ok": "日期", "site_count": int}}"""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def decide_source(rep, it, state, fail_threshold):
    """根据本次探活结果与历史状态，决定该源本次是否纳入聚合。

    核心规则：
      - 探活成功 => 立即恢复（fail_streak 清零）
      - 确定性失败（非 retryable：解析失败/加密/无内容/频道不足/HTTP错误）
        => fail_streak +1，达到阈值才剔除；期间"暂留"但本次不贡献数据
      - 网络抖动失败（retryable）=> fail_streak 不累加（宽容处理）
    返回 (adopt: bool, changed: bool)
    """
    url = it.get("url", "")
    prev = state.get(url, {})
    streak = int(prev.get("fail_streak", 0))
    if rep["ok"]:
        state[url] = {"fail_streak": 0, "last_ok": now_cn().strftime("%Y-%m-%d"),
                      "site_count": rep.get("sites", rep.get("channels", 0))}
        return True, (streak != 0)
    # 失败
    if not rep.get("retryable", False):
        streak += 1
        rep["reason"] = "%s [连续失败%d/%d]" % (rep.get("reason", ""), streak, fail_threshold)
    else:
        rep["reason"] = "%s [网络抖动,不计入剔除]" % rep.get("reason", "")
    state[url] = {"fail_streak": streak,
                  "last_ok": prev.get("last_ok", ""),
                  "site_count": prev.get("site_count", 0)}
    # 达到阈值 -> 剔除；否则暂留（本次不纳入数据，但状态保留）
    return False, True


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main():
    log("开始更新 TVBox 源 ...")
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        sources = json.load(f)

    settings = sources.get("settings", {})
    timeout = int(settings.get("timeout", 18))
    max_workers = int(settings.get("max_workers", 8))
    min_bytes = int(settings.get("min_config_bytes", 300))
    min_channels = int(settings.get("min_live_channels", 3))
    keep_days = int(settings.get("keep_history_days", 30))
    fail_threshold = int(settings.get("fail_threshold", 3))

    config_items = sources.get("configs", [])
    live_items = sources.get("lives", [])
    generated_at = now_cn().strftime("%Y-%m-%d %H:%M:%S UTC+8")
    state = load_state()

    # 并发探活配置源
    log("探活 %d 个配置源 ..." % len(config_items))
    config_reports = []
    site_batches = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(probe_config, it, min_bytes, timeout): it for it in config_items}
        for fut in as_completed(futures):
            it = futures[fut]
            try:
                rep, sites, lives = fut.result()
            except Exception as e:
                rep = {"name": it.get("name"), "url": it.get("url"), "kind": "config",
                       "ok": False, "reason": "异常:%s" % str(e)[:80], "retryable": True}
                sites = []
            adopt, _ = decide_source(rep, it, state, fail_threshold)
            rep["adopted"] = adopt
            config_reports.append(rep)
            if adopt and sites:
                site_batches.append(sites)
                log("  ✓ 配置源 %-10s sites=%d (%dms)" % (rep["name"], rep["sites"], rep["ms"]))
            else:
                tag = "剔除" if (not adopt and state.get(it.get("url", ""), {}).get("fail_streak", 0) >= fail_threshold) else "暂离"
                log("  ✗ 配置源 %-10s %s：%s" % (rep["name"], tag, rep["reason"]))

    # 并发探活直播源
    log("探活 %d 个直播源 ..." % len(live_items))
    live_reports = []
    all_channels = []
    valid_live_sources = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(probe_live, it, min_channels, timeout): it for it in live_items}
        for fut in as_completed(futures):
            it = futures[fut]
            try:
                rep, channels = fut.result()
            except Exception as e:
                rep = {"name": it.get("name"), "url": it.get("url"), "kind": "live",
                       "ok": False, "reason": "异常:%s" % str(e)[:80], "retryable": True}
                channels = []
            adopt, _ = decide_source(rep, it, state, fail_threshold)
            rep["adopted"] = adopt
            live_reports.append(rep)
            if adopt and channels:
                all_channels.extend(channels)
                valid_live_sources.append(it)
                log("  ✓ 直播源 %-10s 频道=%d (%dms)" % (rep["name"], rep["channels"], rep["ms"]))
            else:
                log("  ✗ 直播源 %-10s 暂离/剔除：%s" % (rep["name"], rep["reason"]))

    # 合并
    merged_sites = merge_sites(site_batches)
    log("合并去重后 sites=%d 个" % len(merged_sites))

    cfg = build_config(merged_sites, valid_live_sources, {}, generated_at)
    m3u_text, uniq_channels = build_m3u(all_channels, generated_at)

    # 生成影视仓专用「配置地址清单」（完整地址 + 探活，影视仓正确格式）
    log("生成影视仓配置地址清单（探活完整配置源）...")
    fongmi_cfg, fongmi_total, fongmi_ok, fongmi_dead = build_fongmi_config(
        sources, generated_at, timeout)
    log("  影视仓清单：候选 %d 个 → 可用 %d 个，失效 %d 个" %
        (fongmi_total, fongmi_ok, len(fongmi_dead)))

    # 降级保护：某一类有效源骤降（疑似网络异常）时，保留该类上次产出，避免清空
    degraded_cfg = False
    degraded_live = False
    if os.path.exists(HEALTH_OUT):
        try:
            with open(HEALTH_OUT, "r", encoding="utf-8") as f:
                prev_health = json.load(f)
            prev_sites = prev_health.get("summary", {}).get("sites_merged", 0)
            prev_live = prev_health.get("summary", {}).get("live_ok", 0)
            # 配置骤降：上次 >20，本次掉到 30% 以下
            if prev_sites > 20 and merged_sites < prev_sites * 0.3:
                degraded_cfg = True
            # 直播骤降：上次有效，本次全挂
            if prev_live > 0 and uniq_channels == 0:
                degraded_live = True
        except Exception:
            pass

    degraded = degraded_cfg or degraded_live
    if degraded:
        log("⚠ 检测到有效源骤降（配置=%s 直播=%s），疑似网络异常：保留该类上次成果，仅更新 health" %
            ("降级" if degraded_cfg else "正常", "降级" if degraded_live else "正常"))

    if not degraded_cfg:
        atomic_write(CONFIG_OUT, json.dumps(cfg, ensure_ascii=False, indent=2))
        atomic_write(FONGMI_OUT, json.dumps(fongmi_cfg, ensure_ascii=False, indent=2))
    if not degraded_live:
        atomic_write(LIVE_M3U_OUT, m3u_text)
        txt_lines = []
        seen = set()
        for ch in all_channels:
            u = ch.get("url", "")
            if not u or u in seen:
                continue
            seen.add(u)
            txt_lines.append("%s,%s" % (ch.get("name", ""), u))
        atomic_write(LIVE_TXT_OUT, "\n".join(txt_lines) + "\n")

    # 状态落盘
    atomic_write(STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2))

    # 健康报告
    health = {
        "generated_at": generated_at,
        "degraded": degraded,
        "summary": {
            "config_total": len(config_items),
            "config_ok": sum(1 for r in config_reports if r["ok"]),
            "config_dead": sum(1 for r in config_reports if not r["ok"]),
            "live_total": len(live_items),
            "live_ok": sum(1 for r in live_reports if r["ok"]),
            "live_dead": sum(1 for r in live_reports if not r["ok"]),
            "sites_merged": len(merged_sites),
            "live_channels": uniq_channels,
            "fongmi_total": fongmi_total,
            "fongmi_ok": fongmi_ok,
            "degraded_cfg": degraded_cfg,
            "degraded_live": degraded_live,
        },
        "configs": sorted(config_reports, key=lambda x: x["name"]),
        "lives": sorted(live_reports, key=lambda x: x["name"]),
        "removed": [
            {"name": r["name"], "url": r["url"], "kind": r["kind"], "reason": r.get("reason", "")}
            for r in (config_reports + live_reports)
            if not r.get("adopted", False)
            and state.get(r.get("url", ""), {}).get("fail_streak", 0) >= fail_threshold
        ],
        "observing": [
            {"name": r["name"], "reason": r.get("reason", "")}
            for r in (config_reports + live_reports)
            if not r.get("adopted", False)
            and 0 < state.get(r.get("url", ""), {}).get("fail_streak", 0) < fail_threshold
        ],
    }
    atomic_write(HEALTH_OUT, json.dumps(health, ensure_ascii=False, indent=2))

    # 历史快照仅在非降级时记录
    if not degraded:
        save_history(health, cfg, keep_days)

    s = health["summary"]
    log("完成：配置源 %d/%d 有效，直播源 %d/%d 有效，sites=%d，直播频道=%d，永久剔除=%d，观察中=%d%s" %
        (s["config_ok"], s["config_total"], s["live_ok"], s["live_total"],
         s["sites_merged"], s["live_channels"], len(health["removed"]),
         len(health["observing"]), " [降级保护]" if degraded else ""))
    log("输出：config.json / all.m3u / all.txt / health.json / state.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("致命错误：%s" % e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
