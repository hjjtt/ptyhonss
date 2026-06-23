# -*- coding: utf-8 -*-
"""Numpy + Pandas + Matplotlib 数据分析与可视化 (Jikan 动漫评论)"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager, rcParams

from scraper import config

logger = logging.getLogger(__name__)

# 中文字体兼容
_cn_fonts = [
    "Microsoft YaHei", "SimHei", "PingFang SC", "Hiragino Sans GB",
    "Source Han Sans CN", "Noto Sans CJK SC", "WenQuanYi Zen Hei",
    "Arial Unicode MS",
]
_available = {f.name for f in font_manager.fontManager.ttflist}
for _name in _cn_fonts:
    if _name in _available:
        rcParams["font.sans-serif"] = [_name]
        break
rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.dpi"] = 110


def load_dataframe(db_path: Optional[str] = None) -> pd.DataFrame:
    """从 SQLite 读出全部评论, 转为 DataFrame"""
    import sqlite3
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path)
    try:
        df = pd.read_sql_query("SELECT * FROM v_comment_full", conn)
    finally:
        conn.close()

    if df.empty:
        return df

    df["comment_time"] = pd.to_datetime(df["comment_time"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(1).astype(int)
    df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce").fillna(0).astype(int)
    df = df.dropna(subset=["comment_time", "rating"])
    df["date"] = df["comment_time"].dt.date
    df["year_month"] = df["comment_time"].dt.to_period("M").astype(str)
    df["content_length"] = df["comment_content"].str.len()
    return df


# ----------------------------------------------------------------------
# 图表 1: 各动漫评论数量 Top 20
# ----------------------------------------------------------------------
def plot_count_per_anime(df: pd.DataFrame, out_path: str, top: int = 20) -> str:
    counts = (
        df.groupby("anime_title")
        .size()
        .sort_values(ascending=True)
        .tail(top)
    )
    fig, ax = plt.subplots(figsize=(11, 8))
    y_pos = np.arange(len(counts))
    values = counts.values
    norm = plt.Normalize(values.min(), values.max())
    colors = plt.cm.viridis(norm(values))
    ax.barh(y_pos, values, color=colors, edgecolor="black", linewidth=0.4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(counts.index, fontsize=9)
    ax.set_xlabel("评论数量")
    ax.set_title(f"各动漫评论数量 Top {top}", fontsize=14, fontweight="bold")
    for i, v in enumerate(values):
        ax.text(v + max(values) * 0.01, i, f"{v:,}", va="center", fontsize=8)
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 图表 2: 单动漫每日评论数量趋势
# ----------------------------------------------------------------------
def plot_daily_trend(df: pd.DataFrame, out_path: str,
                     anime_title: Optional[str] = None) -> str:
    if anime_title is None:
        anime_title = df["anime_title"].value_counts().idxmax()
    sub = df[df["anime_title"] == anime_title].sort_values("comment_time")
    if sub.empty:
        return ""

    daily = sub.groupby("date").size()
    full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_idx, fill_value=0)

    kernel = np.ones(7) / 7
    smoothed = np.convolve(daily.values, kernel, mode="valid")

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(daily.index, daily.values, color="#4C72B0", alpha=0.4,
            label="每日评论数", linewidth=1, marker="o", markersize=2)
    ax.plot(daily.index[6:], smoothed, color="#C44E52", linewidth=2.2,
            label="7 日滑动平均")
    ax.set_title(f"动漫《{anime_title[:30]}》每日评论数量趋势", fontsize=14, fontweight="bold")
    ax.set_xlabel("日期")
    ax.set_ylabel("评论数量")
    ax.legend()
    ax.grid(linestyle="--", alpha=0.4)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 图表 3: 评分分布
# ----------------------------------------------------------------------
def plot_rating_distribution(df: pd.DataFrame, out_path: str) -> str:
    ratings = df["rating"].values
    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.arange(0.5, 5.5, 1.0)
    counts, edges, patches = ax.hist(
        ratings, bins=bins, edgecolor="black", color="#55A868", linewidth=0.6,
    )
    cmap = plt.cm.RdYlGn
    for i, patch in enumerate(patches):
        patch.set_facecolor(cmap(0.15 + 0.7 * (i / len(patches))))
    percentages = counts / counts.sum() * 100
    for i, (c, p, patch) in enumerate(zip(counts, percentages, patches)):
        if c > 0:
            cx = patch.get_x() + patch.get_width() / 2
            ax.text(cx, c + max(counts) * 0.01,
                    f"{int(c):,}\n({p:.1f}%)", ha="center", fontsize=9)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xlabel("评分 (1-5, 由 MAL 1-10 归一化)")
    ax.set_ylabel("评论条数")
    ax.set_title("动漫长评评分分布", fontsize=14, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 图表 4: 月度评论趋势
# ----------------------------------------------------------------------
def plot_monthly_trend(df: pd.DataFrame, out_path: str) -> str:
    monthly = df.groupby("year_month").size()
    # x 轴显式用整数下标, 避免 matplotlib 把 "2024-01" 当 category 告警
    x_idx = np.arange(len(monthly))
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.fill_between(x_idx, monthly.values, alpha=0.25, color="#4C72B0")
    ax.plot(x_idx, monthly.values, marker="o", color="#4C72B0", linewidth=1.8)
    # 每隔合理步长显示一个刻度标签, 避免重叠
    step = max(1, len(monthly) // 15)
    ax.set_xticks(x_idx[::step])
    ax.set_xticklabels([str(monthly.index[i]) for i in range(0, len(monthly), step)],
                       rotation=45, ha="right")
    if len(monthly) > 0:
        peak_idx = monthly.values.argmax()
        ax.annotate(
            f"峰值: {int(monthly.values[peak_idx])} 条",
            xy=(x_idx[peak_idx], monthly.values[peak_idx]),
            xytext=(0, 25), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="#C44E52"),
            color="#C44E52", fontweight="bold", ha="center",
        )
    ax.set_title("评论数量月度趋势", fontsize=14, fontweight="bold")
    ax.set_xlabel("月份")
    ax.set_ylabel("评论条数")
    ax.grid(linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 图表 5: 类型对比
# ----------------------------------------------------------------------
def plot_type_comparison(df: pd.DataFrame, out_path: str) -> str:
    grouped = df.groupby("category").agg(
        count=("comment_id", "size"),
        avg_rating=("rating", "mean"),
    ).sort_values("count", ascending=False)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = np.arange(len(grouped))
    width = 0.6
    ax1.bar(x, grouped["count"], width=width, color="#8172B2",
            edgecolor="black", linewidth=0.4, label="评论数")
    ax1.set_xticks(x)
    ax1.set_xticklabels(grouped.index, rotation=15, ha="right")
    ax1.set_ylabel("评论条数")
    ax1.set_title("各类型动漫评论数量与平均评分", fontsize=14, fontweight="bold")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    ax2 = ax1.twinx()
    ax2.plot(x, grouped["avg_rating"], color="#C44E52", marker="o",
             linewidth=2, label="平均评分")
    ax2.set_ylabel("平均评分", color="#C44E52")
    ax2.set_ylim(0, 5.5)
    ax2.tick_params(axis="y", colors="#C44E52")

    for i, v in enumerate(grouped["count"]):
        ax1.text(i, v + grouped["count"].max() * 0.01,
                 f"{v:,}", ha="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 图表 6: 评分 vs 字数 + 散点
# ----------------------------------------------------------------------
def plot_rating_vs_length(df: pd.DataFrame, out_path: str) -> str:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    sub = df[["rating", "content_length"]].copy()
    sub = sub[sub["rating"].between(1, 5)]
    data_by_rating = [sub[sub["rating"] == r]["content_length"].values
                      for r in range(1, 6)]
    bp = ax1.boxplot(data_by_rating, labels=[1, 2, 3, 4, 5], patch_artist=True,
                     boxprops=dict(facecolor="#DDD"), medianprops=dict(color="#C44E52"))
    cmap = plt.cm.RdYlGn
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(cmap(0.15 + 0.7 * (i / 5)))
    ax1.set_title("不同评分的评论字数分布")
    ax1.set_xlabel("评分")
    ax1.set_ylabel("字数")
    ax1.grid(linestyle="--", alpha=0.4)

    sample = df.sample(min(2000, len(df)), random_state=42)
    sc = ax2.scatter(
        sample["content_length"], sample["like_count"],
        c=sample["rating"], cmap="RdYlGn", alpha=0.5, s=12,
        edgecolors="none",
    )
    if len(sample) > 1:
        corr = np.corrcoef(sample["content_length"], sample["like_count"])[0, 1]
    else:
        corr = 0
    ax2.set_title(f"Reactions vs 评论字数 (Pearson r={corr:.3f})")
    ax2.set_xlabel("评论字数")
    ax2.set_ylabel("Reactions 数量")
    ax2.set_yscale("log")
    ax2.grid(linestyle="--", alpha=0.4)
    plt.colorbar(sc, ax=ax2, label="评分")

    fig.suptitle("评论文本与反馈分析", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 图表 7: 高频词
# ----------------------------------------------------------------------
def _tokenize(text: str) -> list:
    text = re.sub(r"\s+", "", text or "")
    tokens = []
    for i in range(len(text) - 1):
        chunk = text[i:i + 2]
        if re.fullmatch(r"[一-龥]{2}", chunk):
            tokens.append(chunk)
    for w in re.findall(r"[A-Za-z]{2,}", text):
        tokens.append(w)
    return tokens


def plot_top_keywords(df: pd.DataFrame, out_path: str, top: int = 20) -> str:
    counter: Counter = Counter()
    for text in df["comment_content"]:
        counter.update(_tokenize(text))
    common = counter.most_common(top)

    words = [w for w, _ in common][::-1]
    counts = [c for _, c in common][::-1]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(np.arange(len(words)), counts, color="#4C72B0",
            edgecolor="black", linewidth=0.4)
    ax.set_yticks(np.arange(len(words)))
    ax.set_yticklabels(words, fontsize=11)
    ax.set_title(f"评论高频词 Top {top}", fontsize=14, fontweight="bold")
    ax.set_xlabel("出现次数")
    for i, v in enumerate(counts):
        ax.text(v + max(counts) * 0.01, i, f"{v:,}", va="center", fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    logger.info("已保存 %s", out_path)
    return out_path


# ----------------------------------------------------------------------
# 一键运行
# ----------------------------------------------------------------------
def generate_all_charts(df: Optional[pd.DataFrame] = None,
                         out_dir: Optional[str] = None) -> list:
    if df is None:
        df = load_dataframe()
    if df.empty:
        logger.warning("无数据, 跳过图表生成")
        return []

    if out_dir is None:
        log_dir = config.LOG_DIR or "logs"
        project_root = os.path.dirname(os.path.abspath(log_dir)) or "."
        out_dir = os.path.join(project_root, "output", "charts")
    os.makedirs(out_dir, exist_ok=True)

    out = []
    out.append(plot_count_per_anime(df, os.path.join(out_dir, "01_count_per_anime.png")))
    out.append(plot_daily_trend(df, os.path.join(out_dir, "02_daily_trend.png")))
    out.append(plot_rating_distribution(df, os.path.join(out_dir, "03_rating_distribution.png")))
    out.append(plot_monthly_trend(df, os.path.join(out_dir, "04_monthly_trend.png")))
    out.append(plot_type_comparison(df, os.path.join(out_dir, "05_type_comparison.png")))
    out.append(plot_rating_vs_length(df, os.path.join(out_dir, "06_rating_vs_length.png")))
    out.append(plot_top_keywords(df, os.path.join(out_dir, "07_top_keywords.png")))
    return [p for p in out if p]
