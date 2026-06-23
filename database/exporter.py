# -*- coding: utf-8 -*-
"""数据导出: SQLite -> data.xlsx"""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

import pandas as pd

from scraper import config

logger = logging.getLogger(__name__)


def export_to_excel(db_path: Optional[str] = None,
                     out_path: Optional[str] = None) -> str:
    """把数据库 v_comment_full 视图导出为 data.xlsx"""
    path = db_path or config.DB_PATH
    out = out_path or config.XLSX_PATH
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        df = pd.read_sql_query("SELECT * FROM v_comment_full", conn)
        anime_df = pd.read_sql_query("SELECT * FROM anime", conn)
    finally:
        conn.close()

    if df.empty:
        logger.warning("数据库为空, 不导出")
        return ""

    column_rename = {
        "comment_id":      "评论ID",
        "user_id":         "用户ID",
        "user_name":       "用户名",
        "category":        "类型",
        "anime_title":     "动漫标题",
        "year":            "上映年份",
        "anime_score":     "原评分(1-10)",
        "mal_id":          "动漫ID",
        "merchant_name":   "商家标识",
        "rating":          "评分(1-5)",
        "like_count":      "Reactions数",
        "comment_time":    "评论时间",
        "comment_content": "评论内容",
    }
    df = df.rename(columns=column_rename)
    df = df[list(column_rename.values())]

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="全部评论", index=False)

        if not anime_df.empty:
            anime_display = anime_df[["mal_id", "title", "type", "episodes", "score", "scored_by", "year"]]
            anime_display.columns = ["动漫ID", "标题", "类型", "集数", "评分(1-10)", "评分人数", "年份"]
            anime_display = anime_display.sort_values("评分人数", ascending=False)
            anime_display.to_excel(writer, sheet_name="动漫列表", index=False)

        per_anime = (
            df.groupby(["动漫ID", "动漫标题", "类型"])
              .agg(评论数=("评论ID", "count"),
                   平均评分=("评分(1-5)", "mean"),
                   总Reactions=("Reactions数", "sum"))
              .round(2)
              .reset_index()
              .sort_values("评论数", ascending=False)
        )
        per_anime.to_excel(writer, sheet_name="按动漫汇总", index=False)

    logger.info("已导出 %d 条数据到 %s", len(df), out)
    return out
