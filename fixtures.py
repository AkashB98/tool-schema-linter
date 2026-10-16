#!/usr/bin/env python3
"""Fictional sample tool schemas for the (fictional) Helios Home / Helios Cloud
product line. These are invented fixtures for demos and evals -- zero real
data, zero API keys, zero personal data.

- HELIOS_GOOD: a clean, well-written Helios Cloud tool (should lint clean).
- HELIOS_BAD: a sloppy Helios Home tool riddled with contract smells.
"""

from __future__ import annotations

from typing import Any, Dict, List

Tool = Dict[str, Any]

HELIOS_GOOD: Tool = {
    "name": "helios_place_order",
    "description": "Places a product order in the Helios Cloud store. "
                   "Use after confirming the cart with the customer.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Customer identifier, e.g. C-1042. "
                               "Find it via helios_find_customer first.",
                "examples": ["C-1042", "C-8817"],
            },
            "product_sku": {
                "type": "string",
                "description": "SKU of the product to order, e.g. HL-BULB-9W.",
                "examples": ["HL-BULB-9W", "HL-THERM-2"],
            },
            "quantity": {
                "type": "integer",
                "minimum": 1,
                "description": "How many units to order. Must be at least 1.",
                "examples": [2, 5],
            },
            "delivery_speed": {
                "type": "string",
                "enum": ["standard", "express", "overnight"],
                "description": "Delivery speed: standard (5 days), "
                               "express (2 days), or overnight.",
                "examples": ["standard", "express", "overnight"],
            },
            "notes": {
                "type": "string",
                "description": "Free-text note for the warehouse team. "
                               "May be left empty.",
                "examples": ["Leave at the side door."],
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags used for order analytics and routing.",
                "examples": [["gift", "priority"]],
            },
            "shipping_address": {
                "type": "object",
                "additionalProperties": False,
                "description": "Where to ship the order.",
                "properties": {
                    "street": {
                        "type": "string",
                        "description": "Street address line.",
                        "examples": ["410 Meridian Ave"],
                    },
                    "zip": {
                        "type": "string",
                        "pattern": "^[0-9]{5}$",
                        "description": "Five-digit US ZIP code.",
                        "examples": ["75201", "10001"],
                    },
                },
                "required": ["street", "zip"],
                "examples": [{"street": "410 Meridian Ave", "zip": "75201"}],
            },
            "api_token": {
                "type": "string",
                "sensitive": True,
                "description": "Store API token used to authenticate the order.",
                "examples": ["tok_sample_9f2k"],
            },
        },
        "required": ["customer_id", "product_sku", "quantity"],
    },
}

# NOTE: "notes" says "May be left empty." -- that is about the VALUE being
# empty, not a claim the parameter is optional, so REQ-002 must not fire
# (it is not in `required` anyway).

HELIOS_BAD: Tool = {
    "name": "Tool1",
    "description": "",
    "parameters": {
        "type": "object",
        "properties": {
            "q": {
                "type": "string",
                "examples": ["bulbs"],
            },
            "userName": {
                "type": "string",
                "description": "TODO",
                "examples": ["akash"],
            },
            "count": {
                "type": "integer",
                "description": "Number of items.",
                "examples": ["three"],
                "default": 1,
            },
            "mode": {
                "type": "string",
                "enum": ["a", "b", "c"],
                "description": "The mode.",
                "examples": ["a"],
            },
            "optional_thing": {
                "type": "string",
                "description": "This parameter is optional and can be null.",
                "examples": ["x"],
            },
            "nullable_id": {
                "oneOf": [{"type": "string"}, {"type": "null"}],
                "description": "Identifier that may be null.",
                "examples": ["id-1"],
            },
            "blob": {
                "type": "object",
                "description": "A blob of stuff.",
            },
            "ids": {
                "type": "array",
                "description": "List of identifiers.",
                "examples": [[1, 2]],
            },
            "meta": {
                "type": "object",
                "description": "Metadata bag.",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Where it came from.",
                        "examples": ["web"],
                    },
                },
            },
            "choice": {
                "anyOf": [{"type": "string"}, {"type": "integer"}],
                "description": "Pick a string or an integer.",
                "examples": ["seven"],
            },
            "contact": {
                "type": "string",
                "format": "email-address",
                "description": "Contact email address.",
                "examples": ["ops@example.com"],
            },
            "zip_code": {
                "type": "string",
                "pattern": "^[0-9]{5}$",
                "description": "ZIP code.",
            },
            "customer_password": {
                "type": "string",
                "description": "Customer password.",
                "examples": ["hunter2"],
            },
            "delete_all": {
                "type": "boolean",
                "description": "Delete everything.",
                "examples": [True],
            },
            "address_ref": {
                "$ref": "#/defs/address",
                "description": "Address reference.",
            },
            "labels": {
                "type": "object",
                "patternProperties": {"^x-": {"type": "string"}},
                "description": "Custom labels.",
                "examples": [{"x-team": "ops"}],
            },
            "dup_a": {
                "type": "string",
                "description": "Identifier string.",
                "examples": ["a1"],
            },
            "dup_b": {
                "type": "string",
                "description": "Identifier string.",
                "examples": ["b2"],
            },
        },
        "required": ["count", "optional_thing", "nullable_id", "nope"],
    },
}


def all_fixtures() -> List[Tool]:
    return [HELIOS_GOOD, HELIOS_BAD]
