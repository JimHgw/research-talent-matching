"""Validate directly against the checked-in OpenAPI 3.1 request models."""

import json

from flask import request
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .paths import ROOT

CONTRACT = json.loads((ROOT / "docs/api/openapi.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource(
    "urn:h18:contract", Resource.from_contents(CONTRACT, default_specification=DRAFT202012)
)


class ApiError(Exception):
    def __init__(self, status, code, message, *, fields=None, revision=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.fields, self.revision = fields or [], revision


def invalid(field, message):
    raise ApiError(422, "VALIDATION_ERROR", "Check the submitted fields.",
                   fields=[{"field": field, "message": message}])


def validator(name):
    return Draft202012Validator({"$ref": f"urn:h18:contract#/components/schemas/{name}"},
                                registry=REGISTRY, format_checker=FormatChecker())


def _field_path(parts):
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += ("." if path else "") + part
    return path or "$"


def validate(name, value):
    errors = list(validator(name).iter_errors(value))
    if errors:
        # Do not echo submitted values (especially passwords) into errors or logs.
        raise ApiError(422, "VALIDATION_ERROR", "Check the submitted fields.", fields=[
            {"field": _field_path(error.absolute_path),
             "message": f"Does not satisfy {error.validator}."} for error in errors[:20]
        ])
    try:
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        invalid("$", "Use valid Unicode characters.")
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(_):
    raise ValueError("Non-finite JSON number")


def body(name):
    if request.mimetype != "application/json":
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Use application/json.")
    try:
        value = json.loads(request.get_data().decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ApiError(400, "BAD_REQUEST", "The request body must be valid JSON.") from None
    return validate(name, value)
