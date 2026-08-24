from unittest.mock import patch

# auth の import 時に実 .env を読まないよう load_dotenv を置き換える。
with patch("dotenv.load_dotenv"):
    from scripts import auth


def test_code_query_is_extracted_from_redirect_url() -> None:
    assert auth.extract_auth_code("https://localhost/?code=ABC123") == "ABC123"


def test_error_code_query_does_not_hide_code_query() -> None:
    url = "https://localhost/?error_code=99&code=ABC123"

    assert auth.extract_auth_code(url) == "ABC123"


def test_raw_authorization_code_is_accepted() -> None:
    assert auth.extract_auth_code("ABC123") == "ABC123"


def test_redirect_fragment_is_ignored() -> None:
    url = "https://localhost/?code=ABC123#_=_"

    assert auth.extract_auth_code(url) == "ABC123"
