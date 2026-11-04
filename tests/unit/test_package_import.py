"""Infrastructure smoke tests."""


def test_package_imports() -> None:
    import neon_armada

    assert neon_armada.__name__ == "neon_armada"
