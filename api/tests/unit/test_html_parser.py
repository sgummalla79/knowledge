from api.infrastructure.parsing.html_parser import HtmlParser


def _write(tmp_path, html: bytes, name: str = "page.html"):
    path = tmp_path / name
    path.write_bytes(html)
    return path


def test_strips_scripts_and_styles(tmp_path):
    html = b"""
    <html><body>
      <script>alert('x')</script>
      <style>.a { color: red; }</style>
      <p>Real content here.</p>
    </body></html>
    """
    path = _write(tmp_path, html)
    text = HtmlParser().parse(path)
    assert "alert" not in text
    assert "color: red" not in text
    assert "Real content here." in text


def test_extracts_visible_text_only(tmp_path):
    html = b"<html><body><h1>Title</h1><p>Paragraph one.</p><p>Paragraph two.</p></body></html>"
    path = _write(tmp_path, html)
    text = HtmlParser().parse(path)
    assert "Title" in text
    assert "Paragraph one." in text
    assert "Paragraph two." in text


def test_empty_body_returns_empty_string(tmp_path):
    html = b"<html><body></body></html>"
    path = _write(tmp_path, html)
    assert HtmlParser().parse(path) == ""
