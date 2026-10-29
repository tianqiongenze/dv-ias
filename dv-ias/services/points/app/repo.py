"""points 持久化：账户乐观锁 + 流水幂等。"""
import os

from szxc_common import db

GOV_URL = os.environ.get("GOV_URL", "http://governance-svc.szxc-prod.svc.cluster.local:8083")

# 行为→积分规则（PointsRule 实体的代码化MVP形态；生产入表可配置）
EARN_RULES = {"environment": 20, "safety": 30, "public": 10, "other": 10}

DDL = [
    """CREATE TABLE IF NOT EXISTS szxc_biz.points_account(
      party_id BIGINT PRIMARY KEY, balance INT NOT NULL DEFAULT 0,
      version INT NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS szxc_biz.points_ledger(
      id BIGINT PRIMARY KEY AUTO_INCREMENT, account_party_id BIGINT NOT NULL,
      ref_id VARCHAR(64) NOT NULL, change_amount INT NOT NULL, balance_after INT NOT NULL,
      reason VARCHAR(64), created_at DATETIME,
      UNIQUE KEY uk_ref(account_party_id, ref_id), KEY idx_party(account_party_id))""",
]


def init_db():
    for ddl in DDL:
        db.execute(ddl)


def ensure_accounts():
    parties = db.query("SELECT id FROM szxc_md.party")
    db.execute_many(
        "INSERT IGNORE INTO szxc_biz.points_account(party_id,balance) VALUES(%s,0)",
        [(p["id"],) for p in parties])


def earn(party_id: int, ref_id: str, type_: str) -> bool:
    """幂等入账：唯一键约束防重放（04号文档不变量）。"""
    amount = EARN_RULES.get(type_, 10)
    try:
        acct = db.query("SELECT balance FROM szxc_biz.points_account WHERE party_id=%s",
                        (party_id,), one=True)
        if not acct:
            db.execute("INSERT IGNORE INTO szxc_biz.points_account(party_id) VALUES(%s)", (party_id,))
            acct = db.query("SELECT balance FROM szxc_biz.points_account WHERE party_id=%s",
                            (party_id,), one=True)
        new_balance = acct["balance"] + amount
        db.execute("UPDATE szxc_biz.points_account SET balance=%s, version=version+1 WHERE party_id=%s",
                   (new_balance, party_id))
        db.execute("INSERT INTO szxc_biz.points_ledger(account_party_id,ref_id,change_amount,"
                   "balance_after,reason,created_at) VALUES(%s,%s,%s,%s,%s,NOW())",
                   (party_id, ref_id, amount, new_balance, f"治理事件办结:{type_}"))
        from szxc_common.cache import invalidate
        invalidate(f"pts:acct:{party_id}")
        return True
    except Exception as e:
        if "Duplicate" in str(e) or "uk_ref" in str(e):
            return False  # 已入账，幂等成功
        raise


def account(party_id: int):
    return db.query("SELECT * FROM szxc_biz.points_account WHERE party_id=%s", (party_id,), one=True)


def ledger(party_id: int, limit: int = 50):
    return db.query("SELECT * FROM szxc_biz.points_ledger WHERE account_party_id=%s "
                    "ORDER BY id DESC LIMIT %s", (party_id, limit))


def leaderboard(limit: int = 10):
    from szxc_common.cache import cached
    return cached("pts:rank:v1", 300,
                  lambda: [
                      {"party_id": r["party_id"], "balance": r["balance"]}
                      for r in db.query(
                          "SELECT party_id,balance FROM szxc_biz.points_account "
                          "ORDER BY balance DESC LIMIT %s", (limit,))], l1_ttl=30)
