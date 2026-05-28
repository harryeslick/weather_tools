"""Adapter that generates Typer CLI options from a Pydantic model.

This keeps the Pydantic query models as the single source of truth for parameter
names, types, defaults, validation, and help text. A CLI command decorated with
``@from_pydantic(SomeQuery, ...)`` exposes one CLI option per leaf field of the
model (nested ``BaseModel`` fields are flattened one level), receives the
assembled model as its first positional argument, and keeps any CLI-only
parameters that follow (api key, output path, cache flags, etc.).

Design notes:
- Only one level of nesting is flattened. The current SILO queries nest at most
  one level (``date_range``, ``coordinates``); deeper nesting raises so we hear
  about it instead of silently flattening surprising shapes.
- Enum fields can be narrowed via ``format_choices`` so e.g. the
  ``patched-point`` command only offers data formats, not search formats. The
  narrowing builds a *subset* enum dynamically so ``--help`` shows just the
  allowed values.
- ``field_aliases`` lets a command keep familiar CLI flags (e.g. ``--var`` for
  the model's ``variables`` field) without renaming the model field.
"""

from __future__ import annotations

import enum
import functools
import inspect
import typing
from typing import Annotated, Any, Callable, Iterable, Optional, Union

import typer
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo


def from_pydantic(
    model_cls: type[BaseModel],
    *,
    format_choices: Optional[Iterable[enum.Enum]] = None,
    field_aliases: Optional[dict[str, str]] = None,
    skip: Iterable[str] = (),
    model_param: str = "query",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a Typer command so its CLI options are derived from ``model_cls``.

    Args:
        model_cls: Pydantic query model. Its non-frozen fields become CLI
            options. Nested ``BaseModel`` fields are flattened one level.
        format_choices: Iterable of allowed enum values for the ``format``
            field. When provided, the CLI's ``--format`` option is restricted
            to this subset and a dynamic subset-enum is shown in ``--help``.
        field_aliases: Map of ``field_name → "--cli-flag"``. The wrapped
            function still receives the field under its model name; only the
            user-facing flag changes.
        skip: Field names to exclude from the CLI surface. Useful for fields
            on the model that are only meaningful in *other* commands (e.g.
            ``radius`` and ``name_fragment`` belong to the search command, not
            the downloader command).
        model_param: Name of the parameter on the wrapped function that
            receives the assembled model. Removed from the visible signature
            so Typer never sees it.

    Returns:
        A decorator that rewrites the wrapped function's signature so Typer
        introspects the generated options, and assembles a ``model_cls`` from
        the parsed values before calling the original function.
    """
    field_aliases = dict(field_aliases or {})
    skip_set = set(skip)
    format_choices_set = set(format_choices) if format_choices else None

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        model_params, nested_map = _build_model_params(
            model_cls,
            format_choices=format_choices_set,
            field_aliases=field_aliases,
            skip=skip_set,
        )

        # Take the original function's signature and drop the model-shaped param.
        original_sig = inspect.signature(fn)
        extra_params: list[inspect.Parameter] = []
        for p in original_sig.parameters.values():
            if p.name == model_param:
                continue
            # Force POSITIONAL_OR_KEYWORD so Typer accepts mixed positions.
            extra_params.append(p.replace(kind=inspect.Parameter.POSITIONAL_OR_KEYWORD))

        # New visible signature: derived params, then the CLI-only extras.
        visible_params = list(model_params.values()) + extra_params
        _check_no_duplicate_names(visible_params)
        new_sig = inspect.Signature(parameters=visible_params)

        @functools.wraps(fn)
        def wrapper(**kwargs: Any) -> Any:
            model_field_names = set(model_params.keys())
            model_kwargs: dict[str, Any] = {}
            nested_groups: dict[str, dict[str, Any]] = {}
            extra_kwargs: dict[str, Any] = {}

            for name, value in kwargs.items():
                if name in nested_map:
                    parent, leaf = nested_map[name]
                    nested_groups.setdefault(parent, {})[leaf] = value
                elif name in model_field_names:
                    model_kwargs[name] = value
                else:
                    extra_kwargs[name] = value

            # Reassemble nested models from their flattened groups. ValidationError
            # raised here would otherwise bypass the command body's try/except (the
            # wrapper runs before the wrapped function), so we convert it into a
            # Typer-rendered error here.
            try:
                for parent, group in nested_groups.items():
                    parent_field = model_cls.model_fields[parent]
                    parent_type = _unwrap_optional(parent_field.annotation)
                    if not _is_pydantic_model(parent_type):
                        raise TypeError(
                            f"Field {parent!r} on {model_cls.__name__} was flattened "
                            "but its annotation is not a BaseModel subclass."
                        )
                    model_kwargs[parent] = parent_type(**group)
                assembled = model_cls(**model_kwargs)
            except ValidationError as exc:
                _emit_validation_error(exc)
                raise typer.Exit(1) from exc

            return fn(assembled, **extra_kwargs)

        wrapper.__signature__ = new_sig  # type: ignore[attr-defined]
        wrapper.__annotations__ = {
            p.name: p.annotation
            for p in visible_params
            if p.annotation is not inspect.Parameter.empty
        }
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _emit_validation_error(exc: ValidationError) -> None:
    """Render a Pydantic ValidationError to stderr in the CLI's house style."""
    typer.echo("❌ Validation error:", err=True)
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "?"
        typer.echo(f"   {loc}: {err['msg']}", err=True)


def _build_model_params(
    model_cls: type[BaseModel],
    *,
    format_choices: Optional[set[enum.Enum]],
    field_aliases: dict[str, str],
    skip: set[str],
) -> tuple[dict[str, inspect.Parameter], dict[str, tuple[str, str]]]:
    """Return ``(flat_params, nested_map)`` for a model's CLI surface.

    ``nested_map`` records which flat field names came from which parent
    (e.g. ``"start_date" → ("date_range", "start_date")``) so the wrapper can
    reassemble nested ``BaseModel``s on the way back.
    """
    params: dict[str, inspect.Parameter] = {}
    nested_map: dict[str, tuple[str, str]] = {}

    for name, field in model_cls.model_fields.items():
        if name in skip or field.frozen:
            continue

        unwrapped = _unwrap_optional(field.annotation)

        if _is_pydantic_model(unwrapped):
            # Flatten one level. Deeper nesting is not supported on purpose.
            for nested_name, nested_field in unwrapped.model_fields.items():
                if _is_pydantic_model(_unwrap_optional(nested_field.annotation)):
                    raise TypeError(
                        f"{model_cls.__name__}.{name}.{nested_name} is a nested "
                        "BaseModel; only one level of nesting is supported."
                    )
                params[nested_name] = _build_param(
                    nested_name,
                    nested_field,
                    field_aliases=field_aliases,
                    format_choices=format_choices,
                )
                nested_map[nested_name] = (name, nested_name)
        else:
            params[name] = _build_param(
                name,
                field,
                field_aliases=field_aliases,
                format_choices=format_choices,
            )

    return params, nested_map


def _build_param(
    name: str,
    field: FieldInfo,
    *,
    field_aliases: dict[str, str],
    format_choices: Optional[set[enum.Enum]],
) -> inspect.Parameter:
    """Build a single Typer-compatible ``inspect.Parameter`` from a Pydantic field."""
    leaf_type = _unwrap_optional(field.annotation)

    # Narrow enum fields when format_choices is supplied and applies.
    if (
        format_choices
        and isinstance(leaf_type, type)
        and issubclass(leaf_type, enum.Enum)
        and all(isinstance(c, leaf_type) for c in format_choices)
    ):
        leaf_type = _narrow_enum(leaf_type, format_choices)

    default = _resolve_default(field, leaf_type, format_choices)
    cli_flag = field_aliases.get(name, "--" + name.replace("_", "-"))
    option = typer.Option(cli_flag, help=field.description or "")

    # For Optional[T] fields keep Optional[T] in the annotation so Typer knows
    # the value may be None.
    visible_annotation: Any
    if _is_optional(field.annotation):
        visible_annotation = Optional[leaf_type]
    else:
        visible_annotation = leaf_type

    return inspect.Parameter(
        name=name,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=Annotated[visible_annotation, option],
        default=default,
    )


def _resolve_default(
    field: FieldInfo,
    leaf_type: Any,
    format_choices: Optional[set[enum.Enum]],
) -> Any:
    """Pick a sensible CLI default given the model's default and any narrowing."""
    if field.is_required():
        # Typer treats `...` as "required option"; we keep that semantics so
        # a missing required field produces a Typer error rather than a
        # Pydantic ValidationError deep inside the wrapper.
        return ...
    raw_default = field.get_default(call_default_factory=True)
    if (
        format_choices
        and isinstance(raw_default, enum.Enum)
        and raw_default not in format_choices
        and isinstance(leaf_type, type)
        and issubclass(leaf_type, enum.Enum)
    ):
        # The model's default isn't in the narrowed choices — fall back to the
        # first allowed choice. (e.g. model default CSV is in the data-format
        # subset, so this rarely triggers; it's a guard against future drift.)
        return next(iter(format_choices))
    return raw_default


def _narrow_enum(enum_cls: type[enum.Enum], choices: set[enum.Enum]) -> type[enum.Enum]:
    """Build a string-valued subset enum so Typer's --help shows only ``choices``."""
    # Preserve declaration order from the original enum for predictable help output.
    members = [(member.name, member.value) for member in enum_cls if member in choices]
    return enum.Enum(  # type: ignore[return-value]
        f"{enum_cls.__name__}Subset",
        members,
        type=str,
    )


def _unwrap_optional(anno: Any) -> Any:
    """Strip a single ``Optional[T]`` layer if present."""
    origin = typing.get_origin(anno)
    if origin is Union:
        args = [a for a in typing.get_args(anno) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return anno


def _is_optional(anno: Any) -> bool:
    if typing.get_origin(anno) is Union:
        return type(None) in typing.get_args(anno)
    return False


def _is_pydantic_model(t: Any) -> bool:
    return isinstance(t, type) and issubclass(t, BaseModel)


def _check_no_duplicate_names(params: list[inspect.Parameter]) -> None:
    seen: set[str] = set()
    for p in params:
        if p.name in seen:
            raise ValueError(
                f"Duplicate parameter name {p.name!r} after flattening. "
                "A nested field collides with another field; pass it via `skip` "
                "or rename in the source model."
            )
        seen.add(p.name)
