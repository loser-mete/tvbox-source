# TVBox 聚合源（自动更新 · 自动剔除失效源）

把多个公开 TVBox 配置源与直播源，每天自动探活、合并去重、剔除失效后，聚合进**一个配置地址**。

> ⚠️ **合规声明**：本项目只做「公开订阅地址的聚合与健康检测」，不含任何破解、账号共享或盗版内容。所有源均来自公开 GitHub 仓库，仅供个人学习研究使用。请在所在地法律允许的范围内使用，勿用于商业用途。第三方源的稳定性与合法性由源作者负责。

---

## 一、源地址（在 TVBox 里填这个）

把下面任一地址填进 TVBox / 影视仓的「配置地址」：

### 主地址（GitHub 原站）
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
| `config.json` | **主配置**，TVBox 填这个地址 |
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
