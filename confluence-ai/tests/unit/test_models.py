"""Unit tests for data models and exception classes."""

from __future__ import annotations

from confluence_ai.models import (
    AttachmentData,
    CodeBlockNode,
    ContentNode,
    ExportResult,
    GliffyNode,
    HeadingNode,
    HorizontalRuleNode,
    ImageContext,
    ImageDescriberConfig,
    ImageNode,
    InlineNode,
    LinkNode,
    ListItemNode,
    ListNode,
    MacroNode,
    PageData,
    PageMetadata,
    ParagraphNode,
    ParsedURL,
    TableNode,
    TextNode,
)
from confluence_ai.exceptions import (
    AuthenticationError,
    ConfluenceConnectionError,
    DownloadError,
    ExporterError,
    FileSystemError,
    ImageDescriptionError,
    InvalidURLError,
    PageNotFoundError,
    ParseError,
)


class TestContentNodes:
    """Verify IR content node construction and defaults."""

    def test_heading_node(self) -> None:
        node = HeadingNode(level=2, text="Section Title")
        assert node.level == 2
        assert node.text == "Section Title"
        assert isinstance(node, ContentNode)

    def test_paragraph_node_default_children(self) -> None:
        node = ParagraphNode()
        assert node.children == []
        assert isinstance(node, ContentNode)

    def test_text_node_defaults(self) -> None:
        node = TextNode(text="hello")
        assert node.text == "hello"
        assert node.bold is False
        assert node.italic is False
        assert node.underline is False
        assert node.code is False
        assert isinstance(node, InlineNode)

    def test_text_node_formatting(self) -> None:
        node = TextNode(text="bold", bold=True, italic=True)
        assert node.bold is True
        assert node.italic is True

    def test_link_node(self) -> None:
        node = LinkNode(href="https://example.com", text="Example")
        assert node.href == "https://example.com"
        assert node.text == "Example"
        assert isinstance(node, InlineNode)

    def test_list_node_defaults(self) -> None:
        node = ListNode(ordered=True)
        assert node.ordered is True
        assert node.items == []

    def test_list_item_node_defaults(self) -> None:
        item = ListItemNode()
        assert item.children == []

    def test_table_node_defaults(self) -> None:
        node = TableNode()
        assert node.headers == []
        assert node.rows == []

    def test_image_node_defaults(self) -> None:
        node = ImageNode(source_type="attachment", filename="img.png")
        assert node.source_type == "attachment"
        assert node.filename == "img.png"
        assert node.url is None
        assert node.alt_text == ""
        assert node.local_path is None

    def test_gliffy_node_defaults(self) -> None:
        node = GliffyNode(name="Process Flow")
        assert node.name == "Process Flow"
        assert node.diagram_id is None
        assert node.local_path is None
        assert node.alt_text == ""

    def test_code_block_node_defaults(self) -> None:
        node = CodeBlockNode(content="print('hi')")
        assert node.content == "print('hi')"
        assert node.language == ""

    def test_horizontal_rule_node(self) -> None:
        node = HorizontalRuleNode()
        assert isinstance(node, ContentNode)

    def test_macro_node_defaults(self) -> None:
        node = MacroNode(name="toc")
        assert node.name == "toc"
        assert node.parameters == {}
        assert node.body == ""


class TestAPIModels:
    """Verify API response model construction and defaults."""

    def test_parsed_url(self) -> None:
        url = ParsedURL(base_url="https://acme.atlassian.net/wiki", page_id="123")
        assert url.base_url == "https://acme.atlassian.net/wiki"
        assert url.page_id == "123"

    def test_page_data_defaults(self) -> None:
        page = PageData(
            page_id="1", title="Test", storage_format="<p>hi</p>", version=1
        )
        assert page.labels == []
        assert page.space_key == ""

    def test_attachment_data_defaults(self) -> None:
        att = AttachmentData(
            filename="img.png", media_type="image/png", download_url="/download/img.png"
        )
        assert att.file_size == 0
        assert att.comment == ""

    def test_page_metadata_defaults(self) -> None:
        meta = PageMetadata(
            source_url="https://example.com",
            page_id="1",
            page_title="Test",
            export_timestamp="2024-01-01T00:00:00Z",
            exporter_version="0.1.0",
        )
        assert meta.space_key == ""
        assert meta.labels == []


class TestConfigModels:
    """Verify configuration model construction and defaults."""

    def test_image_describer_config_defaults(self) -> None:
        cfg = ImageDescriberConfig(provider="anthropic", model="claude-sonnet-4-20250514")
        assert cfg.api_key == ""
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.2

    def test_image_context_defaults(self) -> None:
        ctx = ImageContext()
        assert ctx.is_gliffy is False
        assert ctx.alt_text == ""
        assert ctx.page_title == ""
        assert ctx.filename == ""


class TestResultModels:
    """Verify result model construction and defaults."""

    def test_export_result_defaults(self) -> None:
        result = ExportResult(
            markdown_path="/out/test.md",
            images_downloaded=5,
            descriptions_generated=3,
        )
        assert result.warnings == []

    def test_export_result_with_warnings(self) -> None:
        result = ExportResult(
            markdown_path="/out/test.md",
            images_downloaded=5,
            descriptions_generated=3,
            warnings=["Image download failed: img.png"],
        )
        assert len(result.warnings) == 1


class TestExceptions:
    """Verify custom exception construction and messages."""

    def test_invalid_url_error_default_message(self) -> None:
        err = InvalidURLError(url="http://bad-url")
        assert "http://bad-url" in str(err)
        assert err.url == "http://bad-url"
        assert isinstance(err, ExporterError)

    def test_invalid_url_error_custom_message(self) -> None:
        err = InvalidURLError(url="x", message="custom msg")
        assert str(err) == "custom msg"

    def test_authentication_error(self) -> None:
        err = AuthenticationError(
            base_url="https://acme.atlassian.net/wiki", status_code=401
        )
        assert "401" in str(err)
        assert err.base_url == "https://acme.atlassian.net/wiki"
        assert err.status_code == 401

    def test_confluence_connection_error(self) -> None:
        err = ConfluenceConnectionError(base_url="https://bad.atlassian.net/wiki")
        assert "bad.atlassian.net" in str(err)
        assert err.base_url == "https://bad.atlassian.net/wiki"

    def test_page_not_found_error_404(self) -> None:
        err = PageNotFoundError(page_id="999", status_code=404)
        assert "999" in str(err)
        assert "not found" in str(err).lower()

    def test_page_not_found_error_403(self) -> None:
        err = PageNotFoundError(page_id="999", status_code=403)
        assert "403" in str(err)
        assert "permission" in str(err).lower()

    def test_parse_error(self) -> None:
        err = ParseError()
        assert "parse" in str(err).lower()
        assert isinstance(err, ExporterError)

    def test_download_error(self) -> None:
        err = DownloadError(filename="img.png", url="https://x.com/img.png", status_code=404)
        assert "img.png" in str(err)
        assert err.filename == "img.png"
        assert err.status_code == 404

    def test_image_description_error(self) -> None:
        err = ImageDescriptionError(image_path="/tmp/img.png", provider="anthropic")
        assert "img.png" in str(err)
        assert "anthropic" in str(err)

    def test_filesystem_error(self) -> None:
        err = FileSystemError(path="/out/dir", operation="create")
        assert "/out/dir" in str(err)
        assert "create" in str(err)
