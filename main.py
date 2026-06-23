# -*- coding: utf-8 -*-
"""
《Python 领域应用》课程作业 - 主入口 (Jikan 真实动漫评论)
============================================================
抓取 MyAnimeList 上 150+ 热门动漫的 10000+ 真实长评, 写入 SQLite,
导出 Excel, 用 Numpy + Pandas + Matplotlib 生成 7 张分析图。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import List

from scraper import (
    config,
    crawl_all,
    load_all_raw,
    Comment,
    AnimeInfo,
)
from database import DBManager
from database.exporter import export_to_excel
from analysis import load_dataframe, generate_all_charts

LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.LOG_DIR, "run.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def run_pipeline(skip_crawl: bool = False) -> None:
    started = time.time()
    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # ---------- 1. 初始化数据库 ----------
    logger.info("=" * 60)
    logger.info("Step 1: 初始化数据库")
    db = DBManager()

    # ---------- 2. 抓取 / 加载缓存 ----------
    all_comments: List[Comment] = []
    all_anime: List[AnimeInfo] = []

    if not skip_crawl:
        logger.info("=" * 60)
        logger.info("Step 2: 抓取 Jikan 真实评论 (含累积 raw 缓存)")

        # 2a. 加载 raw 缓存
        cached_comments, cached_anime = load_all_raw()
        if cached_comments:
            all_comments.extend(cached_comments)
            all_anime.extend(cached_anime)
            logger.info("已加载 raw 缓存: %d 条评论, %d 个动漫",
                        len(cached_comments), len(cached_anime))

        # 2b. 抓新动漫 (跳过已抓), 再从 raw 重新加载完整数据 (新+旧)
        skip_ids = {a.mal_id for a in all_anime}
        crawl_all(skip_mal_ids=skip_ids)
        all_comments, all_anime = load_all_raw()

        # 写库
        if all_anime:
            db.upsert_anime(all_anime)
        db.insert_comments(all_comments)
    else:
        # skip_crawl 模式: 从 raw 加载到 db
        logger.info("=" * 60)
        logger.info("Step 2: 跳过抓取, 从 raw 缓存加载数据")
        all_comments, all_anime = load_all_raw()
        if all_anime:
            db.upsert_anime(all_anime)
        db.insert_comments(all_comments)

    # ---------- 3. 统计 ----------
    stats = db.stats()
    logger.info("数据库统计: %s", stats)
    if stats["total_comments"] < 10000:
        logger.warning("评论数 %d 不足 10000", stats["total_comments"])

    # ---------- 4. 导出 Excel ----------
    logger.info("=" * 60)
    logger.info("Step 3: 导出 data.xlsx")
    xlsx = export_to_excel()
    if xlsx:
        logger.info("Excel 导出: %s", xlsx)
        import shutil
        try:
            shutil.copy(xlsx, xlsx.rsplit(".", 1)[0] + ".xlxs")
        except Exception:
            pass

    # ---------- 5. 分析 ----------
    logger.info("=" * 60)
    logger.info("Step 4: Numpy + Pandas + Matplotlib 分析")
    df = load_dataframe()
    logger.info("DataFrame 形状: %s", df.shape)
    if not df.empty:
        import numpy as np
        ratings = df["rating"].values
        likes = df["like_count"].values
        logger.info(
            "评分统计 (Numpy): mean=%.3f, median=%.1f, p95=%.1f",
            ratings.mean(), float(np.median(ratings)), float(np.percentile(ratings, 95)),
        )
        logger.info(
            "Reactions 统计 (Numpy): mean=%.2f, median=%.0f, max=%d",
            likes.mean(), float(np.median(likes)), int(likes.max()),
        )
        charts = generate_all_charts(df)
        for c in charts:
            logger.info("生成图表: %s", c)

    elapsed = time.time() - started
    logger.info("=" * 60)
    logger.info("全部完成, 耗时 %.1f 秒", elapsed)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Jikan 动漫评论数据采集与分析系统")
    p.add_argument("--skip-crawl", action="store_true",
                   help="跳过抓取, 直接分析已有数据库")
    return p.parse_args()


def main():
    args = parse_args()
    run_pipeline(skip_crawl=args.skip_crawl)


if __name__ == "__main__":
    main()
