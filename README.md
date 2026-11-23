# TVBox 聚合源（自动更新 · 自动剔除失效源）

把多个公开 TVBox 配置源与直播源，每天自动探活、合并去重、剔除失效后，聚合进**一个配置地址**。

> ⚠️ **合规声明**：本项目只做「公开订阅地址的聚合与健康检测」，不含任何破解、账号共享或盗版内容。所有源均来自公开 GitHub 仓库，仅供个人学习研究使用。请在所在地法律允许的范围内使用，勿用于商业用途。第三方源的稳定性与合法性由源作者负责。

---

## 一、源地址（先看你用哪个客户端）

> ⚠️ **两个关键坑（2026-11-18 全部定位并修复）**：
> 1. **接口无效**：配置顶层若含 `urls` 字段（哪怕空对象 `{}`），影视仓会当「多仓清单」解析导致「接口无效」。单线路普通源**顶层绝不能有 `urls`**。
> 2. **jar 加载失败**：`csp_` 类站点（含**苹果APP** `csp_AppDrama`）天生依赖 spider.jar，无法做成 HTTP 直链。之前把 213 个 csp 站点塞进 `config.json` 却**没带 spider 字段** → 影视仓报「jar 加载失败」。
>
> 现在的 `myfav.json` **完全复刻你能打开的 `xiaosa` 格式**：顶层 `spider: "./spider.jar;md5;..."` + 仓库根目录内置 spider.jar（md5 实测匹配）+ 无 `urls`。

### ⭐ 我的精选（推荐 · 单线路 · 含苹果APP）
**自带 jar 的完整单仓配置**：51 个 csp 精选站（**19 个苹果/APP 站**含 4 个 AppDrama 苹果站 + 影视/短剧/动漫/儿童）+ 13 个直链兜底站 + 直播，按内容归类。格式与你能打开的 `xiaosa` 一致，影视仓可直接加载：
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
```
### 🇨🇳 国内代理地址（移动宽带优先用这组 · 2026-11-23 实测）

判据：`myfav.json` 能解析 **且** 同目录 `spider.jar` 能完整下载（1700116 字节、md5=`decb609b…a252`）。只满足前者会导致「配置能打开但苹果APP等 csp 站点全空」。

**首选（本机实测最快、jar 完整，从上往下依次试）：**
```
https://gh-proxy.com/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
https://gh-proxy.org/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
https://cdn.gh-proxy.com/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
https://ghfast.top/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
```

> ⚠️ **移动宽带请自己复测一次**：不同运营商/地区对镜像的解析不一样。仓库里放了零依赖测速脚本，在你的网络里跑一下，它会按真实速度排出能用的一串：
> ```bash
> python check_mirrors.py
> ```
> 判据是真实读取字节 + 校验 jar 的 md5，不是只看 HTTP 200（假 200/0B 是常见坑）。

> ⚠️ **已排除的镜像**：`ghproxy.net` 的 jar 虽能下完整但要 48 秒（客户端基本会超时）；`jsdelivr` 系列（`cdn.jsdelivr.net` 等）jar 一律 **403**；`down.nigx.cn` 返回网页；`gh.xiu.org` / `gh.llkk.cc` / `github.moeyy.xyz` 当前 502。GitHub 原站在部分国内线路（含本机）直接断连。
结构一览：

| 分组（影视仓标签页） | 内容 |
|------|------|
| 🍎苹果APP | 19 个 APP 采集站，其中「天堂/橘汁/华谊/苹果」为 AppDrama 苹果站（需 jar） |
| 🔥影视精选 | 15 个 csp 影视站（看剧/懂片/星辰/飞娱/1905 等）+ 8 个直链兜底 |
| 📺短剧专区 | 7猫/河马/围观/好看/星芽/果果 短剧 + 淘片直链 |
| 🌈动漫专区 | 6 个 csp 动漫站（番社/赏月/稀饭/巴士/吉里/花子） |
| 🧒少儿儿童 | 童趣/兔小贝/贝乐虎 |
| ⚡更多内容 | 看球/体育 |
| 📡直播 | APTV / 天幕 / 大嘴巴，走国内镜像，带 EPG |

> **为什么这次能打开**：`spider.jar` 已放在仓库根目录，与 `myfav.json` 同目录，`spider` 字段用相对路径 `./spider.jar` + md5 校验——这正是 `xiaosa/api.json` 能正常加载的同款写法。影视仓会相对配置地址取 jar：用 raw 地址加载就从 raw 取，用 ghfast 镜像加载就走镜像。
> **兜底设计**：13 个 HTTP 直链站零 jar 依赖，即使某天 jar 加载失败，直链站仍可用。
> 已排除所有依赖 `./py/`、`./json/` 外部文件的站点（本仓库无这些文件，会失效）。

### ✅ 影视仓 / FongMi 完整源清单（站点多、求全用这个）
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/fongmi.json
```
国内镜像（主地址打不开时试，按实测速度排序）：
```
https://gh-proxy.com/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/fongmi.json
https://gh-proxy.org/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/fongmi.json
https://ghfast.top/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/fongmi.json
```
这个文件是 **26 条实测可用的完整配置源清单**，每天自动探活剔除失效源。每个源保持原样（含 spider.jar / drpy 脚本），影视仓能正常解析。

### TVBox 原版 / 其他客户端
把下面地址填进「配置地址」：

#### 主地址（GitHub 原站）
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json
```

### 国内镜像地址（如主地址打不开，依次尝试）
```
https://gh-proxy.com/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json
https://gh-proxy.org/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json
https://ghfast.top/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json
```

> 镜像地址会随网络环境变化而失效。**建议把上面几个都试一遍，哪个能用用哪个**。也可以关注本仓库的 Issues/更新。

### 直播专用地址（可选，部分客户端单独配置直播源时用）
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/all.m3u
```

---

## 二、它是怎么工作的

1. **候选清单**：`sources.json` 里维护了一批经过验证的公开配置源和直播源。
2. **知名源发现**（新增）：`discover.py` 从 `discovery_seeds.json` 里的知名影视仓源（xiaosa、饭太硬、安忆、东篱等）出发，**展开其内部结构**，提取可用的直播订阅地址与苹果CMS 直链接口，验证后写入 `discovered.json`。`update.py` 每天自动刷新一次发现池并并入源池。想增加/减少发现来源，改 `discovery_seeds.json` 即可。
3. **每天定时探活**：GitHub Actions 每天北京时间 08:00 自动运行 `update.py`（也可手动触发）。
4. **健康判定**：并发访问每个源——能打开且结构合法才保留；连续失败 3 天才永久剔除，避免网络抖动误杀。
5. **聚合去重**：把有效源的站点按 `api` 去重合并进 `config.json`；直播频道合并进 `all.m3u` / `all.txt`。
6. **容错设计**：支持带注释的 JSONC、加密源自动识别、多仓订阅递归展开、网络异常日保留上次成果；发现池失效不影响手工源。
7. **全程留痕**：`health.json` 记录每个源的死活、耗时与发现池概况，`history/` 保留最近 30 天快照。

> **发现器的边界**：只提取「公开订阅地址」——排除 `proxy://` / 相对路径 / drpy 脚本 / 带 token 的鉴权地址，以及名字含「会员/付费/赞助」的账号共享线路；单个直播源频道数超过 3000 的巨型清单也会跳过，避免 `all.m3u` 膨胀拖慢客户端。`myfav.json` 精选配置不依赖发现池，保持稳定。

### 当前状态
详见 [health.json](health.json)。摘要会显示有效/失效源数量、合并站点数、直播频道数。

---

## 三、文件说明

| 文件 | 作用 |
|------|------|
| `myfav.json` | ⭐**我的精选**：自带 jar 的单线路配置（含苹果APP），影视仓填这个 |
| `spider.jar` | myfav.json 配套的 spider.jar（md5=decb609b673019e18512dc3a96b6a252） |
| `csp_picked.json` | 从 xiaosa 精选的 csp 站点数据（build_myfav.py 的输入） |
| `csp_extras.json` | xiaosa 的 parses/rules/flags/ads（播放解析 + 去广告） |
| `fongmi.json` | **影视仓专用**：配置地址清单（urls 数组），影视仓填这个 |
| `config.json` | **TVBox 原版专用**：单仓聚合配置，TVBox 填这个（含 csp 站，需配 jar） |
| `fongmi_seeds.json` | 影视仓种子清单来源（实测有效的优质源） |
| `discovery_seeds.json` | ⭐知名源发现种子（xiaosa / 饭太硬等，想加发现来源改这里） |
| `discover.py` | 发现器：展开知名源，提取并验证直播/直链候选地址（零依赖） |
| `discovered.json` | 发现池产出：当日验证通过的直播/直链/完整配置候选，供 update.py 并入 |
| `all.m3u` | 聚合后的直播源（M3U 格式） |
| `all.txt` | 聚合后的直播源（名称,URL 格式） |
| `health.json` | 健康报告：每个源死活、剔除名单、观察名单 |
| `sources.json` | 候选源清单（想增删源改这里） |
| `state.json` | 连续失败计数（脚本自动维护，勿手改） |
| `update.py` | 更新脚本（零第三方依赖） |
| `check_mirrors.py` | 国内镜像测速：实测 json + spider.jar 能否完整加载并排出可用地址（在你自己的网络里跑) |
| `history/` | 最近 30 天历史快照 |

---

## 四、常见问题

**Q：配置地址打不开？**
A：GitHub 原站在国内不稳定，优先试上面的国内镜像。镜像本身也可能失效，多试几个。

**Q：某个源被剔除了，还能恢复吗？**
A：能。源恢复后，下次探活成功会自动清零失败计数并重新纳入。也可以手动编辑 `state.json` 把对应源的 `fail_streak` 改为 0。

**Q：想加自己的源？**
A：编辑 `sources.json`，在 `configs`（完整配置）或 `lives`（直播 m3u/txt）里加一项，提交后会自动触发一次更新。

**Q：为什么有些站点搜不到片？**
A：影视源的 `api` 类型多样（内置接口 / JS 脚本），聚合只保证「配置地址有效」，不保证每条站点每次都能搜出结果——这是影视源本身的特性。

**Q：更新频率能改吗？**
A：编辑 `.github/workflows/update.yml` 里的 `cron` 表达式即可。

---

## 五、本地运行

```bash
python update.py
```

需要 Python 3.8+，无需安装任何第三方库。运行后会在当前目录生成/更新上述产物。
