# -*- coding: utf-8 -*-
"""数据库管理器: Jikan 动漫 + 评论"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterable, List, Optional, Sequence

from scraper.crawler import Comment, AnimeInfo
from scraper import config as scraper_config

config = scraper_config
logger = logging.getLogger(__name__)


class DBManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        sql_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(sql_path, "r", encoding="utf-8") as fp:
            schema_sql = fp.read()
        with self._conn() as conn:
            conn.executescript(schema_sql)
        logger.info("数据库初始化完成: %s", self.db_path)

    # ---------- 动漫 ----------
    def upsert_anime(self, anime_list: Sequence[AnimeInfo]) -> int:
        """批量写入/更新动漫元数据, 返回写入条数"""
        rows = [
            (a.mal_id, a.title, a.title_english, a.title_japanese,
             a.type, a.episodes, a.score, a.scored_by, a.rank, a.popularity,
             a.year, a.image_url)
            for a in anime_list
        ]
        if not rows:
            return 0
        with self._conn() as conn:
            cur = conn.executemany(
                "INSERT OR REPLACE INTO anime "
                "(mal_id, title, title_english, title_japanese, type, episodes, "
                " score, scored_by, rank, popularity, year, image_url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        logger.info("动漫元数据写入 %d 条", cur.rowcount)
        return cur.rowcount

    def _anime_id_by_title(self, title: str) -> int:
        """通过标题反查 mal_id"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT mal_id FROM anime WHERE title = ?", (title,)
            ).fetchone()
        return row["mal_id"] if row else 0

    # ---------- 评论 ----------
    def insert_comments(self, comments: Iterable[Comment]) -> int:
        rows = []
        for c in comments:
            mal_id = self._anime_id_by_title(c.merchant_name)
            if not mal_id:
                continue
            rows.append((
                c.comment_id, c.user_id, c.user_name, mal_id,
                c.merchant_name, c.rating, c.like_count,
                c.comment_time, c.comment_content,
            ))
        if not rows:
            return 0
        with self._conn() as conn:
            cur = conn.executemany(
                "INSERT OR IGNORE INTO comment "
                "(comment_id, user_id, user_name, mal_id, merchant_name, "
                " rating, like_count, comment_time, comment_content) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        logger.info("尝试插入 %d 条评论, 受影响 %d 条", len(rows), cur.rowcount)
        return cur.rowcount

    # ---------- 统计 ----------
    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM comment").fetchone()["c"]
            anime = conn.execute("SELECT COUNT(*) AS c FROM anime").fetchone()["c"]
            users = conn.execute("SELECT COUNT(DISTINCT user_id) AS c FROM comment").fetchone()["c"]
            avg_rating = conn.execute("SELECT AVG(rating) AS a FROM comment").fetchone()["a"]
        return {
            "total_comments": total,
            "total_anime": anime,
            "unique_users": users,
            "avg_rating": round(avg_rating, 3) if avg_rating else 0,
        }
