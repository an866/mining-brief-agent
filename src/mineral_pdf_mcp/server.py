"""mineral-pdf-mcp — exposes the ``extract_resources`` tool over MCP."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mining_brief_core.errors import MiningBriefError
from mining_brief_core.logging_setup import configure_logging

from . import __version__
from .extract import extract_resources_from_pdf
from .fetch import resolve_pdf_source
from .models import ExtractionResult

SERVER_NAME = "mineral-pdf-mcp"


def build_server() -> MCPServer:
    """Build the ``mineral-pdf-mcp`` server."""
    server = MCPServer(
        name=SERVER_NAME,
        title="Mineral Resource PDF",
        description=(
            "Extract NI 43-101 mineral-resource statements (Measured/Indicated/Inferred "
            "categories with tonnage, grade, and contained metal) from a PDF given by "
            "URL or local path. Every row carries its page number and raw evidence line."
        ),
        version=__version__,
    )

    @server.tool(
        name="extract_resources",
        description=(
            "Extract Indicated/Inferred (and Measured/Total when present) resource rows "
            "from an NI 43-101 style technical report PDF. Accepts an http(s) URL, a "
            "file:// URI, or a path relative to the repository root. Returns tonnage "
            "(Mt), grade (g/t or %), contained metal, plus page numbers and evidence "
            "quotes for citation."
        ),
    )
    def extract_resources(pdf_url: str) -> ExtractionResult:
        try:
            local_path, downloaded = resolve_pdf_source(pdf_url)
            result = extract_resources_from_pdf(str(local_path), source_uri=pdf_url)
        except MiningBriefError as exc:
            raise ToolError(f"extract_resources failed for {pdf_url}: {exc}") from exc
        if downloaded:
            result.warnings.append(f"downloaded and cached at {local_path}")
        return result

    return server


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    configure_logging(SERVER_NAME)
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
