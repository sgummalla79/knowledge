from app.infrastructure.web.link_extractor import extract_in_scope_links, seed_scope_prefix


def test_seed_scope_prefix_is_seed_directory():
    seed = "https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm"
    assert seed_scope_prefix(seed) == "/docs/atlas.en-us.api_asynch.meta/api_asynch/"


def test_resolves_relative_links_within_scope():
    html = b"""
    <a href="asynch_api_completion_events.htm">Completion Events</a>
    <a href="/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm">Intro</a>
    """
    links = extract_in_scope_links(
        html,
        base_url="https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm",
        scope_prefix="/docs/atlas.en-us.api_asynch.meta/api_asynch/",
    )
    assert (
        "https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_completion_events.htm"
        in links
    )
    assert (
        "https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm" in links
    )


def test_drops_links_outside_scope_prefix():
    html = b'<a href="https://developer.salesforce.com/docs/other-book/page.htm">Other</a>'
    links = extract_in_scope_links(
        html,
        base_url="https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm",
        scope_prefix="/docs/atlas.en-us.api_asynch.meta/api_asynch/",
    )
    assert links == []


def test_drops_off_host_links():
    html = b'<a href="https://other-site.com/docs/atlas.en-us.api_asynch.meta/api_asynch/page.htm">Off host</a>'
    links = extract_in_scope_links(
        html,
        base_url="https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm",
        scope_prefix="/docs/atlas.en-us.api_asynch.meta/api_asynch/",
    )
    assert links == []


def test_dedupes_links_that_differ_only_by_fragment():
    html = b"""
    <a href="page.htm#section-a">A</a>
    <a href="page.htm#section-b">B</a>
    """
    links = extract_in_scope_links(
        html,
        base_url="https://example.com/docs/book/",
        scope_prefix="/docs/book/",
    )
    assert links == ["https://example.com/docs/book/page.htm"]
