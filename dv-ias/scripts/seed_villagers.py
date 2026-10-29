# -*- coding: utf-8 -*-
# 扩充村民账号至 ~600（stress 每 VU 独立账号，避免共享 600req/min/用户 限流桶）
import sys
sys.path.insert(0, "/srv")
from szxc_common import db
from szxc_common.crypto import sm3, sm4_encrypt, sm3_pbkdf2
import secrets, traceback

try:
    existing = db.query("SELECT COUNT(*) c FROM szxc_md.party WHERE role='villager'", one=True)["c"]
    print("existing villagers", existing, flush=True)
    created = 0
    # 新增 客户端 301..600（8位尾号补零）
    for n in range(301, 601):
        phone = "138%08d" % n
        # 去重
        dup = db.query("SELECT 1 FROM szxc_md.party WHERE phone_hash=%s", (sm3(phone.encode()),), one=True)
        if dup:
            continue
        org = "5306001010%d" % ((n - 1) % 6 + 1)
        salt = secrets.token_hex(16)
        pid = db.execute(
            "INSERT INTO szxc_md.party(name,phone_hash,phone_enc,org_code,role) VALUES(%s,%s,%s,%s,%s)",
            ("压测村民%d" % n, sm3(phone.encode()), sm4_encrypt(phone), org, "villager"))
        db.execute("INSERT INTO szxc_md.account(party_id,password_salt,password_hash) VALUES(%s,%s,%s)",
                   (pid, salt, sm3_pbkdf2("szxc@2026", salt, 10000)))
        created += 1
    print("SEED-VILLAGERS created=%d" % created, flush=True)
except Exception:
    print("SEED-FAIL", traceback.format_exc()[-400:], flush=True)