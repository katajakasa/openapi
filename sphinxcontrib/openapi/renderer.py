"""OpenAPI spec renderer."""

import functools
import inspect
import json

import m2r
import requests
import six
from sphinx.util import logging


logger = logging.getLogger(__name__)


def render(spec, markup="commonmark"):
    """The one func to rule them all."""
    nodes = []
    return nodes


missing = object()


def getin(sequence_or_mapping, path, default=missing):
    rv = sequence_or_mapping

    try:
        for part in path:
            rv = rv[part]
    except (IndexError, KeyError, LookupError):
        if default is not missing:
            return default
        raise

    return rv


def indented(generator, indent=3):
    for item in generator:
        if item:
            item = " " * indent + item
        yield item


def _yield_from_generators(generatorfn):
    @functools.wraps(generatorfn)
    def _wrapper(*args, **kwargs):
        for subgenerator in generatorfn(*args, **kwargs):
            if inspect.isgenerator(subgenerator):
                for item in subgenerator:
                    yield item
            else:
                yield subgenerator

    return _wrapper


def _from_restructuredtext_markup(generatorfn):
    pass


def _iterexamples(media_type, example_preference, examples_from_schemas):
    if example_preference:
        order_by = dict(
            ((value, index) for index, value in enumerate(example_preference))
        )
        media_type = sorted(
            media_type.items(), key=lambda item: order_by.get(item[0], float("inf"))
        )
    else:
        media_type = media_type.items()

    for content_type, media_type in media_type:
        # Look for a example in a bunch of possible places. According to
        # OpenAPI v3 spec, `examples` and `example` keys are mutually
        # exlusive, so there's no much difference between their
        # inspection order, while both must take precedence over a
        # schema example.
        if media_type.get("examples", {}):
            for example in media_type["examples"].values():
                if "externalValue" in example:
                    if not example["externalValue"].startswith(("http://", "https://")):
                        logger.warning(
                            "Not supported protocol in 'externalValue': %s",
                            example["externalValue"],
                        )
                        continue

                    try:
                        response = requests.get(example["externalValue"])
                        response.raise_for_status()

                        example["value"] = response.text
                        example.pop("externalValue")
                    except Exception:
                        logger.error(
                            "Cannot retrieve example from: '%s'",
                            example["externalValue"],
                        )
                        continue
                break
            else:
                # If the loop over examples has not been interrupted, we
                # probably didn't find an example to render. In that case,
                # let's try and go next media type.
                continue
        elif media_type.get("example"):
            # Save example from "example" in "examples" compatible format. This
            # allows to treat all returned examples the same way.
            example = {"value": media_type["example"]}
        elif media_type.get("schema", {}).get("example"):
            # Save example from "schema" in "examples" compatible format. This
            # allows to treat all returned examples the same way.
            example = {"value": media_type["schema"]["example"]}
        elif "schema" in media_type and examples_from_schemas:
            # do some dark magic to convert schema to example
            pass
        else:
            continue

        yield content_type, example


class HttpDomainRenderer(object):
    """Render OpenAPI v3 using `sphinxcontrib-httpdomain` extension."""

    # render(...)
    #   render_paths(...)
    #     render_operation(...)
    #       render_parameters(...)
    #         render_parameter(...)
    #       render_responses(...)
    #         render_response(...)

    _markup_converters = {"commonmark": m2r.convert, "restructuredtext": lambda x: x}

    def __init__(
        self,
        markup,
        request_parameters_order=None,
        response_example_preference=None,
        generate_example_from_schema=False,
    ):
        if markup not in self._markup_converters:
            raise ValueError("invalid markup: '%s'" % markup)

        self._convert_markup = self._markup_converters[markup]
        self._request_parameters_order = ["header", "path", "query", "cookie"]
        self._response_example_preference = response_example_preference
        self._generate_example_from_schema = generate_example_from_schema

    @_yield_from_generators
    def render(self, node):
        """Spec render entry point."""
        yield self.render_paths(node)

    @_yield_from_generators
    def render_paths(self, node):
        """Render OAS paths item."""

        for endpoint, pathitem in getin(node, ["paths"], {}).items():
            for method, operation in pathitem.items():
                operation.setdefault("parameters", [])
                parameters = [
                    parameter
                    for parameter in pathitem.get("parameters", [])
                    if (parameter["name"], parameter["in"])
                    not in [
                        (op_parameter["name"], op_parameter["in"])
                        for op_parameter in operation.get("parameters", [])
                    ]
                ]
                operation["parameters"] += parameters

                yield self.render_operation(endpoint, method, operation)
                yield ""

    @_yield_from_generators
    def render_operation(self, endpoint, method, operation):
        """Render OAS operation item."""

        yield ".. http:%s:: %s" % (method, endpoint)

        if operation.get("deprecated"):
            yield "    :deprecated:"

        yield ""

        if operation.get("summary"):
            yield "    **%s**" % operation["summary"]
            yield ""

        if operation.get("description"):
            yield indented(
                self._convert_markup(operation["description"]).strip().splitlines()
            )
            yield ""

        yield indented(self.render_parameters(operation.get("parameters", [])))
        yield indented(self.render_responses(operation["responses"]))

    @_yield_from_generators
    def render_parameters(self, parameters):
        """Render OAS operation's parameters."""

        for parameter in sorted(
            parameters,
            key=lambda p: self._request_parameters_order.index(p["in"].lower()),
        ):
            yield self.render_parameter(parameter)

    @_yield_from_generators
    def render_parameter(self, parameter):
        """Render OAS operation's parameter."""

        kinds = {"path": "param", "query": "queryparam", "header": "reqheader"}
        markers = []
        schema = parameter.get("schema", {})

        if parameter["in"] not in kinds:
            logger.warning(
                "OpenAPI spec contains parameter '%s' (in: '%s') that cannot "
                "be rendererd.",
                parameter["name"],
                parameter["in"],
            )
            return

        if schema.get("type"):
            type_ = schema.get("type")
            if schema.get("format"):
                type_ = "%s:%s" % (type_, schema.get("format"))
            markers.append(type_)

        if parameter.get("required"):
            markers.append("required")

        if parameter.get("deprecated"):
            markers.append("deprecated")

        yield ":%s %s:" % (kinds[parameter["in"]], parameter["name"])

        if parameter.get("description"):
            yield indented(
                self._convert_markup(parameter["description"]).strip().splitlines()
            )

        if markers:
            yield ":%s %s: %s" % (
                "%stype" % kinds[parameter["in"]],
                parameter["name"],
                ", ".join(markers),
            )

    @_yield_from_generators
    def render_responses(self, responses):
        """Render OAS operation's responses."""

        for status_code, response in responses.items():
            yield self.render_response(status_code, response)

    @_yield_from_generators
    def render_response(self, status_code, response):
        """Render OAS operation's response."""

        yield ":statuscode %s:" % status_code
        yield indented(
            self._convert_markup(response["description"]).strip().splitlines()
        )

        if "content" in response:
            yield ""
            yield indented(self.render_content(response["content"]))

        # yield ""
        # yield ":responseheader X-Trace-Id: What the Fuck?"

    @_yield_from_generators
    def render_content(self, media_type):
        # OpenAPI 3.0 spec may contain more than one response media type, and
        # each media type may contain more than one example. Rendering all
        # invariants normally is not an option because the result will be hard
        # to read and follow. The best option we can go with at this moment is
        # to render first found example of either response media type. Users
        # should control what to render by putting recommended example first in
        # the list.
        content_type, example = next(
            _iterexamples(
                media_type,
                self._response_example_preference,
                self._generate_example_from_schema,
            ),
            (None, None),
        )

        if example:
            example = example["value"]

            if not isinstance(example, six.string_types):
                example = json.dumps(example, indent=2)

            yield ".. sourcecode:: http"
            yield ""
            yield "   Content-Type: %s" % content_type
            yield ""
            yield indented(example.splitlines())
