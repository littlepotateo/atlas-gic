import os
from pathlib import Path

import pytest

from atlas.envfile import EnvFileError, load_env_files, parse_env_text


def test_parses_plain_quoted_export_comments_and_blank_lines():
    text = "\n# a comment\nexport A=1\nB = 'two words'\nC=\"x\"  # trailing\nD=plain # note\n bogus line\n"
    assert parse_env_text(text) == {"A": "1", "B": "two words", "C": "x", "D": "plain"}


def test_default_files_fill_unset_variables_and_exported_values_win(tmp_path):
    cwd = tmp_path / "repo"
    home = tmp_path / "home"
    (cwd).mkdir()
    (home / ".config" / "atlas").mkdir(parents=True)
    (cwd / ".env").write_text("ANTHROPIC_API_KEY=from-cwd\nFRED_API_KEY=fred-cwd\n", encoding="utf-8")
    (home / ".config" / "atlas" / ".env").write_text("FRED_API_KEY=fred-home\nOTHER=home\n", encoding="utf-8")
    env = {"ANTHROPIC_API_KEY": "exported"}
    loaded = load_env_files(environ=env, home=home, cwd=cwd)
    assert env["ANTHROPIC_API_KEY"] == "exported"       # process environment wins
    assert env["FRED_API_KEY"] == "fred-cwd"            # cwd file is read before the home file
    assert env["OTHER"] == "home"
    assert sorted(loaded) == ["FRED_API_KEY", "OTHER"]  # names only, never values


def test_empty_exported_value_is_filled_from_file(tmp_path):
    (tmp_path / ".env").write_text("FRED_API_KEY=abc\n", encoding="utf-8")
    env = {"FRED_API_KEY": "   "}
    load_env_files(environ=env, home=tmp_path / "nohome", cwd=tmp_path)
    assert env["FRED_API_KEY"] == "abc"


def test_missing_default_files_are_silently_skipped(tmp_path):
    env = {}
    assert load_env_files(environ=env, home=tmp_path, cwd=tmp_path) == []
    assert env == {}


def test_explicit_env_file_is_used_alone(tmp_path):
    f = tmp_path / "keys.env"
    f.write_text("ANTHROPIC_API_KEY=explicit\n", encoding="utf-8")
    (tmp_path / ".env").write_text("FRED_API_KEY=should-not-load\n", encoding="utf-8")
    env = {"ATLAS_ENV_FILE": str(f)}
    load_env_files(environ=env, home=tmp_path, cwd=tmp_path)
    assert env["ANTHROPIC_API_KEY"] == "explicit"
    assert "FRED_API_KEY" not in env


def test_explicit_missing_file_is_an_error(tmp_path):
    with pytest.raises(EnvFileError, match="does not exist"):
        load_env_files(environ={"ATLAS_ENV_FILE": str(tmp_path / "nope.env")}, home=tmp_path, cwd=tmp_path)


def test_values_are_never_printed(tmp_path, capsys):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=supersecretvalue\n", encoding="utf-8")
    load_env_files(environ={}, home=tmp_path / "nohome", cwd=tmp_path)
    out = capsys.readouterr()
    assert "supersecretvalue" not in out.out + out.err
