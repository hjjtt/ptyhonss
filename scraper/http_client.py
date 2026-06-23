# -*- coding: utf-8 -*-
"""Jikan HTTP 客户端封装, 带重试 / 限速 / 随机 UA"""
from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests

from . import config

logger = logging.getLogger(__name__)

# 多套 UA, 每次请求随机使用, 降低被识别概率
_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Mi 11) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
]


class HttpClient:
    """Jikan API 客户端, 负责限速 / 重试 / 随机 UA"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.DEFAULT_HEADERS)
        self.last_request_at = 0.0

    # ---------- 内部工具 ----------
    def _throttle(self):
        """两次请求之间至少间隔 REQUEST_INTERVAL 秒"""
        now = time.time()
        wait = config.REQUEST_INTERVAL - (now - self.last_request_at)
        if wait > 0:
            time.sleep(wait)
        self.last_request_at = time.time()

    def _rotate_ua(self):
        self.session.headers["User-Agent"] = random.choice(_USER_AGENTS)

    # ---------- 对外接口 ----------
    def get(self, url: str, params: Optional[dict] = None) -> Optional[requests.Response]:
        """带重试的 GET, 失败返回 None"""
        max_retries = config.MAX_RETRIES
        timeout = config.REQUEST_TIMEOUT
        for attempt in range(1, max_retries + 1):
            try:
                self._throttle()
                self._rotate_ua()
                resp = self.session.get(url, params=params or {}, timeout=timeout)
                if resp.status_code == 200:
                    return resp
                # Jikan 429 = rate limit, 等更久再重试
                if resp.status_code == 429:
                    logger.warning(
                        "[HTTP] %s 状态码 429 (rate limit), 第 %d 次重试",
                        url, attempt,
                    )
                    time.sleep(2 ** attempt)
                    continue
                logger.warning(
                    "[HTTP] %s 状态码 %s, 第 %d 次重试",
                    url, resp.status_code, attempt,
                )
            except requests.RequestException as exc:
                logger.warning("[HTTP] 请求异常 %s, 第 %d 次重试: %s", url, attempt, exc)
            time.sleep(2 ** attempt * 0.5)
        return None
