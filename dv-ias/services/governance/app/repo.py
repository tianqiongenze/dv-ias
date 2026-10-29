"""governance 持久化：事件状态机 + 流转记录 + 种子。"""
import datetime as dt

from szxc_common import db
from szxc_common.cache import counter

# 状态机（04号文档 GovernanceEvent 聚合）
TRANSITIONS = {
    "pending":   {"accept": "accepted", "reject": "rejected"},
    "accepted":  {"dispatch": "dispatched"},
    "dispatched": {"resolve": "resolved"},
    "resolved":  {"approve": "approved", "reject": "rejected"},
}

DDL = [
    """CREATE TABLE IF NOT EXISTS szxc_biz.gov_event(
      id BIGINT PRIMARY KEY AUTO_INCREMENT, sn VARCHAR(32) NOT NULL UNIQUE,
      village_code CHAR(12) NOT NULL, type VARCHAR(32) NOT NULL,
      source VARCHAR(16) NOT NULL, state VARCHAR(16) NOT NULL,
      geo_lat DOUBLE, geo_lng DOUBLE, description TEXT,
      reporter_id BIGINT NOT NULL, assignee_id BIGINT,
      created_at DATETIME, updated_at DATETIME,
      KEY idx_village_state(village_code, state, created_at), KEY idx_reporter(reporter_id))""",
    """CREATE TABLE IF NOT EXISTS szxc_biz.event_transition(
      id BIGINT PRIMARY KEY AUTO_INCREMENT, event_id BIGINT NOT NULL,
      action VARCHAR(32) NOT NULL, actor_id BIGINT, note TEXT,
      created_at DATETIME, KEY idx_event(event_id))""",
]

EARN_POINTS = {"environment": 20, "safety": 30, "public": 10, "other": 10}


def init_db():
    for ddl in DDL:
        db.execute(ddl)


def next_sn() -> str:
    seq = counter("seq:gov_event", 1)
    if seq < 0:  # Redis 不可用降级为时间戳
        seq = int(dt.datetime.now().strftime("%H%M%S%f")[:8])
    return f"EVT{dt.date.today():%Y%m%d}{seq:06d}"


def submit(village_code, type_, source, lat, lng, desc, reporter_id) -> int:
    sn = next_sn()
    eid = db.execute(
        "INSERT INTO szxc_biz.gov_event(sn,village_code,type,source,state,geo_lat,geo_lng,"
        "description,reporter_id,created_at,updated_at) "
        "VALUES(%s,%s,%s,%s,'pending',%s,%s,%s,%s,NOW(),NOW())",
        (sn, village_code, type_, source, lat, lng, desc, reporter_id))
    db.execute("INSERT INTO szxc_biz.event_transition(event_id,action,actor_id,created_at) "
               "VALUES(%s,'submit',%s,NOW())", (eid, reporter_id))
    return eid


def transition(eid: int, action: str, actor_id: int, note: str = "") -> dict:
    """聚合行为：校验状态机合法迁移，写主库+流转记录（同线程顺序保证）。"""
    ev = db.query("SELECT * FROM szxc_biz.gov_event WHERE id=%s", (eid,), one=True)
    if not ev:
        raise ValueError("事件不存在")
    allowed = TRANSITIONS.get(ev["state"], {})
    if action not in allowed:
        raise ValueError(f"事件处于 {ev['state']} 状态，不允许 {action}")
    new_state = allowed[action]
    assignee = ev["assignee_id"]
    if action in ("accept", "dispatch"):
        assignee = actor_id
    db.execute("UPDATE szxc_biz.gov_event SET state=%s, assignee_id=%s, updated_at=NOW() WHERE id=%s",
               (new_state, assignee, eid))
    db.execute("INSERT INTO szxc_biz.event_transition(event_id,action,actor_id,note,created_at) "
               "VALUES(%s,%s,%s,%s,NOW())", (eid, action, actor_id, note))
    from szxc_common.cache import invalidate_prefix
    invalidate_prefix("gov:evt:")
    return get(eid)


def get(eid: int):
    return db.query("SELECT * FROM szxc_biz.gov_event WHERE id=%s", (eid,), one=True)


def timeline(eid: int):
    return db.query("SELECT * FROM szxc_biz.event_transition WHERE event_id=%s ORDER BY id", (eid,))


def list_events(village_code=None, state=None, reporter_id=None, page=1, size=20):
    where, args = "WHERE 1=1", []
    if village_code:
        where += " AND village_code LIKE %s"; args.append(village_code + "%")
    if state:
        where += " AND state=%s"; args.append(state)
    if reporter_id:
        where += " AND reporter_id=%s"; args.append(reporter_id)
    args += [size, (page - 1) * size]
    return db.query(f"SELECT * FROM szxc_biz.gov_event {where} ORDER BY id DESC LIMIT %s OFFSET %s",
                    tuple(args))


def approved_after(after_id: int):
    return db.query("SELECT * FROM szxc_biz.gov_event WHERE id>%s AND state='approved' "
                    "ORDER BY id LIMIT 200", (after_id,))


def seed_if_empty():
    if db.query("SELECT 1 FROM szxc_biz.gov_event LIMIT 1", one=True):
        return
    import random
    types = list(EARN_POINTS)
    villages = ["53060010101", "53060010102", "53060010103", "53060010201", "53060010202", "53060010203"]
    states = ["pending", "accepted", "dispatched", "resolved", "approved"]
    for i in range(36):
        v = random.choice(villages)
        st = states[i % len(states)]
        eid = submit(v, types[i % len(types)], "citizen" if i % 3 else "patrol",
                     25.0 + random.random(), 102.5 + random.random(),
                     f"种子事件{i + 1}：{'垃圾堆放待清理' if i % 4 == 0 else '道路积水/路灯故障/噪声扰民等'}",
                     9 + (i % 30))
        if st != "pending":
            for act in ["accept", "dispatch", "resolve"][: states.index(st)]:
                transition(eid, act, 4)
            if st == "approved":
                transition(eid, "approve", 3)
