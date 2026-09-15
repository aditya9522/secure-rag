from app.security.passwords import hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    password = "correct horse battery staple"
    first = hash_password(password)
    second = hash_password(password)

    assert first != second
    assert verify_password(password, first)
    assert not verify_password("wrong password", first)
    assert not verify_password(password, "not-a-valid-hash")
