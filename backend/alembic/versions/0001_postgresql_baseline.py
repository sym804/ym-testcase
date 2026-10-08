"""PostgreSQL 기준점.

SQLite 시절 이력 14개(마지막 5e0b8c2d4f17)를 압축했다. 옛 이력은 sqlite-legacy
브랜치에 있다. 이 리비전은 현재 모델(models.py)의 스키마를 그대로 만든다.

Revision ID: 0001_pg_baseline
Revises: 
Create Date: 2026-10-08 22:19:29.650732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_pg_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.Enum('user', 'qa_manager', 'admin', name='userrole'), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('token_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('account_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request_type', sa.Enum('find_id', 'reset_password', name='accountrequesttype'), nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'completed', name='accountrequeststatus'), nullable=False),
    sa.Column('claimed_username', sa.String(length=100), nullable=True),
    sa.Column('claimed_display_name', sa.String(length=100), nullable=True),
    sa.Column('contact', sa.String(length=200), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('code_hash', sa.String(length=255), nullable=True),
    sa.Column('code_expires_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_account_requests_id'), 'account_requests', ['id'], unique=False)
    op.create_index('ix_account_requests_status_created', 'account_requests', ['status', 'created_at'], unique=False)
    op.create_table('api_keys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('key_id', sa.String(length=16), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_id')
    )
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('jira_base_url', sa.String(length=500), nullable=True),
    sa.Column('issue_tracker', sa.String(length=20), nullable=True),
    sa.Column('is_private', sa.Boolean(), nullable=False),
    sa.Column('field_config', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
    op.create_table('custom_field_defs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('field_name', sa.String(length=100), nullable=False),
    sa.Column('field_type', sa.String(length=20), nullable=False),
    sa.Column('options', sa.JSON(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_required', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_custom_field_defs_id'), 'custom_field_defs', ['id'], unique=False)
    op.create_table('project_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.Enum('tester', 'admin', name='projectrole'), nullable=False),
    sa.Column('added_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_members_id'), 'project_members', ['id'], unique=False)
    op.create_index('ix_project_members_project_user', 'project_members', ['project_id', 'user_id'], unique=True)
    op.create_table('saved_filters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('logic', sa.String(length=3), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_filters_id'), 'saved_filters', ['id'], unique=False)
    op.create_table('test_case_sheets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('is_folder', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['test_case_sheets.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_case_sheets_id'), 'test_case_sheets', ['id'], unique=False)
    op.create_index('ix_test_case_sheets_parent_id', 'test_case_sheets', ['parent_id'], unique=False)
    op.create_index('ix_test_case_sheets_project_id', 'test_case_sheets', ['project_id'], unique=False)
    op.create_index('uq_test_case_sheets_project_name', 'test_case_sheets', ['project_id', 'name'], unique=True)
    op.create_table('test_cases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('no', sa.Integer(), nullable=False),
    sa.Column('tc_id', sa.String(length=50), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=True),
    sa.Column('category', sa.String(length=200), nullable=True),
    sa.Column('depth1', sa.String(length=200), nullable=True),
    sa.Column('depth2', sa.String(length=200), nullable=True),
    sa.Column('priority', sa.String(length=20), nullable=True),
    sa.Column('test_type', sa.String(length=50), nullable=True),
    sa.Column('precondition', sa.Text(), nullable=True),
    sa.Column('test_steps', sa.Text(), nullable=True),
    sa.Column('expected_result', sa.Text(), nullable=True),
    sa.Column('r1', sa.String(length=10), nullable=True),
    sa.Column('r2', sa.String(length=10), nullable=True),
    sa.Column('r3', sa.String(length=10), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('sheet_name', sa.String(length=100), nullable=False),
    sa.Column('custom_fields', sa.JSON(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_cases_id'), 'test_cases', ['id'], unique=False)
    op.create_index('ix_test_cases_project_id_deleted', 'test_cases', ['project_id', 'deleted_at'], unique=False)
    op.create_index('ix_test_cases_sheet_name', 'test_cases', ['project_id', 'sheet_name'], unique=False)
    op.create_index('uq_test_cases_project_tc_id', 'test_cases', ['project_id', 'tc_id'], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('uq_test_cases_sheet_no', 'test_cases', ['project_id', 'sheet_name', 'no'], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('test_plans',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('milestone', sa.String(length=200), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('end_date', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_plans_id'), 'test_plans', ['id'], unique=False)
    op.create_table('test_case_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('test_case_id', sa.Integer(), nullable=False),
    sa.Column('changed_by', sa.Integer(), nullable=False),
    sa.Column('changed_at', sa.DateTime(), nullable=True),
    sa.Column('field_name', sa.String(length=100), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_case_history_id'), 'test_case_history', ['id'], unique=False)
    op.create_index('ix_test_case_history_tc_id', 'test_case_history', ['test_case_id'], unique=False)
    op.create_table('test_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=True),
    sa.Column('environment', sa.String(length=100), nullable=True),
    sa.Column('round', sa.Integer(), server_default='1', nullable=False),
    sa.Column('status', sa.Enum('in_progress', 'completed', name='testrunstatus'), nullable=True),
    sa.Column('sheet_names', sa.JSON(), nullable=True),
    sa.Column('test_plan_id', sa.Integer(), nullable=True),
    sa.Column('compare_run_id', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['compare_run_id'], ['test_runs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_plan_id'], ['test_plans.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_runs_id'), 'test_runs', ['id'], unique=False)
    op.create_index('ix_test_runs_project_id', 'test_runs', ['project_id'], unique=False)
    op.create_index('ix_test_runs_status', 'test_runs', ['project_id', 'status'], unique=False)
    op.create_table('run_issues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('test_run_id', sa.Integer(), nullable=False),
    sa.Column('issue_key', sa.String(length=50), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('origin_run_id', sa.Integer(), nullable=True),
    sa.Column('origin_round', sa.Integer(), nullable=True),
    sa.Column('verdict', sa.String(length=20), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['origin_run_id'], ['test_runs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['test_run_id'], ['test_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_issues_id'), 'run_issues', ['id'], unique=False)
    op.create_index('uq_run_issues_run_url', 'run_issues', ['test_run_id', 'url'], unique=True)
    op.create_table('test_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('test_run_id', sa.Integer(), nullable=False),
    sa.Column('test_case_id', sa.Integer(), nullable=False),
    sa.Column('result', sa.Enum('PASS', 'FAIL', 'BLOCK', 'NA', 'NS', name='testresultvalue'), nullable=False),
    sa.Column('actual_result', sa.Text(), nullable=True),
    sa.Column('issue_link', sa.String(length=500), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('executed_by', sa.Integer(), nullable=False),
    sa.Column('executed_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('duration_sec', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['executed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_run_id'], ['test_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_test_results_case_id', 'test_results', ['test_case_id'], unique=False)
    op.create_index(op.f('ix_test_results_id'), 'test_results', ['id'], unique=False)
    op.create_index('ix_test_results_run_id', 'test_results', ['test_run_id'], unique=False)
    op.create_index('ix_test_results_run_result', 'test_results', ['test_run_id', 'result'], unique=False)
    op.create_index('uq_test_results_run_case', 'test_results', ['test_run_id', 'test_case_id'], unique=True)
    op.create_table('attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('test_result_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('filepath', sa.String(length=1000), nullable=False),
    sa.Column('content_type', sa.String(length=200), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['test_result_id'], ['test_results.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_id'), 'attachments', ['id'], unique=False)
    op.create_index(op.f('ix_attachments_test_result_id'), 'attachments', ['test_result_id'], unique=False)
    op.create_table('run_issue_test_cases',
    sa.Column('run_issue_id', sa.Integer(), nullable=False),
    sa.Column('test_case_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['run_issue_id'], ['run_issues.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('run_issue_id', 'test_case_id')
    )
    op.create_index('ix_run_issue_test_cases_case_id', 'run_issue_test_cases', ['test_case_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_run_issue_test_cases_case_id', table_name='run_issue_test_cases')
    op.drop_table('run_issue_test_cases')
    op.drop_index(op.f('ix_attachments_test_result_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_index('uq_test_results_run_case', table_name='test_results')
    op.drop_index('ix_test_results_run_result', table_name='test_results')
    op.drop_index('ix_test_results_run_id', table_name='test_results')
    op.drop_index(op.f('ix_test_results_id'), table_name='test_results')
    op.drop_index('ix_test_results_case_id', table_name='test_results')
    op.drop_table('test_results')
    op.drop_index('uq_run_issues_run_url', table_name='run_issues')
    op.drop_index(op.f('ix_run_issues_id'), table_name='run_issues')
    op.drop_table('run_issues')
    op.drop_index('ix_test_runs_status', table_name='test_runs')
    op.drop_index('ix_test_runs_project_id', table_name='test_runs')
    op.drop_index(op.f('ix_test_runs_id'), table_name='test_runs')
    op.drop_table('test_runs')
    op.drop_index('ix_test_case_history_tc_id', table_name='test_case_history')
    op.drop_index(op.f('ix_test_case_history_id'), table_name='test_case_history')
    op.drop_table('test_case_history')
    op.drop_index(op.f('ix_test_plans_id'), table_name='test_plans')
    op.drop_table('test_plans')
    op.drop_index('uq_test_cases_sheet_no', table_name='test_cases', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('uq_test_cases_project_tc_id', table_name='test_cases', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_test_cases_sheet_name', table_name='test_cases')
    op.drop_index('ix_test_cases_project_id_deleted', table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_id'), table_name='test_cases')
    op.drop_table('test_cases')
    op.drop_index('uq_test_case_sheets_project_name', table_name='test_case_sheets')
    op.drop_index('ix_test_case_sheets_project_id', table_name='test_case_sheets')
    op.drop_index('ix_test_case_sheets_parent_id', table_name='test_case_sheets')
    op.drop_index(op.f('ix_test_case_sheets_id'), table_name='test_case_sheets')
    op.drop_table('test_case_sheets')
    op.drop_index(op.f('ix_saved_filters_id'), table_name='saved_filters')
    op.drop_table('saved_filters')
    op.drop_index('ix_project_members_project_user', table_name='project_members')
    op.drop_index(op.f('ix_project_members_id'), table_name='project_members')
    op.drop_table('project_members')
    op.drop_index(op.f('ix_custom_field_defs_id'), table_name='custom_field_defs')
    op.drop_table('custom_field_defs')
    op.drop_index(op.f('ix_projects_id'), table_name='projects')
    op.drop_table('projects')
    op.drop_index('ix_api_keys_user_id', table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_index('ix_account_requests_status_created', table_name='account_requests')
    op.drop_index(op.f('ix_account_requests_id'), table_name='account_requests')
    op.drop_table('account_requests')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    # 테이블을 지워도 PostgreSQL 의 enum 타입은 남는다. 다시 upgrade 할 때 충돌한다.
    bind = op.get_bind()
    for name in ("userrole", "accountrequesttype", "accountrequeststatus",
                 "projectrole", "testrunstatus", "testresultvalue"):
        sa.Enum(name=name).drop(bind, checkfirst=True)
