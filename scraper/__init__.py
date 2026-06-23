# -*- coding: utf-8 -*-
"""scraper 包入口"""
from .crawler import Comment, AnimeInfo, crawl_all, fetch_anime_list  # noqa: F401
from .cache import load_all_raw  # noqa: F401
