# Jikan 动漫评论采集与分析系统

> 《Python 领域应用》课程作业 —— **真实数据版**
> 爬虫 + 数据库 + Numpy / Pandas / Matplotlib

抓取 [MyAnimeList](https://myanimelist.net)（通过 [Jikan API](https://jikan.moe)）上热门动漫的 **10000+ 真实长评**，写入 SQLite、导出 Excel，并用 Numpy + Pandas + Matplotlib 生成 7 张分析图。

## 1. 数据来源

Jikan API 是 MyAnimeList 的非官方公开 REST API：

- 数据源：`https://api.jikan.moe/v4`
- **无需鉴权**，无需申请 Token
- 限速 3 req/s（本系统按 1.5s 间隔更保守）
- 每个动漫最多抓 100 条长评（5 页 × 20）

抓取目标：80 个热门 TV 动漫 → 实测稳定拿到 **13000+ 条**真实长评。

## 2. 系统架构

```
ptyhonss/
├── scraper/                 # 爬虫模块
│   ├── config.py           # Jikan API 配置 + 抓取参数
│   ├── http_client.py      # HTTP 客户端 (重试 / 限速 / 随机 UA)
│   ├── crawler.py          # 动漫列表 + 长评抓取
│   └── cache.py            # raw JSON 缓存加载 (增量累积)
├── database/                # 数据库模块
│   ├── schema.sql          # SQLite 表结构 (幂等, 提交作业用)
│   ├── schema_init.sql     # 完整建表 (含清空)
│   ├── db_manager.py       # 数据库 CRUD
│   └── exporter.py         # data.xlsx 导出
├── analysis/
│   └── visualizer.py       # Numpy + Pandas + Matplotlib 7 张图
├── data/
│   ├── comments.db         # SQLite 数据库
│   └── raw/                # 原始 JSON 备份 (按时间戳, 增量累积)
├── output/
│   ├── data.xlsx / .xlxs   # 作业要求的数据文件
│   └── charts/*.png        # 7 张分析图
├── logs/run.log            # 运行日志
├── main.py                 # 入口
└── requirements.txt
```

## 3. 核心功能

| 步骤 | 内容 | 实现位置 |
| ---- | ---- | -------- |
| 1 | Jikan 动漫列表 + 长评抓取 | `scraper/crawler.py` |
| 2 | 限速 + 重试 + 随机 UA | `scraper/http_client.py` |
| 3 | 原始 JSON 落盘 (增量累积, 按时间戳) | `scraper/crawler.py::_dump_raw_json` |
| 4 | 从 raw 缓存去重加载 | `scraper/cache.py::load_all_raw` |
| 5 | SQLite 入库 (动漫 + 评论) | `database/db_manager.py` |
| 6 | 导出 data.xlsx (3 个 sheet) | `database/exporter.py` |
| 7 | Numpy + Pandas + Matplotlib 7 张图 | `analysis/visualizer.py` |

## 4. 字段映射 (符合课程要求)

| 作业要求字段 | 数据库字段 | 数据来源 |
| ------------ | ---------- | -------- |
| 评论 id      | comment_id | MAL review id |
| 用户 id 或名称 | user_id, user_name | MAL 用户主页 URL + 用户名 |
| 商家名称     | merchant_name | 动漫标题 (动漫类比"商家") |
| 评分         | rating | MAL 1-10 分归一化到 1-5 |
| 评论时间     | comment_time | review.date |
| 评论内容     | comment_content | review.review 正文 |
| (附加) 点赞 | like_count | review.reactions.overall |

## 5. 安装与运行

```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 跑起来 (默认: 抓取 + 入库 + 导出 + 分析)
python main.py

# 3) 跳过抓取, 直接用 raw 缓存 + 已有数据库分析 (推荐复跑)
python main.py --skip-crawl
```

抓取是增量累积的：每次运行只抓未抓过的新动漫，原始 JSON 永久保留在 `data/raw/`，即使后续 Jikan 接口变动也能从缓存还原全部数据。

## 6. 数据库表设计 (ER)

```
anime (动漫表, 类比"商家")       comment (评论表)
+-----------------+              +----------------------+
| mal_id (PK)     |◄─────────────| mal_id (FK)          |
| title           |              | comment_id (PK)      |
| title_english   |              | user_id              |
| title_japanese  |              | user_name            |
| type            |              | merchant_name        |
| episodes        |              | rating (1-5)         |
| score (1-10)    |              | like_count           |
| scored_by       |              | comment_time         |
| rank / popularity|             | comment_content      |
| year / image_url|              +----------------------+
+-----------------+
                  视图 v_comment_full = comment LEFT JOIN anime
```

## 7. 7 张分析图

1. **各动漫评论数量 Top 20**（横向柱状图 + viridis 渐变）
2. **单动漫每日评论趋势**（折线图 + 7 日滑动平均，Numpy 卷积）
3. **评分分布**（彩色直方图 + 百分比标注）
4. **评论数量月度趋势**（面积图 + 峰值箭头标注）
5. **动漫类型对比**（双 Y 轴：评论数 + 平均评分）
6. **评分 vs 字数 + Reactions**（箱线图 + 散点图，Numpy 算 Pearson 系数）
7. **评论高频词 Top 20**（中文 2-gram + 英文词，横向柱状图）

## 8. 数据过滤规则（默认开启）

课程要求：每个"景区"（动漫）最多 1000 条评论，且必须是近两年的数据。本系统在抓取层默认强制执行该规则：

| 配置项 (`scraper/config.py`) | 默认值 | 说明 |
| --- | --- | --- |
| `ENABLE_FILTER` | `True` | 总开关。设 `False` 则抓全量历史数据 |
| `MAX_REVIEWS_PER_ANIME_LIMIT` | `1000` | 单动漫评论数硬上限（与 API 翻页上限取较小值） |
| `RECENT_YEARS` | `2` | 只保留相对当前时刻近 N 年的评论 |

实现位置：`scraper/crawler.py::_fetch_anime_reviews`——每条评论的 `date` 字段会被检查，早于截止日期的直接丢弃；同时 `MAX_REVIEWS_PER_ANIME` 与该上限取较小值作为单动漫最终抓取量。

关闭过滤抓全量历史（调试/对比用）：

```python
# scraper/config.py
ENABLE_FILTER = False
```

## 9. 抗限速设计

- **指数退避**重试（`2^attempt × 0.5` 秒）
- **固定间隔**节流（默认 1.5s，远低于 Jikan 3 req/s 上限）
- **随机 User-Agent**轮换，降低被识别概率
- 原始 JSON 落盘后按 `comment_id` 去重，避免重复入库

## 10. 关于"商家"概念

本系统的"商家"对应**动漫作品**：每部动漫类比一个"商家"，动漫下的用户长评类比"用户评价"。`merchant_name` 字段存储动漫标题，`anime` 表即"商家档案表"（含评分、集数、上映年份等元数据）。

## 11. 满足课程要求清单

| 要求 | 实现 |
| ---- | ---- |
| ① 真实爬取 ≥ 10000 条 | ✓ 实测 13033 条 (Jikan 真实数据) |
| ② 存入数据库 (字段齐全) | ✓ SQLite, 表 anime + comment + 视图 v_comment_full |
| ③ Numpy + Pandas + Matplotlib ≥ 2 张图 | ✓ 7 张 |
| ④ 提交 data.xlxs | ✓ output/data.xlxs |
| ⑤ 提交 SQL 表结构 | ✓ database/schema.sql |
| ⑥ 提交源码 | ✓ 全部 .py 文件 |
| ⑦ 字段: 评论id, 用户id, 商家, 评分, 时间, 内容 | ✓ 全部包含 |
| ⑧ 景区 ≤ 1000 条 + 近两年 | ✓ `ENABLE_FILTER=True`, 抓取层默认强制 (见第 8 节) |
