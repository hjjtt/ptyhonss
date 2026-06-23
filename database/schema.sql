-- ============================================================
-- Jikan (MyAnimeList) 动漫评论数据库结构 (SQLite) - 幂等版本
-- 重复执行不会破坏已有数据
-- 提交作业中 "sql 数据库表结构" 即此文件
-- ============================================================

-- ------------------------------------------------------------
-- 1. 动漫表 (类比"商家")
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anime (
    mal_id          INTEGER PRIMARY KEY,    -- MyAnimeList ID
    title           TEXT NOT NULL,          -- 标题
    title_english   TEXT,                   -- 英文标题
    title_japanese  TEXT,                   -- 日文标题
    type            TEXT,                   -- TV / Movie / OVA ...
    episodes        INTEGER,                -- 集数
    score           REAL,                   -- MAL 评分 (1-10)
    scored_by       INTEGER,                -- 评分人数
    rank            INTEGER,                -- 总排名
    popularity      INTEGER,                -- 热度排名
    year            INTEGER,                -- 上映年份
    image_url       TEXT,                   -- 海报 URL
    created_at      TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- 2. 评论主表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comment (
    comment_id       TEXT PRIMARY KEY,        -- MAL review id
    user_id          TEXT NOT NULL,           -- MAL profile URL
    user_name        TEXT,                    -- MAL 用户名
    mal_id           INTEGER NOT NULL,        -- 所属动漫 id
    merchant_name    TEXT NOT NULL,           -- 动漫标题 (冗余)
    rating           INTEGER NOT NULL,        -- 1-5 (归一化自 MAL score)
    like_count       INTEGER,                 -- reactions overall
    comment_time     TEXT NOT NULL,           -- 'YYYY-MM-DD HH:MM:SS'
    comment_content  TEXT NOT NULL,           -- 评论正文
    created_at       TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (mal_id) REFERENCES anime(mal_id)
);

-- ------------------------------------------------------------
-- 3. 索引
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_comment_anime    ON comment(mal_id);
CREATE INDEX IF NOT EXISTS idx_comment_time     ON comment(comment_time);
CREATE INDEX IF NOT EXISTS idx_comment_rating   ON comment(rating);
CREATE INDEX IF NOT EXISTS idx_comment_user     ON comment(user_id);
CREATE INDEX IF NOT EXISTS idx_anime_type       ON anime(type);

-- ------------------------------------------------------------
-- 4. 视图
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_comment_full;
CREATE VIEW v_comment_full AS
SELECT
    c.comment_id,
    c.user_id,
    c.user_name,
    a.type            AS category,
    a.title           AS anime_title,
    a.year,
    a.score           AS anime_score,
    c.mal_id,
    c.merchant_name,
    c.rating,
    c.like_count,
    c.comment_time,
    c.comment_content
FROM comment c
LEFT JOIN anime a ON c.mal_id = a.mal_id;
