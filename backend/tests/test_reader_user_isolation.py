import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.reader import AssetParsedDocumentResponse, AssetPdfDescriptor
from app.services.asset_reader_service import get_asset_parsed_document, get_asset_pdf_descriptor


class ReaderUserIsolationTests(unittest.TestCase):
    def test_get_asset_pdf_descriptor_requires_current_user_asset(self) -> None:
        db = SimpleNamespace()

        with patch("app.services.asset_reader_service.require_user_asset", side_effect=HTTPException(status_code=404, detail="未找到对应的学习资产。")):
            with self.assertRaises(HTTPException) as ctx:
                get_asset_pdf_descriptor(db, "asset-1", "user-a")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_asset_parsed_document_requires_current_user_asset(self) -> None:
        db = SimpleNamespace()

        with patch("app.services.asset_reader_service.require_user_asset", side_effect=HTTPException(status_code=404, detail="未找到对应的学习资产。")):
            with self.assertRaises(HTTPException) as ctx:
                get_asset_parsed_document(db, "asset-1", "user-a")

        self.assertEqual(ctx.exception.status_code, 404)
