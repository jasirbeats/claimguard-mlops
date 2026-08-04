from claimguard.data.generate import generate_claims


def test_generation_is_reproducible() -> None:
    first = generate_claims(rows=250, seed=7)
    second = generate_claims(rows=250, seed=7)
    assert first.equals(second)
    assert first["claim_tracking_id"].is_unique
    assert set(first["will_become_stuck"].unique()).issubset({0, 1})
