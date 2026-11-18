# TVBox 聚合源（自动更新 · 自动剔除失效源）

把多个公开 TVBox 配置源与直播源，每天自动探活、合并去重、剔除失效后，聚合进**一个配置地址**。

> ⚠️ **合规声明**：本项目只做「公开订阅地址的聚合与健康检测」，不含任何破解、账号共享或盗版内容。所有源均来自公开 GitHub 仓库，仅供个人学习研究使用。请在所在地法律允许的范围内使用，勿用于商业用途。第三方源的稳定性与合法性由源作者负责。

---

## 一、源地址（先看你用哪个客户端）

> ⚠️ **影视仓 / FongMi 用户请直接用【影视仓专用地址】**，不要用下面的 config.json！
> 影视仓的「配置地址」要的是**配置地址清单** `{"urls":[{"name","url"}]}`（每条指向一个完整的带 spider 的原始配置），
> 不是把站点拆解重组的单仓 JSON。填错格式就会提示「接口无效」。

### ⭐ 我的精选（推荐 · 站点归类版）
想要**站点少而精、按类型归好类**的话，用这个——25 个实测好站按内容分成标签页，含直播：
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
```
国内镜像（主地址打不开时试）：
```
https://ghfast.top/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/myfav.json
https://cdn.jsdelivr.net/gh/loser-mete/tvbox-source@main/myfav.json
```
结构一览：

| 分组（影视仓标签页） | 内容 |
|------|------|
| 🔥影视精选 | 12 个实测可用的综合影视直链站（魔都/天涯/非凡/360/极速/闪电/无尽…） |
| 🌈动漫专区 | 5 个内置动漫分类的直链站（进站后点「动漫/国产动漫/日韩动漫」标签） |
| 📺短剧专区 | 淘片 + 4 个内置短剧分类的直链站 |
| 🧒少儿儿童 | 内置「儿童儿歌」分类的直链站 |
| ⚡备用线路 | 7 个多源交叉收录的老牌站（电影天堂/量子/暴风/爱坤…） |
| 📡直播 | APTV / 天幕 / 大嘴巴，走国内镜像，带 EPG |

> 所有点播站点均为 **HTTP 直链**（苹果CMS标准接口），影视仓原生支持、**零 spider 依赖**，不会「接口无效」。
> 动漫/少儿/短剧用站内的**分类标签**查看——这些综合站内置的分类比单一专项源更全更稳。早期版本曾放动漫/少儿/短剧专项源，但它们是 `csp_`/`drpy.js` 脚本型、依赖各自 spider.jar，影视仓合并订阅时会失效，现已移除。

### ✅ 影视仓 / FongMi 完整源清单（站点多、求全用这个）
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/fongmi.json
```
国内镜像（主地址打不开时试）：
```
https://ghfast.top/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/fongmi.json
https://cdn.jsdelivr.net/gh/loser-mete/tvbox-source@main/fongmi.json
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
https://ghfast.top/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json
https://gh-proxy.com/https://raw.githubusercontent.com/loser-mete/tvbox-source/main/config.json
https://cdn.jsdelivr.net/gh/loser-mete/tvbox-source@main/config.json
```

> 镜像地址会随网络环境变化而失效。**建议把上面几个都试一遍，哪个能用用哪个**。也可以关注本仓库的 Issues/更新。

### 直播专用地址（可选，部分客户端单独配置直播源时用）
```
https://raw.githubusercontent.com/loser-mete/tvbox-source/main/all.m3u
```

---

## 二、它是怎么工作的

1. **候选清单**：`sources.json` 里维护了一批经过验证的公开配置源和直播源。
2. **每天定时探活**：GitHub Actions 每天北京时间 08:00 自动运行 `update.py`（也可手动触发）。
3. **健康判定**：并发访问每个源——能打开且结构合法才保留；连续失败 3 天才永久剔除，避免网络抖动误杀。
4. **聚合去重**：把有效源的站点按 `api` 去重合并进 `config.json`；直播频道合并进 `all.m3u` / `all.txt`。
5. **容错设计**：支持带注释的 JSONC、加密源自动识别、多仓订阅递归展开、网络异常日保留上次成果。
6. **全程留痕**：`health.json` 记录每个源的死活与耗时，`history/` 保留最近 30 天快照。

### 当前状态
详见 [health.json](health.json)。摘要会显示有效/失效源数量、合并站点数、直播频道数。

---

## 三、文件说明

| 文件 | 作用 |
|------|------|
| `fongmi.json` | **影视仓专用**：配置地址清单（urls 数组），影视仓填这个 |
| `config.json` | **TVBox 原版专用**：单仓聚合配置，TVBox 填这个 |
| `fongmi_seeds.json` | 影视仓种子清单来源（实测有效的优质源） |
| `all.m3u` | 聚合后的直播源（M3U 格式） |
| `all.txt` | 聚合后的直播源（名称,URL 格式） |
| `health.json` | 健康报告：每个源死活、剔除名单、观察名单 |
| `sources.json` | 候选源清单（想增删源改这里） |
| `state.json` | 连续失败计数（脚本自动维护，勿手改） |
| `update.py` | 更新脚本（零第三方依赖） |
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
