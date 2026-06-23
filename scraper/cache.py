# -*- coding: utf-8 -*-
"""从已下载的原始 JSON 加载数据, 支持增量累积"""
from __future__ import annotations

import json
import logging
import os
from typing import List

from . import config
from .crawler import Comment, AnimeInfo

logger = logging.getLogger(__name__)


def load_all_raw() -> tuple:
    """从 data/raw/ 加载所有原始 JSON

    Returns:
        (all_comments, all_anime)  - 评论按 comment_id 去重, 动漫按 mal_id 去重
    """
    raw_dir = config.RAW_JSON_DIR
    if not os.path.isdir(raw_dir):
        return [], []

    all_comments: List[Comment] = []   # 保留顺序
    seen_comment_ids: set = set()
    seen_anime: dict = {}  # mal_id -> AnimeInfo (取最新)

    for fname in sorted(os.listdir(raw_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(raw_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("跳过无效文件 %s: %s", fname, e)
            continue

        # 动漫元数据
        for a in data.get("anime", []):
            try:
                info = AnimeInfo(
                    mal_id=int(a["mal_id"]),
                    title=a.get("title", ""),
                    title_english=a.get("title_english", ""),
                    title_japanese=a.get("title_japanese", ""),
                    type=a.get("type", ""),
                    episodes=int(a.get("episodes") or 0),
                    score=float(a.get("score") or 0),
                    scored_by=int(a.get("scored_by") or 0),
                    rank=int(a.get("rank") or 0),
                    popularity=int(a.get("popularity") or 0),
                    year=a.get("year"),
                    image_url=a.get("image_url", ""),
                )
                seen_anime[info.mal_id] = info
            except (KeyError, ValueError, TypeError):
                continue

        # 评论 (按 comment_id 去重)
        for c in data.get("comments", []):
            try:
                cid = c["comment_id"]
                if cid in seen_comment_ids:
                    continue
                seen_comment_ids.add(cid)
                all_comments.append(Comment(
                    comment_id=cid,
                    user_id=c["user_id"],
                    user_name=c["user_name"],
                    merchant_name=c["merchant_name"],
                    rating=c.get("rating", 1),
                    comment_time=c["comment_time"],
                    comment_content=c["comment_content"],
                    like_count=c.get("like_count", 0),
                ))
            except KeyError:
                continue

    logger.info(
        "从 raw 加载 %d 条评论 (去重后), %d 个动漫",
        len(all_comments), len(seen_anime),
    )
    return all_comments, list(seen_anime.values())


def _load_anime_from_raw() -> List[AnimeInfo]:
    """只加载 anime 元数据 (从 raw)"""
    _, anime = load_all_raw()
    return anime
