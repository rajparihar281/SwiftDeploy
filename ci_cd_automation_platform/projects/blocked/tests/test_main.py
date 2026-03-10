def test_failure():
    """A test that always fails to verify 'BLOCK' governance status."""
    assert False, "Intentional failure for governance blocking test"

def test_logic():
    """This test won't even matter if the one above fails."""
    assert 1 + 1 == 2
