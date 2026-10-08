"""Strict, reusable query pagination using the contract's limits and defaults."""

import re

from flask import request
from jsonschema import Draft202012Validator

from .validation import CONTRACT, invalid


def pagination():
    values = []
    for parameter in ("Page", "PageSize"):
        definition = CONTRACT["components"]["parameters"][parameter]
        name, schema = definition["name"], definition["schema"]
        raw = request.args.getlist(name)
        if not raw:
            values.append(schema["default"])
            continue
        if len(raw) != 1 or not re.fullmatch(r"[0-9]+", raw[0]):
            invalid(name, "Use one positive integer.")
        try:
            value = int(raw[0])
        except ValueError:
            invalid(name, "Use a valid positive integer.")
        if not Draft202012Validator(schema).is_valid(value):
            invalid(name, "The page value is outside the allowed range.")
        values.append(value)
    return tuple(values)
