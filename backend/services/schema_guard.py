"""pre-Alembic DB 를 "최신" 으로 표시하기 전에 스키마를 확인한다.

테이블은 있는데 `alembic_version` 이 없는 DB 를 그대로 `stamp(head)` 하면, 구버전
스키마가 최신으로 표시되고 그 사이 마이그레이션이 전부 건너뛰어진다. 그 뒤 API 가
없는 컬럼을 찾다가 죽거나 중복을 그대로 받는다.

어느 시점의 스키마인지 알 수 없는 DB 를 자동으로 맞추려 들면 더 망가진다.
표지가 되는 컬럼을 검사해 최신이면 표시하고, 아니면 멈추고 사람에게 알린다.
"""


class SchemaMismatch(RuntimeError):
    """pre-Alembic DB 의 스키마가 최신이 아니다."""


#: 최신 스키마의 표지. 나중에 마이그레이션으로 들어온 컬럼을 고른다.
#: 이것이 다 있으면 head 로 봐도 된다는 뜻이지, 스키마 전체를 검증하지는 않는다.
REQUIRED_COLUMNS = {
    "test_runs": ["sheet_names", "round", "test_plan_id"],
    "test_cases": ["deleted_at", "sheet_name", "custom_fields"],
    "test_case_sheets": ["parent_id", "is_folder"],
    "users": ["must_change_password"],
    "projects": ["is_private", "field_config"],
}


def assert_schema_is_current(inspector) -> None:
    """표지 컬럼이 다 있는지 본다. 없으면 `SchemaMismatch` 를 낸다."""
    tables = set(inspector.get_table_names())
    missing: list[str] = []

    for table, columns in REQUIRED_COLUMNS.items():
        if table not in tables:
            missing.append(f"{table} (테이블 없음)")
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        for column in columns:
            if column not in present:
                missing.append(f"{table}.{column}")

    if missing:
        raise SchemaMismatch(
            "이 DB 는 Alembic 으로 관리되지 않은 구버전 스키마입니다. "
            "최신으로 표시하면 그 사이 마이그레이션이 건너뛰어져 이후 요청이 실패합니다. "
            f"없는 것: {', '.join(missing)}. "
            "백업한 뒤 빈 DB 로 새로 만들거나, 손으로 스키마를 맞춘 다음 다시 실행해 주세요."
        )
