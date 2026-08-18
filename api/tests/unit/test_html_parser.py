from api.infrastructure.parsing.html_parser import HtmlParser


def test_strips_scripts_and_styles():
    html = b"""
    <html><body>
      <script>alert('x')</script>
      <style>.a { color: red; }</style>
      <p>Real content here.</p>
    </body></html>
    """
    text = HtmlParser().parse(html)
    assert "alert" not in text
    assert "color: red" not in text
    assert "Real content here." in text


def test_extracts_visible_text_only():
    html = b"<html><body><h1>Title</h1><p>Paragraph one.</p><p>Paragraph two.</p></body></html>"
    text = HtmlParser().parse(html)
    assert "Title" in text
    assert "Paragraph one." in text
    assert "Paragraph two." in text


def test_empty_body_returns_empty_string():
    html = b"<html><body></body></html>"
    assert HtmlParser().parse(html) == ""
