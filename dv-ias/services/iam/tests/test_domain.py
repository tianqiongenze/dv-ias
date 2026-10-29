"""iam TDD 单元测试：国密口令派生、JWT 签发校验、手机号脱敏（不依赖DB）。"""
import os, sys
sys.path.insert(0, "/srv")

from szxc_common.crypto import sm3, sm3_pbkdf2, sm4_encrypt, sm4_decrypt, mask_phone
from szxc_common.web import issue_token
import jwt


def test_sm3_deterministic_and_differs():
    assert sm3(b"abc") == sm3(b"abc")
    assert sm3(b"abc") != sm3(b"abd")
    assert len(sm3(b"x")) == 64  # 32字节hex


def test_password_hash_salt_changes_output():
    h1 = sm3_pbkdf2("szxc@2026", "aa" * 16, 100)
    h2 = sm3_pbkdf2("szxc@2026", "bb" * 16, 100)
    assert h1 != h2 and len(h1) == 64


def test_sm4_roundtrip_and_mask():
    enc = sm4_encrypt("13800000001")
    assert enc != "13800000001"
    assert sm4_decrypt(enc) == "13800000001"
    assert mask_phone("13800000001") == "138****0001"


def test_jwt_roundtrip():
    tok = issue_token(7, "张三", ["villager"])
    payload = jwt.decode(tok, os.environ.get("JWT_SECRET", "SzxcJwt-2026-bN8wQ4vXzA6sD1fG"),
                         algorithms=["HS256"])
    assert payload["sub"] == "7" and payload["roles"] == ["villager"]  # PyJWT≥2.10 要求 sub 为字符串
