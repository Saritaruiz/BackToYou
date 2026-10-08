"""RF29 typography contracts, alongside the RNF27 layout conventions."""

import re

from django.conf import settings
from django.test import SimpleTestCase


class TypographyTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = (settings.BASE_DIR / "static/css/styles.css").read_text(encoding="utf-8")
        cls.base = (settings.BASE_DIR / "templates/base.html").read_text(encoding="utf-8")

    def rule(self, selector):
        return re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", self.css).group(1)

    def test_shared_template_loads_both_fonts_with_swap(self):
        self.assertIn("https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800", self.base)
        self.assertIn("family=DM+Serif+Display&amp;display=swap", self.base)
        for template in (settings.BASE_DIR / "templates").glob("*.html"):
            if template.name != "base.html":
                self.assertIn('extends "base.html"', template.read_text(encoding="utf-8"))

    def test_heading_and_body_families_have_correct_fallbacks(self):
        self.assertIn('--font-heading: "DM Serif Display", Georgia, "Times New Roman", serif;', self.css)
        self.assertIn('--font-body: "DM Sans", Arial, Helvetica, sans-serif;', self.css)
        self.assertIn("font-family: var(--font-body);", self.rule("body"))
        self.assertIn("font-family: var(--font-heading);", self.rule("h1, h2, h3, h4, h5, h6, .page-title"))
        for selector in ("button, input, select, textarea, .button", "label", "input,\nselect,\ntextarea"):
            self.assertIn("font-family: var(--font-body);", self.rule(selector))

    def test_desktop_scale_and_weights(self):
        root = self.rule(":root")
        for name, size in (("h1", 48), ("h2", 36), ("h3", 28), ("h4", 22), ("body", 16), ("small", 14)):
            self.assertIn(f"--fs-{name}: {size}px;", root)
        self.assertIn("--fw-regular: 400;", root)
        self.assertIn("--fw-semibold: 600;", root)
        for selector, token in (("h1, .page-title", "h1"), ("h2", "h2"), ("h3", "h3"), ("h4, h5, h6", "h4"), ("body", "body"), ("small", "small")):
            self.assertIn(f"font-size: var(--fs-{token});", self.rule(selector))
        button = self.rule(".site-nav a,\n.nav-logout button,\n.button,\nbutton")
        for rule in (button, self.rule("label")):
            self.assertIn("font-size: var(--fs-small);", rule)
            self.assertIn("font-weight: var(--fw-semibold);", rule)
        self.assertNotRegex(self.css, r"\.stats-summary h2\s*\{")

    def test_mobile_scale_and_long_text_wrapping(self):
        mobile = re.search(r"@media \(max-width: 600px\)\s*\{\s*:root\s*\{([^}]*)", self.css).group(1)
        for level, size in enumerate((36, 30, 24, 20), start=1):
            self.assertIn(f"--fs-h{level}: {size}px;", mobile)
        self.assertNotIn("--fs-body:", mobile)
        self.assertNotIn("--fs-small:", mobile)
        self.assertIn("overflow-wrap: anywhere;", self.rule("body"))
        self.assertIn("white-space: normal;", self.rule(".filter-form > .button,\n.filter-form > button"))

    def test_readable_prose_and_non_color_heading_hierarchy(self):
        self.assertIn("max-width: 75ch;", self.rule(".hero p,\np.lead,\n.detail-card > p.description"))
        self.assertEqual(self.css.count("max-width: 75ch;"), 1)
        self.assertIn("line-height: 1.5;", self.rule("body"))
        headings = self.rule("h1, h2, h3, h4, h5, h6, .page-title")
        self.assertIn("line-height: 1.25;", headings)
        self.assertIn("margin-block: 0 12px;", headings)
        self.assertIn("font-weight: var(--fw-regular);", headings)
