import textwrap
import pytest

from sphinxcontrib.openapi import renderer


def textify(generator):
    return "\n".join(generator)


@pytest.fixture(scope="function")
def testrenderer():
    return renderer.HttpDomainRenderer("commonmark")


@pytest.mark.parametrize(
    ["statuscode"], [pytest.param("200"), pytest.param("4XX"), pytest.param("default")]
)
def test_render_response_status_code(testrenderer, statuscode):
    """Path response's definition is rendered for any status code."""

    markup = textify(
        testrenderer.render_response(statuscode, {"description": "An evidence."})
    )
    assert markup == textwrap.dedent(
        """\
        :statuscode %s:
           An evidence.
        """.rstrip()
        % statuscode
    )


def test_render_response_minimum(testrenderer):
    """Minimum path response's definition is rendered."""

    markup = textify(testrenderer.render_response(200, {"description": "An evidence."}))
    assert markup == textwrap.dedent(
        """\
        :statuscode 200:
           An evidence.
        """.rstrip()
    )


def test_render_response_description_commonmark():
    """Path response's 'description' can be in commonmark."""

    testrenderer = renderer.HttpDomainRenderer("commonmark")
    markup = textify(
        testrenderer.render_response(
            200, {"description": "An __evidence__ that matches\nthe `query`."}
        )
    )
    assert markup == textwrap.dedent(
        """\
        :statuscode 200:
           An **evidence** that matches
           the ``query``.
        """.rstrip()
    )


def test_render_response_description_restructuredtext():
    """Path response's 'description' can be in restructuredtext."""

    testrenderer = renderer.HttpDomainRenderer("restructuredtext")
    markup = textify(
        testrenderer.render_response(
            200, {"description": "An __evidence__ that matches\nthe `query`."}
        )
    )
    assert markup == textwrap.dedent(
        """\
        :statuscode 200:
           An __evidence__ that matches
           the `query`.
        """.rstrip()
    )


def test_render_response_content(testrenderer):
    """"""

    markup = textify(
        testrenderer.render_response(
            200,
            {
                "description": "An evidence.",
                "content": {"application/json": {"example": {"foo": "bar", "baz": 42}}},
            },
        )
    )
    exp = textwrap.dedent(
        """\
        :statuscode 200:
           An evidence.

           .. sourcecode:: http

              Content-Type: application/json

              {
                "foo": "bar",
                "baz": 42
              }
        """.rstrip()
    )
    assert markup == exp
