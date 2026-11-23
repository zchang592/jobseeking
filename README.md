# 音乐教职雷达

一个可自托管的中文个人招聘工作台。Python 后台每天北京时间 **08:30** 读取公开招聘栏目，解析公告及岗位附件，保存独立岗位、原始链接和核验记录。Next.js 工作台提供筛选、岗位详情、专业匹配、资格判断、收藏、申请进度、来源管理和每日简报。

首次安装会导入 **35 个真实岗位**及其证据。交付快照最近核验于 2026-11-23，其中有历史职位，也有截止日期未知的职位。目录共 23 个来源，12 个完成了招聘公告或官方岗位目录核验。逐校样本、访问失败和停用原因见 [来源核验记录](docs/SOURCES.md)。首页上的“今日新发现”按首次采集日统计，公告发布日期另存。初次打开时“正在招聘”为零是有效结果。

## GitHub Pages 公开版

公开索引默认显示中学、国际及双语学校岗位，另设高校、小学与其他分类。可按关键词、学校、学段和状态筛选，岗位详情保留学位要求、报名时间、官方公告及附件。构建命令从已核验的公开数据生成网页。登录、个人画像、岗位匹配、收藏和申请进度通过下方的服务端版本使用。

在仓库的 **Settings → Pages** 将 **Source** 设为 **GitHub Actions**。之后推送到 `main` 会发布公开版。工作流设置为每天北京时间 08:30 触发采集和重建，实际启动时间取决于 GitHub 调度，可能延迟。可在 **Actions → Publish music job radar → Run workflow** 手动发布，勾选刷新选项可先采集再发布。遇到采集中断时会继续使用上一份可用快照。

在本机预览静态版：

```bash
python3 scripts/build_pages.py --output .pages-dist
python3 -m http.server 8000 --directory .pages-dist
```

用浏览器打开 http://localhost:8000。重新构建时使用空的输出目录。

## 本地启动

需要 Docker Engine / Docker Desktop（Linux 容器）、Docker Compose v2 和 Python 3。Python 仅用于生成本机随机密码。

```bash
# 在项目根目录执行
python3 scripts/configure.py
docker compose up -d --build
docker compose ps
```

在本机浏览器打开 **http://localhost:3000**。在自己的终端运行 `python3 scripts/configure.py --show-password` 查看工作台密码。初始化命令可以重复执行，会保留已有的 `.env`。也可将 `.env.example` 复制为 `.env` 并自行设置密码，数据库密码建议使用十六进制随机串，工作台密码至少 12 位。`RADAR_PORT` 可更换 Web 端口。

```bash
curl -fsS http://localhost:3000/api/health
docker compose exec -T api python -m radar.cli status
```

登录后可以直接搜索“电子音乐作曲”。打开浙江音乐学院的岗位，能看到“研究生/博士”、专业匹配分、“明确不符合”、原公告和对应 PDF 页码。“监控来源”可以展开查看失败原因，包括源站无法读取附件等情况。

## 在长期运行的服务器部署

1. 把项目复制到自己的 Linux 服务器，安装 Docker 和 Compose，设置 Docker 开机启动。
2. 在项目目录执行 `python3 scripts/configure.py`。配置邮件时编辑同目录的 `.env`。使用 HTTPS 域名时将 `RADAR_SECURE_COOKIE=true`。
3. 执行 `docker compose up -d --build`，用 `docker compose ps` 检查四个服务。Web 默认只监听服务器的 `127.0.0.1:3000`，数据库和 API 只在 Compose 网络中提供服务。
4. 使用已有反向代理将自己的 HTTPS 域名指向 `127.0.0.1:3000`。例如给域名配置指向服务器的 DNS 后，宿主机上的 Caddy 可使用下列配置（替换为自己的域名）。

```caddyfile
radar.example.com {
    reverse_proxy 127.0.0.1:3000
}
```

也可以保留本机 HTTP 设置，通过 `ssh -L 3000:127.0.0.1:3000 用户@服务器` 自用。服务使用 `restart: unless-stopped`，关闭浏览器后采集照常运行。每日任务只安排一次；如果 08:30 时机器停机，当天恢复后会补跑。单机部署保留 **一个 worker**。`pgdata` 卷保存岗位、证据和个人操作，`radar-state` 卷保存 worker 锁及可选私有画像。

- 查看任务：`docker compose exec -T api python -m radar.cli status`，或打开网页的“监控来源”。
- 手动采集：点击“立即更新”，或执行 `docker compose exec -T api python -m radar.cli refresh --wait`。多个请求会复用正在运行的任务。
- 备份数据库：`docker compose exec -T db pg_dump -U radar -d radar -Fc > radar.dump`。备份和 `.env` 含个人状态或凭据，应私密保存。
- 更新代码后执行 `docker compose up -d --build`。`docker compose down` 保留命名卷；切勿使用 `down -v` 来做常规更新。
- 如出网代理要求受信任的自签 CA，可用 `RADAR_CA_FILE=/path/to/public-ca-bundle.pem docker compose -f compose.yaml -f docs/compose.ca.yaml up -d --build`。PEM 包应含标准公共根证书及管理员提供的代理 CA 公共证书；此配置保持 TLS 校验。普通公网部署使用默认 Compose 文件即可。

## 添加学校与栏目

在“监控来源 → 添加来源”填写学校名称和招聘栏目网址，选择省市、学校类型、学段；官网和公众号名称可选。对只有一篇公开公告的网址，选择“监控单篇公开公告”。保存后点击“立即更新”，展开该来源查看公告链接、最近成功时间及错误。暂停或移除来源会保留历史岗位和已收藏记录。

栏目采集器从 HTML 链接发现招聘公告，并在正文、岗位表、专业方向与职责中查找音乐相关工作。每轮每来源默认最多处理 5 篇，`RADAR_NOTICES_PER_SOURCE` 可调整。新公告优先，18 小时内核验过的公告通常跳过，旧公告按核验时间轮转。正文、附件使用校验标识和内容摘要；附件位于正文外的下载列表也会检查。相同学校、批次、年度和明确岗位代码允许跨站归并。无代码的转载，须能唯一对上公告标题、发布日期、学校、岗位以及专业 / 部门；缺少可靠标识时保留独立来源，避免把两次招考误当作一次。

为项目预置学校，可编辑 [data/sources.json](data/sources.json)，沿用同类学校条目的字段。在已有数据库上，重新构建后执行 `docker compose exec -T api python -m radar.cli sync-sources` 添加新栏目。已有记录的启停状态和用户移除的来源会保留。跨域公告或附件只访问经核对并列入该来源 `hosts` 的域名。特殊网站可像香港中文大学（深圳）音乐学院的公开岗位目录一样编写专用解析器。可访问的目录与受限的详情分别作为证据处理。

公众号名称用于登记，公开文章链接支持按单篇来源监控。遇到登录、验证页、robots 禁止或正文不可读时记录原因，供人工核实。本版未接入授权微信搜索或搜索引擎 API。

## 扩展中学与国际学校来源

目前默认关注普通初中、高中、国际和双语学校，普通高校单独分类。公开版首页提供 BOSS 直聘的高中、初中、国际学校音乐教师搜索入口，以及 TES 和部分学校招聘官网。BOSS 的 robots.txt 禁止自动访问搜索页，需自行登录和查看；如申请到 BOSS 明确授权的招聘数据接口，可在获得接口文档及授权后另行开发接入。国际学校有时使用外部招聘系统或只面向特定签证及国籍要求，具体条件需查看招聘方原文。

福建省人社厅招聘方案和中国人民大学附属中学招聘栏目已加入监控。栏目成功访问不等于当前有音乐职位，结果将随公告更新；未检测到岗位时保留“待核实”并展示失败原因。默认邮件简报聚焦中学与国际学校，不自动推送高校及小学岗位。

## 匹配、权限与邮件

- **专业匹配和报考资格分别计算。** 作曲、配器、和声、复调、合作钢琴等同义或相关方向在岗位名称、职责和专业字段中匹配。广东只影响同等条件时的排序。要求已取得博士学位的岗位，即使专业高度相关，仍显示学历障碍；出现算法、编程要求会单列能力核查。教师资格、职称及业绩没有证据时提示核实。
- 当前采用可解释规则，无需 AI 或搜索密钥。默认画像为“作曲硕士已毕业、博士在读”，以及用户提供的教学和专业实践方向。身份认证覆盖岗位分析、画像、申请进度、来源与操作接口。密码产生的会话存于 HttpOnly Cookie，写操作要求同源前端请求头。修改工作台密码并重启 API 即可令旧会话失效。
- 可用 [data/profile.json](data/profile.json) 的结构准备一份私有 `profile.json`。原生运行时放在 `runtime/profile.json`；Compose 中使用下面的命令写入私有卷并重新加载。`highest_degree` 只填写**已经取得**的学位。版本库中不需要存放本人简历或联系方式。

```bash
docker compose exec -T api python -c "from pathlib import Path; import sys; Path('/var/lib/radar/profile.json').write_bytes(sys.stdin.buffer.read())" < /path/to/private/profile.json
docker compose restart api worker
```

- 每次查看按北京时间计算“未开始、招聘中、已截止、待核实”。日期精确到日时可报名至该日结束，明确时刻按原文判断；未明确的截止时间显示“截止时间未知”。有“招满即停”条款时，在未超过最终日期前仍需确认是否有名额。
- 在 `.env` 中设置 `SMTP_HOST`、`SMTP_PORT`、`SMTP_MODE`（`ssl` 或 `starttls`）、`SMTP_FROM`、`SMTP_TO`；需要认证时填写 `SMTP_USER`、`SMTP_PASSWORD`。随后执行 `docker compose up -d --force-recreate api worker`。每日任务收尾发送简报，默认排除小学、明确不符、资格信息不足、已忽略、已结束及非招聘中岗位。专业分至少 75 且有报考可能的岗位可进入推荐，并在距截止 7、3、1 天形成提醒。
- 数据库保存每日投递和“岗位 + 截止日 + 提醒天数”的记录，同一次提醒只预留一次。投递结果不明确时会报告异常，保留预留记录以免重复发送。未配置 SMTP 时，网页简报仍可使用。

## 架构与阶段范围

```text
浏览器 → Next.js / TypeScript → 私有 FastAPI → PostgreSQL
                                       ↑
          每日 08:30 / 手动队列 → Python worker
                              ↳ 招聘栏目 → 公告 → HTML / PDF / Excel / Word 岗位
                              ↳ 内容变化核验、证据入库、规则匹配与邮件简报
```

生产使用 PostgreSQL。原生开发默认使用 SQLite，便于在没有容器服务时运行相同的数据模型。应用运行不依赖外部字体、图像服务、搜索或 LLM。

| 阶段 | 当前交付及后续范围 |
|---|---|
| 一：岗位工作台 | 已实现数据库、真实来源核验、中文界面、筛选排序、岗位详情、个人进度及来源管理。 |
| 二：采集管线 | 已实现每日与手动任务、增量核验、来源健康记录、PDF / XLS / XLSX / DOCX 岗位解析和有明确标识的去重。同一公告改版会更新记录；仅在独立补充公告中描述且缺少可关联岗位的延期，需要人工核实。扫描件、旧 DOC 和压缩包保留原件链接并标记。 |
| 三：画像与提醒 | 已实现私有结构化画像、规则匹配、日报和 SMTP。上传 / 替换简历、提取画像和带证据的 LLM 分析留待后续。 |
| 四：扩展发现 | 已支持新增栏目和单篇公开链接。搜索 API、用户配置同义词、授权公众号搜索、粘贴正文和企业微信推送留待后续。 |

## 开发与测试

原生运行推荐 Linux / macOS、Python 3.12、Node 24。初始化后在项目根目录执行：

```bash
python3 scripts/configure.py
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm --prefix web ci
python -m unittest discover -s tests -v
npm --prefix web run build
```

在三个终端中分别启动以下命令，先让 API 健康检查通过，再启动 worker。原生 Web 从 `http://127.0.0.1:8170` 读取数据。

```bash
.venv/bin/uvicorn radar.api:app --host 127.0.0.1 --port 8170
.venv/bin/python -m radar.worker
npm --prefix web run dev -- --hostname 127.0.0.1 --port 3000
```

已经用 Compose 启动时，也可直接运行 `docker compose exec -T api python - < tests/test_radar.py`。测试在唯一的临时数据库中执行，包含真实快照恢复、权限、日期边界、Excel 多岗位拆分、更新/去重、博士与例外条件、定时与手动队列、邮件去重等。网络和 SMTP 测试使用可控传输，不向用户发送测试邮件。来源实测记录独立列于 [docs/SOURCES.md](docs/SOURCES.md)。

主要入口为 [采集器](radar/crawl.py)、[公告与附件解析](radar/extract.py)、[资格和匹配规则](radar/analysis.py)、[调度器](radar/worker.py)、[API](radar/api.py) 和 [网页](web/app)。`scripts/export_verified.py` 可从已采集的数据库导出新的公开快照，它不导出登录信息、收藏或申请状态；导出后应复核来源与岗位证据。
