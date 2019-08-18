import textwrap

import pytest
import responses

from sphinxcontrib.openapi import renderer


def textify(generator):
    return "\n".join(generator)


@pytest.fixture(scope="function")
def testrenderer():
    return renderer.HttpDomainRenderer("commonmark")


@pytest.mark.parametrize(
    ["media_type"],
    [
        pytest.param(
            {
                "application/json": {
                    "examples": {"test": {"value": {"foo": "bar", "baz": 42}}}
                }
            },
            id="examples",
        ),
        pytest.param(
            {"application/json": {"example": {"foo": "bar", "baz": 42}}}, id="example",
        ),
        pytest.param(
            {"application/json": {"schema": {"example": {"foo": "bar", "baz": 42}}}},
            id="schema/example",
        ),
        pytest.param(
            {
                "application/json": {
                    "examples": {
                        "test": {
                            "value": textwrap.dedent(
                                """\
                                {
                                  "foo": "bar",
                                  "baz": 42
                                }
                                """
                            )
                        }
                    }
                }
            },
            id="examples::str",
        ),
        pytest.param(
            {
                "application/json": {
                    "example": textwrap.dedent(
                        """\
                        {
                          "foo": "bar",
                          "baz": 42
                        }
                        """
                    )
                }
            },
            id="example::str",
        ),
        pytest.param(
            {
                "application/json": {
                    "schema": {
                        "example": textwrap.dedent(
                            """\
                            {
                              "foo": "bar",
                              "baz": 42
                            }
                            """
                        )
                    }
                }
            },
            id="schema/example::str",
        ),
        pytest.param(
            {
                "application/json": {
                    "schema": {"example": {"foobar": "bazinga"}},
                    "example": {"foo": "bar", "baz": 42},
                }
            },
            id="example-beats-schema/example",
        ),
        pytest.param(
            {
                "application/json": {
                    "schema": {"example": {"foobar": "bazinga"}},
                    "examples": {"test": {"value": {"foo": "bar", "baz": 42}}},
                }
            },
            id="examples-beats-schema/example",
        ),
    ],
)
def test_render_content_example(testrenderer, media_type):
    """Path response's example is rendered."""

    markup = textify(testrenderer.render_content(media_type))
    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: application/json

           {
             "foo": "bar",
             "baz": 42
           }
        """.rstrip()
    )


def test_render_content_example_1st_from_examples(testrenderer):
    """Path response's first example is rendered."""

    markup = textify(
        testrenderer.render_content(
            {
                "application/json": {
                    "examples": {
                        "foo": {"value": {"foo": "bar", "baz": 42}},
                        "bar": {"value": {"foobar": "bazinga"}},
                    }
                }
            }
        )
    )
    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: application/json

           {
             "foo": "bar",
             "baz": 42
           }
        """.rstrip()
    )


def test_render_content_example_1st_from_media_type(testrenderer):
    """Path response's example from first media type is rendered."""

    markup = textify(
        testrenderer.render_content(
            {
                "text/plain": {"example": 'foo = "bar"\nbaz = 42'},
                "application/json": {"schema": {"type": "object"}},
            }
        )
    )

    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: text/plain

           foo = "bar"
           baz = 42
        """.rstrip()
    )


def test_render_content_example_preference(testrenderer):
    """Path response's example from preferred media type is rendered."""

    testrenderer = renderer.HttpDomainRenderer(
        "commonmark", response_example_preference=["text/plain"]
    )

    markup = textify(
        testrenderer.render_content(
            {
                "application/json": {"example": {"foo": "bar", "baz": 42}},
                "text/plain": {"example": 'foo = "bar"\nbaz = 42'},
            }
        )
    )

    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: text/plain

           foo = "bar"
           baz = 42
        """.rstrip()
    )


def test_render_content_example_preference_complex(testrenderer):
    """Path response's example from preferred media type is rendered."""

    testrenderer = renderer.HttpDomainRenderer(
        "commonmark", response_example_preference=["application/json", "text/plain"]
    )

    markup = textify(
        testrenderer.render_content(
            {
                "text/csv": {"example": "foo,baz\nbar,42"},
                "text/plain": {"example": 'foo = "bar"\nbaz = 42'},
                "application/json": {"schema": {"type": "object"}},
            }
        )
    )

    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: text/plain

           foo = "bar"
           baz = 42
        """.rstrip()
    )


@responses.activate
def test_render_content_example_external(testrenderer):
    """Path response's example can be retrieved from external location."""

    responses.add(
        responses.GET,
        "https://example.com/json/examples/test.json",
        json={"foo": "bar", "baz": 42},
        status=200,
    )

    markup = textify(
        testrenderer.render_content(
            {
                "application/json": {
                    "examples": {
                        "test": {
                            "externalValue": "https://example.com/json/examples/test.json"
                        }
                    }
                }
            }
        )
    )
    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: application/json

           {"foo": "bar", "baz": 42}
        """.rstrip()
    )


@responses.activate
def test_render_content_example_external_errored_next_example(testrenderer, caplog):
    """Path response's example fallbacks on next when external cannot be retrieved."""

    responses.add(
        responses.GET, "https://example.com/json/examples/test.json", status=404,
    )

    markup = textify(
        testrenderer.render_content(
            {
                "application/json": {
                    "examples": {
                        "test": {
                            "externalValue": "https://example.com/json/examples/test.json"
                        },
                        "fallback": {"value": '{"spam": 42}'},
                    }
                }
            }
        )
    )
    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: application/json

           {"spam": 42}
        """.rstrip()
    )


@responses.activate
def test_render_content_example_external_errored_next_media_type(testrenderer, caplog):
    """Path response's example fallbacks on next when external cannot be retrieved."""

    responses.add(
        responses.GET, "https://example.com/json/examples/test.json", status=404,
    )

    markup = textify(
        testrenderer.render_content(
            {
                "application/json": {
                    "examples": {
                        "test": {
                            "externalValue": "https://example.com/json/examples/test.json"
                        },
                    }
                },
                "text/csv": {"example": "spam,42"},
            }
        )
    )
    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: text/csv

           spam,42
        """.rstrip()
    )


def test_render_content_example_content_type(testrenderer):
    """Path response's example can render something other than application/json."""

    markup = textify(
        testrenderer.render_content(
            {
                "text/csv": {
                    "example": textwrap.dedent(
                        """\
                        foo,baz
                        bar,42
                        """
                    )
                }
            }
        )
    )
    assert markup == textwrap.dedent(
        """\
        .. sourcecode:: http

           Content-Type: text/csv

           foo,baz
           bar,42
        """.rstrip()
    )


def test_render_content_example_noop(testrenderer):
    """Path response's example is not rendered if there's nothing to render."""

    markup = textify(
        testrenderer.render_content(
            {"application/json": {"schema": {"type": "object"}}}
        )
    )

    assert markup == ""
