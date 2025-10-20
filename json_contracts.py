"""JSON contracts for x_make_github_clones_x."""

from __future__ import annotations

_NAMES_SCHEMA: dict[str, object] = {
    "oneOf": [
        {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "uniqueItems": True,
        },
        {"type": "string", "minLength": 1},
    ]
}

_PARAMETERS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "username": {"type": "string", "minLength": 1},
        "target_dir": {"type": "string", "minLength": 1},
        "shallow": {"type": "boolean"},
        "include_forks": {"type": "boolean"},
        "force_reclone": {"type": "boolean"},
        "names": _NAMES_SCHEMA,
        "token": {"type": ["string", "null"], "minLength": 1},
        "include_private": {"type": "boolean"},
        "allow_token_clone": {"type": "boolean"},
    },
    "additionalProperties": False,
    "anyOf": [
        {"required": ["username"]},
        {"required": ["token"]},
    ],
}

_INVOCATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "username": {"type": ["string", "null"], "minLength": 1},
        "target_dir": {"type": "string", "minLength": 1},
        "shallow": {"type": "boolean"},
        "include_forks": {"type": "boolean"},
        "force_reclone": {"type": "boolean"},
        "names_filter": {
            "type": ["array", "null"],
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "uniqueItems": True,
        },
        "include_private": {"type": "boolean"},
        "token_provided": {"type": "boolean"},
        "allow_token_clone": {"type": "boolean"},
    },
    "required": [
        "username",
        "target_dir",
        "shallow",
        "include_forks",
        "force_reclone",
        "names_filter",
        "include_private",
        "token_provided",
        "allow_token_clone",
    ],
    "additionalProperties": False,
}

_SUMMARY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "total_repos": {"type": "integer", "minimum": 0},
        "successful": {"type": "integer", "minimum": 0},
        "missing_clone_url": {"type": "integer", "minimum": 0},
        "failed_updates": {"type": "integer", "minimum": 0},
        "fetch_error": {"type": ["string", "null"]},
        "missing_repos": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "uniqueItems": True,
        },
        "failed_repos": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "uniqueItems": True,
        },
    },
    "required": [
        "total_repos",
        "successful",
        "missing_clone_url",
        "failed_updates",
        "fetch_error",
    ],
    "additionalProperties": False,
}

_REPO_ENTRY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "full_name": {"type": "string", "minLength": 1},
        "target_path": {"type": "string", "minLength": 1},
        "source_https": {"type": ["string", "null"], "minLength": 1},
        "source_ssh": {"type": ["string", "null"], "minLength": 1},
        "used_token_clone": {"type": "boolean"},
        "status": {
            "type": "string",
            "enum": ["updated", "failed", "missing_clone_url", "skipped"],
        },
        "duration_seconds": {"type": "number", "minimum": 0},
        "error": {"type": "string", "minLength": 1},
    },
    "required": [
        "name",
        "full_name",
        "target_path",
        "source_https",
        "source_ssh",
        "used_token_clone",
        "status",
        "duration_seconds",
    ],
    "additionalProperties": False,
}

OUTPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_github_clones_x output",
    "type": "object",
    "properties": {
        "status": {"const": "success"},
        "schema_version": {"const": "x_make_github_clones_x.run/1.0"},
        "run_id": {
            "type": "string",
            "pattern": "^[a-f0-9]{32}$",
        },
        "started_at": {"type": "string", "format": "date-time"},
        "completed_at": {"type": "string", "format": "date-time"},
        "duration_seconds": {"type": "number", "minimum": 0},
        "invocation": _INVOCATION_SCHEMA,
        "summary": _SUMMARY_SCHEMA,
        "repos": {
            "type": "array",
            "items": _REPO_ENTRY_SCHEMA,
        },
        "exit_code": {"type": "integer"},
    },
    "required": [
        "status",
        "schema_version",
        "run_id",
        "started_at",
        "completed_at",
        "duration_seconds",
        "invocation",
        "summary",
        "repos",
        "exit_code",
    ],
    "additionalProperties": False,
}

INPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_github_clones_x input",
    "type": "object",
    "properties": {
        "command": {"const": "x_make_github_clones_x"},
        "parameters": _PARAMETERS_SCHEMA,
    },
    "required": ["command", "parameters"],
    "additionalProperties": False,
}

ERROR_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_github_clones_x error",
    "type": "object",
    "properties": {
        "status": {"const": "failure"},
        "message": {"type": "string", "minLength": 1},
        "details": {"type": "object"},
    },
    "required": ["status", "message"],
    "additionalProperties": True,
}

__all__ = ["ERROR_SCHEMA", "INPUT_SCHEMA", "OUTPUT_SCHEMA"]
