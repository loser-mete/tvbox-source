#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_mirrors.py —— 国内镜像可用性测速（零第三方依赖）

背景：myfav.json 的 spider 字段是相对路径 ./spider.jar，
影视仓会用「加载配置的地址」去取同目录的 spider.jar。
所以一个镜像「可用」必须同时满足：
  1) myfav.json 能完整返回且是合法配置；
  2) spider.jar 能完整下载（1700116 字节）且 md5 匹配。
很多镜像 json 能开、jar 却 403 或中途断流 —— 本脚本会逐一实测戳穿。

用法：
  python check_mirrors.py                # 测全部内置镜像
  python check_mirrors.py --file config.json   # 换一个配置文件测
  python check_mirrors.py --timeout 40         # 调整超时（秒）

★ 请在你要使用的实际网络环境（如移动宽带）里跑一次，
  本机结果只代表本机线路，移动宽带出口不同、结果可能不同。

判据：真实读取 body 并校验字节数 / md5 / JSON 结构，
      绝不只看 HTTP 状态码（假 200 / 0B 是常见坑）。
"""
import argparse
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://raw.githubusercontent.com/loser-mete/tvbox-source/main/"
JAR_NAME = "spider.jar"
JAR_SIZE = 1700116
JAR_MD5 = "decb609b673019e18512dc3a96b6a252"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# (显示名, URL 模板) —— {f} 会被替换成文件名
MIRRORS = [
    ("GitHub 原站",        "{b}{f}"),
    ("ghfast.top",         "https://ghfast.top/{b}{f}"),
    ("gh-proxy.com",       "https://gh-proxy.com/{b}{f}"),
    ("cdn.gh-proxy.com",   "https://cdn.gh-proxy.com/{b}{f}"),
    ("gh.llkk.cc",         "https://gh.llkk.cc/{b}{f}"),
    ("ghproxy.net",        "https://ghproxy.net/{b}{f}"),
    ("github.moeyy.xyz",   "https://github.moeyy.xyz/{b}{f}"),
    ("down.nigx.cn",       "https://down.nigx.cn/{b}{f}"),
    ("gh-proxy.org",       "https://gh-proxy.org/{b}{f}"),
    ("gh.xiu.org",         "https://gh.xiu.org/{b}{f}"),
]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def fetch(url, timeout):
    """返回 (ok, bytes, elapsed_ms, err)。真实读完整 body。"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            data = r.read()
            code = getattr(r, "status", 200)
        ms = int((time.time() - t0) * 1000)
        if code != 200:
            return False, data, ms, "HTTP %d" % code
        return True, data, ms, ""
    except Exception as e:
        return False, b"", int((time.time() - t0) * 1000), "%s: %s" % (type(e).__name__, str(e)[:60])


def check_json(data):
    if len(data) < 1000:
        return False, "体积过小 %dB" % len(data)
    head = data[:200].lower()
    if b"<html" in head or b"<!doctype" in head:
        return False, "返回网页而非 JSON"
    try:
        d = json.loads(data.decode("utf-8", "replace"))
    except Exception as e:
        return False, "JSON 解析失败 %s" % str(e)[:40]
    if not isinstance(d, dict) or "sites" not in d:
        return False, "不是有效配置(缺 sites)"
    return True, "sites=%d spider=%s" % (len(d.get("sites", [])), "有" if d.get("spider") else "无")


def check_jar(data):
    md5 = hashlib.md5(data).hexdigest()
    if len(data) != JAR_SIZE:
        return False, "体积 %dB(应 %dB)" % (len(data), JAR_SIZE)
    if md5 != JAR_MD5:
        return False, "md5 %s 不符" % md5
    return True, "体积/md5 完全一致"


def probe(name, tpl, cfg, timeout):
    jurl = tpl.format(b=BASE, f=cfg)
    rurl = tpl.format(b=BASE, f=JAR_NAME)
    ok_j, jb, ms_j, err_j = fetch(jurl, timeout)
    ok_r, rb, ms_r, err_r = fetch(rurl, timeout)
    jok, jinfo = check_json(jb) if ok_j else (False, err_j)
    rok, rinfo = check_jar(rb) if ok_r else (False, err_r)
    usable = jok and rok
    return {
        "name": name, "usable": usable,
        "json": (jok, len(jb), ms_j, jinfo),
        "jar": (rok, len(rb), ms_r, rinfo),
        "total_ms": ms_j + ms_r,
        "jurl": jurl,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="myfav.json", help="要测的配置文件名")
    ap.add_argument("--timeout", type=int, default=35, help="单文件超时秒数")
    args = ap.parse_args()

    print("=" * 78)
    print("国内镜像可用性实测  |  配置=%s  jar=%s (%dB)" % (args.file, JAR_MD5[:12], JAR_SIZE))
    print("判据：json 可解析 + jar 体积/md5 完全一致，两者都过才算可用")
    print("=" * 78)

    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(probe, n, t, args.file, args.timeout): n for n, t in MIRRORS}
        for fu in as_completed(futs):
            try:
                results.append(fu.result())
            except Exception as e:
                results.append({"name": futs[fu], "usable": False, "total_ms": 999999,
                                "json": (False, 0, 0, str(e)[:50]),
                                "jar": (False, 0, 0, ""), "jurl": ""})

    # 可用优先、再按总耗时升序
    results.sort(key=lambda x: (not x["usable"], x["total_ms"]))

    for r in results:
        flag = "✅可用" if r["usable"] else "❌不可用"
        jo, jb, jm, ji = r["json"]
        ro, rb, rm, ri = r["jar"]
        print("\n[%s] %-18s  json %dms / jar %dms" % (flag, r["name"], jm, rm))
        print("    json: %s | %dB | %s" % ("OK" if jo else "FAIL", jb, ji))
        print("    jar : %s | %dB | %s" % ("OK" if ro else "FAIL", rb, ri))
        print("    URL : %s" % r["jurl"])

    good = [r for r in results if r["usable"]]
    print("\n" + "=" * 78)
    if good:
        print("推荐顺序（本机实测，越快越前）：")
        for i, r in enumerate(good, 1):
            print("  %d. %s  (%dms)  %s" % (i, r["name"], r["total_ms"], r["jurl"]))
    else:
        print("⚠️ 本机没有镜像同时通过 json + jar 校验。")
        print("   请在你的实际网络环境重跑：python check_mirrors.py")
    print("=" * 78)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
