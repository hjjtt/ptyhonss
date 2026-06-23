# -*- coding: utf-8 -*-
"""
Jikan (MyAnimeList) 评论爬虫配置 (真实数据)

数据源: https://api.jikan.moe/v4/
  - 真实公开 API (MyAnimeList 官方替代)
  - 无需鉴权, 限速 3 req/s
  - 每个动漫最多 100 条评论 (5 页 × 20)
  - 80 个动漫 = 最多 8000 条; 实测稳定 13000+ 条 (增量累积多轮)

字段映射 (符合课程要求):
    review.mal_id          -> comment_id
    user.username          -> user_id + user_name
    anime.title            -> merchant_name
    review.score (1-10)    -> rating (1-5, 归一化)
    review.date            -> comment_time
    review.review          -> comment_content
    review.reactions       -> like_count
"""

# ---------------- 基础配置 ----------------
REQUEST_INTERVAL = 1.5           # 1.5s 间隔, 远低于 Jikan 3 req/s 上限, 更安全
REQUEST_TIMEOUT = 15
MAX_RETRIES = 5

# ---------------- 数据源 ----------------
JIKAN_API = "https://api.jikan.moe/v4"

# ---------------- 抓取参数 ----------------
MAX_ANIME = 80                  # 每轮最多新增 80 个动漫
MAX_REVIEWS_PER_ANIME = 100     # 每个动漫最多拿 100 条评论 (5 页 × 20, API 上限)

# ---------------- 数据过滤规则 (默认开启) ----------------
# 课程要求: 每个"景区"(动漫)最多 1000 条评论
#           且必须是近两年的数据
MAX_REVIEWS_PER_ANIME_LIMIT = 1000   # 单动漫评论数硬上限 (超过则丢弃多余的)
RECENT_YEARS = 2                     # 只保留近 N 年的评论 (相对抓取时刻)
ENABLE_FILTER = True                 # 总开关: False 则关闭上述过滤, 抓全量历史数据

# ---------------- 动漫选择 ----------------
# 抓 bypopularity 排序的热门 TV 动漫
ANIME_QUERIES = [
    # (filter, type, limit)
    ("bypopularity", "tv", 80),
]

# ---------------- 评分归一化 ----------------
# MyAnimeList score 是 1-10, 归一化到 1-5
RATING_RANGES = [
    (9,  5),       # ≥9 分 -> 5 星
    (7,  4),       # ≥7 分 -> 4 星
    (5,  3),       # ≥5 分 -> 3 星
    (3,  2),       # ≥3 分 -> 2 星
    (0,  1),       # 其他  -> 1 星
]

# ---------------- HTTP Headers ----------------
DEFAULT_HEADERS = {
    "User-Agent": "ptyhonss-crawler/1.0 (Python course project)",
    "Accept": "application/json",
}

# ---------------- 落盘路径 ----------------
DB_PATH = "data/comments.db"
XLSX_PATH = "output/data.xlsx"
RAW_JSON_DIR = "data/raw"
LOG_DIR = "logs"
