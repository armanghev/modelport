from __future__ import annotations

import getpass
import sys
from typing import Callable, TypeVar

import questionary
from questionary import Choice, Style

T = TypeVar("T")

_SKIP = "__skip__"
_CUSTOM = "__custom__"

# Questionary merges with its default style, which uses orange (#FF9D00) for answers.
# Override those tokens explicitly so the CLI matches a neutral terminal look.
_STYLE = Style(
    [
        ("qmark", "fg:ansibrightblack bold"),
        ("question", "bold"),
        ("answer", "noinherit fg:ansiwhite bold"),
        ("pointer", "fg:ansicyan bold"),
        ("highlighted", "fg:ansicyan bold"),
        ("selected", "fg:ansigreen"),
        ("instruction", "fg:ansibrightblack"),
        ("text", ""),
        ("search_success", "noinherit fg:ansigreen bold"),
        ("search_none", "noinherit fg:ansired bold"),
    ]
)


def _supports_color() -> bool:
    return sys.stdout.isatty() and sys.stderr.isatty()


def _interactive_available() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _bold(text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[1m{text}\033[0m"


def _dim(text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[2m{text}\033[0m"


def _choice_label(value: str, description: str | None) -> str:
    if description and description != value:
        return f"{description} ({value})"
    return description or value


def _unwrap(result: T | None) -> T:
    if result is None:
        raise KeyboardInterrupt()
    return result


def print_banner(title: str, subtitle: str) -> None:
    print()
    print(_bold(title))
    print(_dim(subtitle))
    print()


def print_step(label: str) -> None:
    print(_bold(f"\n{label}"))


def _read_line(label: str, *, secret: bool) -> str:
    prompt = f"{label}: "
    if secret:
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            print("  Warning: could not hide input; typing will be visible.", file=sys.stderr)
            return input(prompt)
    return input(prompt)


def prompt_text(label: str, default: str | None = None, secret: bool = False) -> str:
    if _interactive_available() and not secret:
        result = questionary.text(
            label,
            default=default or "",
            style=_STYLE,
        ).ask()
        value = _unwrap(result).strip()
        if value:
            return value
        if default is not None:
            return default
        while not value:
            print("  Enter a value or press Enter for the default.")
            value = _read_line(label, secret=False).strip()
            if not value and default is not None:
                return default
        return value

    if _interactive_available() and secret:
        result = questionary.password(
            label,
            style=_STYLE,
        ).ask()
        value = _unwrap(result).strip()
        if value:
            return value
        if default is not None:
            return default
        print("  Enter a value or press Enter for the default.")
        return prompt_text(label, default=default, secret=True)

    suffix = f" [{default}]" if default else ""
    prompt_label = f"{label}{suffix}"
    while True:
        raw = _read_line(prompt_label, secret=secret).strip()
        if not raw and default is not None:
            return default
        if raw:
            return raw
        print("  Enter a value or press Enter for the default.")


def _parse_yes_no(raw: str) -> bool | None:
    value = raw.strip().lower()
    if value in {"y", "yes"}:
        return True
    if value in {"n", "no"}:
        return False
    return None


def prompt_yes_no(label: str) -> bool:
    instruction = "y or n required"
    while True:
        if _interactive_available():
            result = questionary.text(
                label,
                validate=lambda text: (
                    True
                    if _parse_yes_no(text) is not None
                    else "Answer y or n."
                ),
                style=_STYLE,
                instruction=instruction,
            ).ask()
            if result is None:
                raise KeyboardInterrupt()
            parsed = _parse_yes_no(result)
        else:
            raw = input(f"{label} (y/n): ").strip()
            parsed = _parse_yes_no(raw)
            if parsed is None:
                print("  Please answer y or n.")
                continue

        if parsed is not None:
            return parsed
        print("  Please answer y or n.")


def _select_kwargs(*, item_count: int) -> dict[str, object]:
    searchable = item_count > 12
    return {
        "style": _STYLE,
        "use_arrow_keys": True,
        "use_jk_keys": not searchable,
        "use_search_filter": searchable,
        "instruction": (
            "type to filter · ↑/↓ navigate · enter select"
            if searchable
            else "↑/↓ navigate · enter select"
        ),
    }


def _select_option_numeric(
    label: str,
    options: list[tuple[str, str]],
    *,
    allow_custom: bool = False,
    custom_label: str = "Type a custom value",
) -> str:
    print_step(label)
    indexed: list[tuple[str, str | None]] = []
    for index, (value, description) in enumerate(options, start=1):
        indexed.append((value, description))
        line = f"  {index}. {description or value}"
        if description and description != value:
            line += _dim(f"  ({value})")
        print(line)

    custom_index: int | None = None
    if allow_custom:
        custom_index = len(indexed) + 1
        print(f"  {custom_index}. {custom_label}")

    while True:
        raw = input("Choose a number: ").strip()
        if not raw.isdigit():
            print("  Enter the list number.")
            continue
        choice = int(raw)
        if 1 <= choice <= len(indexed):
            return indexed[choice - 1][0]
        if allow_custom and custom_index is not None and choice == custom_index:
            return prompt_text("Custom value")
        print("  That number is not on the list.")


def select_option(
    label: str,
    options: list[tuple[str, str]],
    *,
    allow_custom: bool = False,
    custom_label: str = "Type a custom value",
) -> str:
    if not options and not allow_custom:
        raise ValueError(f"No options available for {label}")

    if not _interactive_available():
        return _select_option_numeric(
            label,
            options,
            allow_custom=allow_custom,
            custom_label=custom_label,
        )

    choices: list[Choice | str] = [
        Choice(title=_choice_label(value, description), value=value)
        for value, description in options
    ]
    if allow_custom:
        choices.append(Choice(title=custom_label, value=_CUSTOM))

    result = _unwrap(
        questionary.select(
            label,
            choices=choices,
            **_select_kwargs(item_count=len(choices)),
        ).ask()
    )
    if result == _CUSTOM:
        return prompt_text("Custom value")
    return str(result)


def _select_optional_numeric(
    label: str,
    options: list[tuple[str, str]],
    *,
    skip_label: str = "Skip (keep agent default)",
) -> str | None:
    print_step(label)
    print(f"  0. {skip_label}")
    for index, (value, description) in enumerate(options, start=1):
        line = f"  {index}. {description or value}"
        if description and description != value:
            line += _dim(f"  ({value})")
        print(line)
    custom_index = len(options) + 1
    print(f"  {custom_index}. Type a custom model id")
    while True:
        raw = input("Choose a number: ").strip()
        if raw == "0":
            return None
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
            if choice == custom_index:
                custom = prompt_text("Model id")
                return custom or None
        print("  Enter 0 to skip, a list number, or the custom option number.")


def select_optional(
    label: str,
    options: list[tuple[str, str]],
    *,
    skip_label: str = "Skip (keep agent default)",
) -> str | None:
    if not _interactive_available():
        return _select_optional_numeric(label, options, skip_label=skip_label)

    choices: list[Choice | str] = [Choice(title=skip_label, value=_SKIP)]
    choices.extend(
        Choice(title=_choice_label(value, description), value=value)
        for value, description in options
    )
    choices.append(Choice(title="Type a custom model id", value=_CUSTOM))

    result = _unwrap(
        questionary.select(
            label,
            choices=choices,
            **_select_kwargs(item_count=len(options)),
        ).ask()
    )
    if result == _SKIP:
        return None
    if result == _CUSTOM:
        custom = prompt_text("Model id")
        return custom or None
    return str(result)


def run_if_tty(interactive_runner: Callable[[], T], non_interactive_runner: Callable[[], T], *, is_tty: bool) -> T:
    if is_tty:
        return interactive_runner()
    return non_interactive_runner()
