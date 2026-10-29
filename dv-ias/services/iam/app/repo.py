"""iam 持久化：DDL + 仓储 + 种子（幂等）。"""
from szxc_common import db
from szxc_common.crypto import sm3, sm3_pbkdf2, sm4_encrypt, sm4_decrypt, mask_phone
import os, secrets

DDL = [
    """CREATE TABLE IF NOT EXISTS szxc_md.org(
      code CHAR(12) PRIMARY KEY, name VARCHAR(64) NOT NULL,
      level VARCHAR(16) NOT NULL, parent_code CHAR(12),
      KEY idx_parent(parent_code))""",
    """CREATE TABLE IF NOT EXISTS szxc_md.party(
      id BIGINT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(64) NOT NULL,
      phone_hash CHAR(64) NOT NULL UNIQUE, phone_enc TEXT NOT NULL,
      org_code CHAR(12) NOT NULL, role VARCHAR(32) NOT NULL,
      KEY idx_org(org_code))""",
    """CREATE TABLE IF NOT EXISTS szxc_md.account(
      id BIGINT PRIMARY KEY AUTO_INCREMENT, party_id BIGINT NOT NULL UNIQUE,
      password_salt CHAR(32) NOT NULL, password_hash CHAR(64) NOT NULL,
      status VARCHAR(16) NOT NULL DEFAULT 'active')""",
]


def hash_password(password: str, salt_hex: str) -> str:
    return sm3_pbkdf2(password, salt_hex, 10000)


def init_db():
    for ddl in DDL:
        db.execute(ddl)


def org_children(code: str):
    return db.query("SELECT * FROM szxc_md.org WHERE parent_code=%s ORDER BY code", (code,))


def org(code: str):
    return db.query("SELECT * FROM szxc_md.org WHERE code=%s", (code,), one=True)


def org_tree_cached():
    from szxc_common.cache import cached
    return cached("md:org:tree:v1", 1800, _load_org_tree, l1_ttl=60)


def _load_org_tree():
    rows = db.query("SELECT * FROM szxc_md.org ORDER BY code")
    nodes = {r["code"]: {"code": r["code"], "name": r["name"], "level": r["level"],
                         "parent": r["parent_code"], "children": []} for r in rows}
    roots = []
    for n in nodes.values():
        p = nodes.get(n["parent"])
        (p["children"] if p else roots).append(n)
    return roots


def party(pid: int):
    r = db.query("SELECT p.*, a.id AS account_id FROM szxc_md.party p "
                 "LEFT JOIN szxc_md.account a ON a.party_id=p.id WHERE p.id=%s", (pid,), one=True)
    if r:
        r["phone"] = sm4_decrypt(r["phone_enc"])
    return r


def party_by_phone(phone: str):
    ph = sm3(phone.encode()).hex() if isinstance(sm3(phone.encode()), bytes) else sm3(phone.encode())
    return db.query("SELECT p.*, a.password_salt, a.password_hash, a.id AS account_id "
                    "FROM szxc_md.party p JOIN szxc_md.account a ON a.party_id=p.id "
                    "WHERE p.phone_hash=%s AND a.status='active'", (ph,), one=True)


def create_party(name: str, phone: str, org_code: str, role: str, password: str | None = None):
    salt = secrets.token_hex(16)
    pid = db.execute(
        "INSERT INTO szxc_md.party(name,phone_hash,phone_enc,org_code,role) VALUES(%s,%s,%s,%s,%s)",
        (name, sm3(phone.encode()), sm4_encrypt(phone), org_code, role))
    db.execute("INSERT INTO szxc_md.account(party_id,password_salt,password_hash) VALUES(%s,%s,%s)",
               (pid, salt, hash_password(password or "szxc@2026", salt)))
    return pid


# ───────── 种子数据（示例县：绿野县）─────────
def seed_if_empty():
    if db.query("SELECT 1 FROM szxc_md.party LIMIT 1", one=True):
        return
    orgs = [
        ("530600", "绿野县", "COUNTY", None),
        ("530600101", "青禾乡", "TOWNSHIP", "530600"),
        ("530600102", "沃野乡", "TOWNSHIP", "530600"),
        ("53060010101", "清溪村", "VILLAGE", "530600101"),
        ("53060010102", "麦香村", "VILLAGE", "530600101"),
        ("53060010103", "柳林村", "VILLAGE", "530600101"),
        ("53060010201", "稻花村", "VILLAGE", "530600102"),
        ("53060010202", "山泉村", "VILLAGE", "530600102"),
        ("53060010203", "云岭村", "VILLAGE", "530600102"),
    ] + [(f"{v}{g:02d}", f"{vn}第{g}组", "GROUP", v)
         for v, vn in [("53060010101", "清溪村"), ("53060010102", "麦香村"), ("53060010103", "柳林村"),
                       ("53060010201", "稻花村"), ("53060010202", "山泉村"), ("53060010203", "云岭村")]
         for g in (1, 2)]
    db.execute_many("INSERT INTO szxc_md.org(code,name,level,parent_code) VALUES(%s,%s,%s,%s)", orgs)
    villages = ["53060010101", "53060010102", "53060010103", "53060010201", "53060010202", "53060010203"]
    # 县管理员
    create_party("张县管", "13900000001", "530600", "county_admin", "szxc@2026")
    idx = 2
    for v in villages:
        create_party(f"{dict((o[0], o[1]) for o in orgs)[v]}村管", f"1390000{idx:05d}", v, "village_admin", "szxc@2026")
        idx += 1
        create_party(f"{dict((o[0], o[1]) for o in orgs)[v]}网格员", f"1390000{idx:05d}", v, "grid_admin", "szxc@2026")
        idx += 1
    surnames = "王李张刘陈杨赵黄周吴徐孙马朱胡郭何高林罗"
    for i in range(30):
        v = villages[i % 6]
        name = surnames[i % len(surnames)] + "村民" + f"{i + 1:02d}"
        create_party(name, f"1380000{i + 1:05d}", v, "villager", "szxc@2026")
    from szxc_common.cache import invalidate
    invalidate("md:org:tree:v1")
