import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.user import User
from app.services.auth_bootstrap_service import ensure_default_account_and_migrate_legacy_data


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def first(self):
        return self.values[0] if self.values else None

    def all(self):
        return list(self.values)


class _FakeDb:
    def __init__(self, *, users_by_id=None, query_results=None):
        self.users_by_id = users_by_id or {}
        self.query_results = query_results or {}
        self.added = []
        self.flush_count = 0
        self.commit_count = 0

    def get(self, model, primary_key):  # noqa: ANN001
        if model is User:
            return self.users_by_id.get(primary_key)
        return None

    def add(self, obj):  # noqa: ANN001
        self.added.append(obj)
        if isinstance(obj, User):
            self.users_by_id[obj.id] = obj

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1

    def scalars(self, statement):  # noqa: ANN001
        model = statement.column_descriptions[0].get('entity')
        return _ScalarResult(self.query_results.get(model, []))


class AuthBootstrapServiceTests(unittest.TestCase):
    def test_ensure_default_account_is_noop_when_disabled(self) -> None:
        db = _FakeDb()

        result = ensure_default_account_and_migrate_legacy_data(db, enabled=False)

        self.assertFalse(result.created_default_user)
        self.assertEqual(result.migrated_asset_count, 0)
        self.assertEqual(db.commit_count, 0)

    def test_ensure_default_account_creates_login_user_with_password_hash(self) -> None:
        db = _FakeDb(users_by_id={})

        result = ensure_default_account_and_migrate_legacy_data(db, enabled=True)

        self.assertTrue(result.created_default_user)
        self.assertEqual(result.default_user.email, 'demo@paper-learning.local')
        self.assertEqual(result.default_user.display_name, '默认演示账户')
        self.assertEqual(result.default_user.status, 'active')
        self.assertIsNotNone(result.default_user.password_hash)
        self.assertNotEqual(result.default_user.password_hash, 'paper123456')
        self.assertEqual(db.flush_count, 1)
        self.assertEqual(db.commit_count, 1)

    def test_ensure_default_account_backfills_existing_user_password_hash(self) -> None:
        existing_user = SimpleNamespace(
            id='default-demo-user',
            email='demo@paper-learning.local',
            display_name='默认演示账户',
            password_hash=None,
            status='invited',
        )
        db = _FakeDb(users_by_id={'default-demo-user': existing_user})

        result = ensure_default_account_and_migrate_legacy_data(db, enabled=True)

        self.assertFalse(result.created_default_user)
        self.assertEqual(result.default_user.status, 'active')
        self.assertIsNotNone(result.default_user.password_hash)
        self.assertEqual(db.commit_count, 1)

    def test_ensure_default_account_migrates_legacy_owned_records(self) -> None:
        legacy_user = SimpleNamespace(id='local-dev-user')
        legacy_asset_a = SimpleNamespace(id='asset-1', user_id='local-dev-user')
        legacy_asset_b = SimpleNamespace(id='asset-2', user_id='local-dev-user')
        legacy_session = SimpleNamespace(id='session-1', user_id='local-dev-user')
        legacy_anchor = SimpleNamespace(id='anchor-1', user_id='local-dev-user')
        legacy_note = SimpleNamespace(id='note-1', user_id='local-dev-user')
        db = _FakeDb(
            users_by_id={'local-dev-user': legacy_user},
            query_results={
                User: [],
            },
        )
        db.query_results.update({
            __import__('app.models.asset', fromlist=['Asset']).Asset: [legacy_asset_a, legacy_asset_b],
            __import__('app.models.chat_session', fromlist=['ChatSession']).ChatSession: [legacy_session],
            __import__('app.models.anchor', fromlist=['Anchor']).Anchor: [legacy_anchor],
            __import__('app.models.note', fromlist=['Note']).Note: [legacy_note],
        })

        result = ensure_default_account_and_migrate_legacy_data(db, enabled=True)

        self.assertEqual(legacy_asset_a.user_id, result.default_user.id)
        self.assertEqual(legacy_asset_b.user_id, result.default_user.id)
        self.assertEqual(legacy_session.user_id, result.default_user.id)
        self.assertEqual(legacy_anchor.user_id, result.default_user.id)
        self.assertEqual(legacy_note.user_id, result.default_user.id)
        self.assertEqual(result.migrated_asset_count, 2)
        self.assertEqual(result.migrated_chat_session_count, 1)
        self.assertEqual(result.migrated_anchor_count, 1)
        self.assertEqual(result.migrated_note_count, 1)
        self.assertEqual(db.commit_count, 1)


if __name__ == '__main__':
    unittest.main()
