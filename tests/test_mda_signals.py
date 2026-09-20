#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "normalize_mda_news.py"

spec = importlib.util.spec_from_file_location("normalize_mda_news", MODULE_PATH)
mda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mda)

SOURCE = {
    "id": "mda_business_news",
    "name": "Mississippi Development Authority Business News",
    "platform": "mda_news",
    "type": "economic_development",
    "state": "MS",
}


class MdaSignalTests(unittest.TestCase):
    def normalized(self, title, detail):
        return mda.normalize_project(
            {
                "id": "sample",
                "name": title,
                "detailText": detail,
                "sourceUrl": "https://mississippi.org/news/sample/",
                "source": SOURCE["name"],
                "publishedAt": "September 15, 2026",
                "detailStatus": "fetched",
            },
            SOURCE,
        )

    def test_hitachi(self):
        p = self.normalized(
            "Hitachi Energy bringing its largest transformer manufacturing investment in U.S. to Mississippi",
            "Hitachi Energy is investing $528 million in a new transformer manufacturing "
            "facility in Gallman in Copiah County. The project will create 654 jobs "
            "and includes construction of a new 200,000-square-foot facility.",
        )
        self.assertEqual(p["company"], "Hitachi Energy")
        self.assertEqual(p["county"], "Copiah")
        self.assertEqual(p["city"], "Gallman")
        self.assertEqual(p["investment"], 528_000_000)
        self.assertEqual(p["jobs"], 654)
        self.assertEqual(p["facilitySqFt"], 200_000)
        self.assertEqual(p["lifecycleStage"], "pre_construction")

    def test_general_atomics(self):
        p = self.normalized(
            "General Atomics marks second expansion in four months in Shannon",
            "General Atomics is expanding once again in Shannon, continuing a long "
            "track record of investment in Lee County. The project represents a "
            "corporate investment of $87 million and will create 125 jobs. "
            "The project includes the construction of a new 200,000-square-foot "
            "manufacturing facility.",
        )
        self.assertEqual(p["company"], "General Atomics")
        self.assertEqual(p["county"], "Lee")
        self.assertEqual(p["city"], "Shannon")
        self.assertEqual(p["investment"], 87_000_000)
        self.assertEqual(p["jobs"], 125)

    def test_southwire(self):
        p = self.normalized(
            "Southwire expanding operations in Starkville",
            "The project represents a corporate investment of more than $256 million "
            "and will create 128 jobs. The expansion includes the addition of "
            "approximately 380,000 square feet in Oktibbeha County. "
            "Construction is expected to begin in late 2026.",
        )
        self.assertEqual(p["company"], "Southwire")
        self.assertEqual(p["county"], "Oktibbeha")
        self.assertEqual(p["city"], "Starkville")
        self.assertEqual(p["investment"], 256_000_000)
        self.assertEqual(p["jobs"], 128)
        self.assertEqual(p["facilitySqFt"], 380_000)


    def test_solero_project_investment_not_company_goal(self):
        p = self.normalized(
            "Solero Technologies expanding operations in Water Valley",
            "The project represents a corporate investment of more than $14 million "
            "and will create 86 new jobs. The expansion includes improvements to "
            "electrical systems, HVAC systems, roofing and flooring. As we work to "
            "grow the company into a more than $1 billion enterprise, continued "
            "investment in our Water Valley facility will be essential.",
        )
        self.assertEqual(p["city"], "Water Valley")
        self.assertEqual(p["investment"], 14_000_000)
        self.assertEqual(p["jobs"], 86)

    def test_non_project_news_rejected(self):
        self.assertFalse(
            mda.title_is_project(
                "Mississippi Development Authority accepting applications for "
                "Energy Efficiency and Conservation Block Grant Program"
            )
        )


if __name__ == "__main__":
    unittest.main()
