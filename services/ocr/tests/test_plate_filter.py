from src.plate_filter import is_valid_taiwan_plate, normalize_plate


def test_standard_new_format():
    assert is_valid_taiwan_plate("ABC-1234") is True

def test_old_format_two_letters():
    assert is_valid_taiwan_plate("AB-1234") is True

def test_old_format_letters_both_sides():
    assert is_valid_taiwan_plate("AB-12CD") is False

def test_motorcycle_format():
    assert is_valid_taiwan_plate("ABC-123") is True

def test_new_6_digit():
    assert is_valid_taiwan_plate("1234-AB") is True

def test_invalid_too_short():
    assert is_valid_taiwan_plate("A-1") is False

def test_invalid_random_text():
    assert is_valid_taiwan_plate("HELLO WORLD") is False

def test_normalize_removes_spaces():
    assert normalize_plate("ABC  1234") == "ABC-1234"

def test_normalize_adds_dash():
    assert normalize_plate("ABC1234") == "ABC-1234"

def test_normalize_already_correct():
    assert normalize_plate("ABC-1234") == "ABC-1234"
