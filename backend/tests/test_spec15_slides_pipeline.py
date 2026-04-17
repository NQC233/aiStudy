import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Spec15SlidesPipelineTests(unittest.TestCase):
    def test_services_package_exports_new_slide_pipeline_surface(self) -> None:
        import app.services as services

        self.assertTrue(callable(services.build_asset_slide_analysis_pack))
        self.assertTrue(callable(services.build_visual_asset_cards))
        self.assertTrue(callable(services.build_presentation_plan))
        self.assertTrue(callable(services.build_scene_specs))
        self.assertTrue(callable(services.render_slide_page))
        self.assertTrue(callable(services.build_runtime_bundle))

    def test_services_package_does_not_export_legacy_slide_pipeline_surface(self) -> None:
        import app.services as services

        legacy_exports = [
            "enqueue_asset_lesson_plan_rebuild",
            "get_asset_lesson_plan",
            "run_asset_lesson_plan_pipeline",
            "ensure_asset_slides_schema_up_to_date",
            "run_asset_slides_dsl_pipeline",
        ]

        for export_name in legacy_exports:
            self.assertFalse(hasattr(services, export_name), export_name)


if __name__ == "__main__":
    unittest.main()
