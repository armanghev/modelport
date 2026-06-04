from __future__ import annotations

import sys
from typing import Callable, TypeVar

T = TypeVar("T")


def _supports_color() -> bool:
    return sys.stdout.isatty() and sys.stderr.isatty()


def _bold(text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[1m{text}\033[0m"


def _dim(text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[2m{text}\033[0m"


def print_banner(title: str, subtitle: str) -> None:
    print()
    print(_bold(title))
    print(_dim(subtitle))
    print()


def print_step(label: str) -> None:
    print(_bold(f"\n{label}"))


def prompt_text(label: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{label}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        if raw:
            if secret:
                return raw
            return raw
        print("  Enter a value or press Enter for the default.")


def prompt_yes_no(label: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} ({hint}): ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("  Please answer y or n.")


def select_option(
    label: str,
    options: list[tuple[str, str]],
    *,
    allow_custom: bool = False,
    custom_label: str = "Type a custom value",
) -> str:
    if not options and not allow_custom:
        raise ValueError(f"No options available for {label}")

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


def select_optional(
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


def run_if_tty(interactive_runner: Callable[[], T], non_interactive_runner: Callable[[], T], *, is_tty: bool) -> T:
    if is_tty:
        return interactive_runner()
    return non_interactive_runner()
