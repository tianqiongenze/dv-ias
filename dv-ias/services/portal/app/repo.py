"""portal 持久化与种子。"""
from szxc_common import db

DDL = ["""CREATE TABLE IF NOT EXISTS szxc_biz.publication(
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  village_code CHAR(12) NOT NULL, `column` VARCHAR(16) NOT NULL,
  title VARCHAR(128) NOT NULL, content TEXT NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'published',
  publisher_id BIGINT, published_at DATETIME,
  KEY idx_village(village_code, `column`, published_at))"""]

FORBIDDEN = ["暴力", "赌", "诈骗"]  # 内容审核极简词表（AI审核见07号文档治理辅助Agent）


def init_db():
    for ddl in DDL:
        db.execute(ddl)


def list_pub(village_code: str | None, column: str | None, page: int, size: int):
    where, args = "WHERE status='published'", []
    if village_code:
        where += " AND village_code LIKE %s"; args.append(village_code + "%")
    if column:
        where += " AND `column`=%s"; args.append(column)
    args += [size, (page - 1) * size]
    return db.query(f"SELECT * FROM szxc_biz.publication {where} "
                    f"ORDER BY published_at DESC LIMIT %s OFFSET %s", tuple(args))


def count_pub(village_code: str | None, column: str | None) -> int:
    where, args = "WHERE status='published'", []
    if village_code:
        where += " AND village_code LIKE %s"; args.append(village_code + "%")
    if column:
        where += " AND `column`=%s"; args.append(column)
    r = db.query(f"SELECT COUNT(*) c FROM szxc_biz.publication {where}", tuple(args), one=True)
    return r["c"]


def get_pub(pid: int):
    return db.query("SELECT * FROM szxc_biz.publication WHERE id=%s", (pid,), one=True)


def create_pub(village_code, column, title, content, publisher_id):
    if any(w in content or w in title for w in FORBIDDEN):
        raise ValueError("内容包含违规词，已被拦截")
    return db.execute(
        "INSERT INTO szxc_biz.publication(village_code,`column`,title,content,publisher_id,published_at) "
        "VALUES(%s,%s,%s,%s,%s,NOW())", (village_code, column, title, content, publisher_id))


def invalidate_list():
    from szxc_common.cache import invalidate_prefix
    invalidate_prefix("pub:list:")


def seed_if_empty():
    if db.query("SELECT 1 FROM szxc_biz.publication LIMIT 1", one=True):
        return
    villages = [("53060010101", "清溪村"), ("53060010102", "麦香村"), ("53060010103", "柳林村"),
                ("53060010201", "稻花村"), ("53060010202", "山泉村"), ("53060010203", "云岭村")]
    rows = []
    for code, name in villages:
        rows.append((code, "村务", f"{name}2026年第四季度村务公开",
                     f"{name}村民委员会现将本季度村级事务办理情况公开如下：一、人居环境整治完成3处点位改造；二、新建文化广场已竣工验收；三、下季度重点推进高标准农田建设。监督电话：0871-6800000。"))
        rows.append((code, "财务", f"{name}2026年10月财务收支明细",
                     f"{name}本月村级财务：收入合计48,600元（含村集体林地承包收入），支出合计36,200元（环卫保洁、路灯电费、文化活动），结余12,400元，明细账目可到村委会查阅。"))
        rows.append((code, "党务", f"{name}党支部10月主题党日活动公示",
                     f"{name}党支部于10月15日开展《田间党课》主题党日活动，组织党员32人参加秋粮抢收志愿服务，帮助缺劳力户收割水稻18亩。"))
    db.execute_many(
        "INSERT INTO szxc_biz.publication(village_code,`column`,title,content,publisher_id,published_at) "
        "VALUES(%s,%s,%s,%s,1,NOW())", rows)
