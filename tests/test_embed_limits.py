import pytest
import utils

def test_create_embed_truncation():
    """Verify create_embed safely truncates strings exceeding Discord API limits."""
    huge_title = "A" * 300
    huge_desc = "B" * 5000
    huge_footer = "C" * 2500
    huge_field_name = "D" * 300
    huge_field_val = "E" * 1500

    embed = utils.create_embed(
        title=huge_title,
        description=huge_desc,
        footer_text=huge_footer,
        fields=[{"name": huge_field_name, "value": huge_field_val}]
    )

    assert len(embed.title) <= 256
    assert embed.title.endswith("...")
    assert len(embed.description) <= 4096
    assert embed.description.endswith("\n...")
    assert len(embed.footer.text) <= 2048
    assert embed.footer.text.endswith("...")
    assert len(embed.fields[0].name) <= 256
    assert embed.fields[0].name.endswith("...")
    assert len(embed.fields[0].value) <= 1024
    assert embed.fields[0].value.endswith("...")

def test_chunk_text_lines_normal():
    """Verify chunk_text_lines correctly splits lines without exceeding max_chars."""
    lines = [f"P{i}: Team {i} - long text line with details {i * 100}" for i in range(1, 100)]
    chunks = utils.chunk_text_lines(lines, max_chars=1000)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000

    # Ensure all original lines are present across chunks
    combined = "\n".join(chunks)
    for line in lines:
        assert line in combined

def test_chunk_text_lines_single_huge_line():
    """Verify chunk_text_lines handles individual lines larger than max_chars."""
    huge_line = "X" * 2500
    chunks = utils.chunk_text_lines([huge_line], max_chars=1000)

    assert len(chunks) == 3
    assert len(chunks[0]) == 1000
    assert len(chunks[1]) == 1000
    assert len(chunks[2]) == 500

def test_chunk_text_lines_empty():
    """Verify chunk_text_lines handles empty input."""
    assert utils.chunk_text_lines([]) == []
