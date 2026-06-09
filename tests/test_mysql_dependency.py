def test_pymysql_is_available_in_app_runtime() -> None:
    import pymysql

    assert pymysql.__name__ == "pymysql"


def test_mysql_dependency_flag_is_true_when_pymysql_installed() -> None:
    from sqlmind_agent.dependency_check import MYSQL_AVAILABLE

    assert MYSQL_AVAILABLE is True
