"""Load the project catalog (``data/projects.json``).

The catalog maps a human project name and its aliases to the things a brief
needs: which commodities to price, what to search the news for, and which
NI 43-101 documents to mine for resource statements.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import BaseModel, Field

from mining_brief_core import paths
from mining_brief_core.errors import DataNotFoundError

CATALOG_SCHEMA = "mining-brief-agent/projects@1"


class ResourceDoc(BaseModel):
    label: str
    uri: str


class ProjectSpec(BaseModel):
    key: str
    name_en: str
    name_zh: str
    aliases: list[str] = Field(default_factory=list)
    commodities: list[str] = Field(default_factory=list)
    news_query: str
    resources: list[ResourceDoc] = Field(default_factory=list)
    risk_keywords: list[str] = Field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.name_zh or self.name_en


class Catalog(BaseModel):
    schema_: str = Field(alias="schema")
    note: str = ""
    default_project: str
    projects: list[ProjectSpec]

    model_config = {"populate_by_name": True}

    def by_key(self, key: str) -> ProjectSpec:
        for project in self.projects:
            if project.key == key:
                return project
        raise DataNotFoundError(f"project {key!r} is not in the catalog")


def load_catalog(path_str: str | None = None) -> Catalog:
    """Load the catalog (cached per path; pass a fresh path in tests)."""
    return _load_catalog_cached(path_str)


@lru_cache(maxsize=4)
def _load_catalog_cached(path_str: str | None) -> Catalog:
    path = paths.projects_file() if path_str is None else paths.project_root() / path_str
    if not path.is_file():
        raise DataNotFoundError(f"project catalog not found at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Catalog.model_validate(payload)
