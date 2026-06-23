-- ============================================================
-- Jikan 动漫评论数据库结构 (SQLite) - 完整建表 (含清空)
-- 第一次创建数据库时使用, 第二次执行会清空数据
-- ============================================================

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS comment;
DROP TABLE IF EXISTS anime;
DROP VIEW  IF EXISTS v_comment_full;

PRAGMA foreign_keys = ON;

CREATE TABLE anime (
    mal_id          INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    title_english   TEXT,
    title_japanese  TEXT,
    type            TEXT,
    episodes        INTEGER,
    score           REAL,
    scored_by       INTEGER,
    rank            INTEGER,
    popularity      INTEGER,
    year            INTEGER,
    image_url       TEXT,
    created_at      TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE comment (
    comment_id       TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    user_name        TEXT,
    mal_id           INTEGER NOT NULL,
    merchant_name    TEXT NOT NULL,
    rating           INTEGER NOT NULL,
    like_count       INTEGER,
    comment_time     TEXT NOT NULL,
    comment_content  TEXT NOT NULL,
    created_at       TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (mal_id) REFERENCES anime(mal_id)
);

CREATE INDEX idx_comment_anime    ON comment(mal_id);
CREATE INDEX idx_comment_time     ON comment(comment_time);
CREATE INDEX idx_comment_rating   ON comment(rating);
CREATE INDEX idx_comment_user     ON comment(user_id);
CREATE INDEX idx_anime_type       ON anime(type);

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
