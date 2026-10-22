"""Extraction contract tests: exactly one fenced bash block (DESIGN.md)."""

import pytest

from shell_grpo.evaluate import extract_script


def test_single_bash_block_extracts():
    text = (
        "Here is my script:\n\n```bash\n#!/bin/bash\necho hi\n```\n\n"
        "It counts the files."
    )
    result = extract_script(text)
    assert result.ok
    assert result.script == "#!/bin/bash\necho hi\n"
    assert result.n_blocks == 1


def test_missing_block_rejected():
    assert not extract_script("I would write a script that counts files.").ok


def test_multiple_blocks_rejected():
    text = "```bash\necho one\n```\nand also\n```bash\necho two\n```"
    result = extract_script(text)
    assert not result.ok
    assert result.n_blocks == 2


def test_empty_block_rejected():
    assert not extract_script("```bash\n```").ok


def test_thinking_channel_text_ignored_outside_fence():
    # Thought-channel prose mentioning code must not become the script.
    text = (
        "<|channel>thought\nI should write a for loop over the directory.\n<channel|>\n"
        "```bash\n#!/bin/bash\nprintf '%d\\n' \"$(ls | wc -l)\"\n```"
    )
    result = extract_script(text)
    assert result.ok
    assert "for loop" not in result.script


def test_prose_mentioning_bash_ticks_not_a_block():
    assert not extract_script("Use `bash` shebang and ``` in docs.").ok


def test_sh_and_shell_fences_accepted():
    assert extract_script("```sh\necho x\n```").ok
    assert extract_script("```shell\necho x\n```").ok


def test_whitespace_only_block_rejected():
    assert not extract_script("```bash\n   \n\t\n```").ok


def test_gemma4_prompt_template_frozen():
    """The rendered prompt must match the processor's observed output exactly."""
    from shell_grpo.generate import ModelConfig, render_prompt

    cfg = ModelConfig(
        deployment_alias="gemma4:e4b", repo_id="r", revision="v", quantization="q",
        chat_template="gemma-4-thinking", enable_thinking=True, max_seq_length=2048,
        max_new_tokens=512, temperature=1.0, top_p=0.95, top_k=64,
    )
    rendered = render_prompt(object(), "Count the files.", cfg)
    assert rendered == (
        "<|turn>system\n<|think|>\n<turn|>\n"
        "<|turn>user\nCount the files.<turn|>\n"
        "<|turn>model\n<|channel>thought\n<channel|>\n"
    )
    cfg2 = ModelConfig(
        deployment_alias="gemma4:e4b", repo_id="r", revision="v", quantization="q",
        chat_template="gemma-4-thinking", enable_thinking=False, max_seq_length=2048,
        max_new_tokens=512, temperature=1.0, top_p=0.95, top_k=64,
    )
    assert render_prompt(object(), "x", cfg2) == "<|turn>user\nx<turn|>\n<|turn>model\n"
