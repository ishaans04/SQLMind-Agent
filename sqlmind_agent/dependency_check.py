import sys

try:
    import pymysql

    MYSQL_AVAILABLE = True
except ImportError:
    pymysql = None
    MYSQL_AVAILABLE = False


def mysql_dependency_error() -> str:
    return (
        "MySQL support requires pymysql in the FastAPI/MCP Python interpreter: "
        f"{sys.executable}"
    )
