# -*- coding: utf-8 -*-
"""Jikan (MyAnimeList) 评论爬虫 (真实数据, 无需鉴权)

抓取动漫 + 用户长评, 字段完整, 10000+ 真实数据。
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

from . import config
from .http_client import HttpClient

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 过滤规则 (课程要求: 单动漫 <= 1000 条 + 近两年)
# ----------------------------------------------------------------------
def _cutoff_date() -> Optional[datetime]:
    """返回近两年的截止日期; 关闭过滤时返回 None

    返回 naive datetime (本地时间), 与 _iso_to_str 走同一基准。
    """
    if not getattr(config, "ENABLE_FILTER", False):
        return None
    years = getattr(config, "RECENT_YEARS", 2)
    return datetime.now() - timedelta(days=365 * years)


def _is_recent(date_str: str, cutoff: Optional[datetime]) -> bool:
    """判断评论时间是否在近两年内; cutoff 为 None 时不限"""
    if cutoff is None:
        return True
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return False
    # 统一去掉时区信息, 按本地时间比较 (cutoff 是 naive 的)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt >= cutoff


def _review_limit() -> int:
    """返回单动漫评论数上限 (同时受 API 翻页上限和课程规则约束)"""
    api_cap = getattr(config, "MAX_REVIEWS_PER_ANIME", 100)
    if getattr(config, "ENABLE_FILTER", False):
        rule_cap = getattr(config, "MAX_REVIEWS_PER_ANIME_LIMIT", 1000)
        return min(api_cap, rule_cap)
    return api_cap


# ----------------------------------------------------------------------
# 数据模型
# ----------------------------------------------------------------------
@dataclass
class Comment:
    comment_id: str
    user_id: str
    user_name: str
    merchant_name: str
    rating: int
    comment_time: str
    comment_content: str
    like_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnimeInfo:
    mal_id: int
    title: str
    title_english: str
    title_japanese: str
    type: str
    episodes: int
    score: float
    scored_by: int
    rank: int
    popularity: int
    year: Optional[int]
    image_url: str

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------
def _score_to_rating(score: int) -> int:
    """MAL 1-10 分 -> 1-5 评分"""
    for threshold, rating in config.RATING_RANGES:
        if score >= threshold:
            return rating
    return 1


def _iso_to_str(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso


# ----------------------------------------------------------------------
# 动漫信息
# ----------------------------------------------------------------------
def fetch_anime_list(filter_kind: str = "bypopularity", anime_type: str = "tv",
                      limit: int = 50) -> List[AnimeInfo]:
    """获取动漫列表 (分页, 拿到 limit 条)"""
    client = HttpClient()
    collected: List[AnimeInfo] = []
    page = 1
    per_page = 25

    while len(collected) < limit and page <= 8:
        params = {
            "page": page,
            "limit": per_page,
            "type": anime_type,
            "filter": filter_kind,
            "sfw": "true",
        }
        resp = client.get(f"{config.JIKAN_API}/top/anime", params=params)
        if resp is None:
            break
        try:
            data = resp.json()
        except json.JSONDecodeError:
            break
        items = data.get("data", [])
        if not items:
            break

        for a in items:
            try:
                info = AnimeInfo(
                    mal_id=int(a["mal_id"]),
                    title=a.get("title", "").strip(),
                    title_english=(a.get("title_english") or "").strip(),
                    title_japanese=(a.get("title_japanese") or "").strip(),
                    type=a.get("type", ""),
                    episodes=int(a.get("episodes") or 0),
                    score=float(a.get("score") or 0),
                    scored_by=int(a.get("scored_by") or 0),
                    rank=int(a.get("rank") or 0),
                    popularity=int(a.get("popularity") or 0),
                    year=(a.get("year") if a.get("year") is not None else None),
                    image_url=(a.get("images", {}).get("jpg", {}) or {}).get("image_url", ""),
                )
                collected.append(info)
            except (KeyError, ValueError, TypeError) as e:
                logger.debug("跳过无效 anime: %s", e)
            if len(collected) >= limit:
                break
        if len(items) < per_page:
            break
        page += 1

    return collected[:limit]


# ----------------------------------------------------------------------
# 评论抓取
# ----------------------------------------------------------------------
def _parse_review(raw: dict, anime: AnimeInfo) -> Optional[Comment]:
    """单条评论解析"""
    rid = raw.get("mal_id") or raw.get("id")
    user = raw.get("user") or {}
    text = (raw.get("review") or "").strip()
    if not rid or not text:
        return None
    username = user.get("username", "anonymous")
    user_url = user.get("url", "")
    score = int(raw.get("score") or 0)
    date_str = raw.get("date", "")
    reactions = raw.get("reactions") or {}
    overall = int(reactions.get("overall", 0))

    return Comment(
        comment_id=str(rid),
        user_id=user_url or username,   # URL 是用户唯一标识
        user_name=username,
        merchant_name=anime.title,
        rating=_score_to_rating(score),
        comment_time=_iso_to_str(date_str),
        comment_content=text[:1500],     # 截断
        like_count=overall,
    )


def _fetch_anime_reviews(anime: AnimeInfo, max_count: int) -> List[Comment]:
    """抓取单个动漫的所有评论 (翻 5 页 × 20)

    受 config.ENABLE_FILTER 控制:
      - 开启: 只保留近两年评论, 且单动漫 <= MAX_REVIEWS_PER_ANIME_LIMIT
      - 关闭: 抓全量历史数据
    """
    client = HttpClient()
    collected: List[Comment] = []
    page = 1
    per_page = 20  # Jikan 单页最大 20
    cutoff = _cutoff_date()
    limit = min(max_count, _review_limit())
    skipped_old = 0  # 因时间过旧被跳过的计数

    while len(collected) < limit and page <= 5:
        params = {"page": page}
        resp = client.get(f"{config.JIKAN_API}/anime/{anime.mal_id}/reviews", params=params)
        if resp is None:
            break
        try:
            data = resp.json()
        except json.JSONDecodeError:
            break
        items = data.get("data", [])
        if not items:
            break

        for r in items:
            if len(collected) >= limit:
                break
            # 近两年过滤
            if not _is_recent(r.get("date", ""), cutoff):
                skipped_old += 1
                continue
            parsed = _parse_review(r, anime)
            if parsed:
                collected.append(parsed)

        if len(items) < per_page:
            break
        page += 1

    if cutoff is not None and skipped_old > 0:
        logger.debug("    %s 跳过 %d 条非近两年评论", anime.title[:20], skipped_old)
    return collected


# ----------------------------------------------------------------------
# 顶层入口
# ----------------------------------------------------------------------
def crawl_all(skip_mal_ids: set = None) -> List[Comment]:
    """抓取所有动漫的评论

    skip_mal_ids: 跳过已抓过的动漫 (避免重复抓)
    """
    skip_mal_ids = skip_mal_ids or set()
    logger.info("=" * 60)
    logger.info("启动 Jikan 爬虫, 抓取动漫长评 (真实数据)")
    if getattr(config, "ENABLE_FILTER", False):
        cutoff = _cutoff_date()
        logger.info(
            "过滤规则已开启: 单动漫 <= %d 条, 仅保留近 %d 年 (截止 %s)",
            config.MAX_REVIEWS_PER_ANIME_LIMIT, config.RECENT_YEARS,
            cutoff.strftime("%Y-%m-%d") if cutoff else "无",
        )
    else:
        logger.info("过滤规则已关闭: 抓取全量历史数据")
    if skip_mal_ids:
        logger.info("跳过 %d 个已抓动漫", len(skip_mal_ids))

    # 1) 收集动漫列表
    seen_ids: set = set(skip_mal_ids)  # 包含已抓的
    all_anime: List[AnimeInfo] = []
    for filter_kind, atype, limit in config.ANIME_QUERIES:
        logger.info("获取动漫: filter=%s, type=%s, limit=%d", filter_kind, atype, limit)
        anime_list = fetch_anime_list(filter_kind, atype, limit)
        added_this = 0
        for a in anime_list:
            if a.mal_id not in seen_ids:
                seen_ids.add(a.mal_id)
                all_anime.append(a)
                added_this += 1
        logger.info("    本批 %d (新增 %d, 跳过 %d), 累计 %d",
                    len(anime_list), added_this, len(anime_list) - added_this,
                    len(all_anime))
        if len(all_anime) >= config.MAX_ANIME:
            break
    all_anime = all_anime[:config.MAX_ANIME]
    logger.info("共 %d 个目标动漫 (含 %d 跳过)", len(all_anime), len(skip_mal_ids))

    if not all_anime:
        logger.info("无新动漫, 跳过抓评论")
        return []

    # 2) 每个动漫拉评论
    all_comments: List[Comment] = []
    for idx, anime in enumerate(all_anime, 1):
        logger.info("(%d/%d) %s (id=%d, score=%.2f)",
                    idx, len(all_anime), anime.title[:30], anime.mal_id, anime.score)
        comments = _fetch_anime_reviews(anime, config.MAX_REVIEWS_PER_ANIME)
        all_comments.extend(comments)
        if idx % 10 == 0 or idx == len(all_anime):
            logger.info("    累计 %d 条评论", len(all_comments))

    logger.info("=" * 60)
    logger.info("全部完成, 共 %d 条真实评论", len(all_comments))
    _dump_raw_json(all_comments, all_anime)
    return all_comments


def _dump_raw_json(comments: Iterable[Comment], anime_list: List[AnimeInfo]) -> None:
    os.makedirs(config.RAW_JSON_DIR, exist_ok=True)
    ts = int(time.time())
    out = {
        "anime": [a.to_dict() for a in anime_list],
        "comments": [c.to_dict() for c in comments],
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    path = os.path.join(config.RAW_JSON_DIR, f"jikan_{ts}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    logger.info("原始数据落盘: %s", path)
