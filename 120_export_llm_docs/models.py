"""
Data models for Phase 120: Export LLM-Friendly Documentation

This module defines the data structures used throughout the export pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class Parameter:
    """Represents a method or property parameter."""
    name: str
    description: str


@dataclass
class ExampleReference:
    """Reference to an example with language and URL."""
    name: str
    language: str
    url: str


@dataclass
class ExampleContent:
    """Full content of a code example."""
    url: str
    content: str
    title: Optional[str] = None
    language: Optional[str] = None


@dataclass
class Member:
    """Base class for type members (properties and methods)."""
    name: str
    description: str = ""
    parameters: List[Parameter] = field(default_factory=list)
    returns: str = ""
    remarks: str = ""
    signature: str = ""


@dataclass
class Property(Member):
    """Represents a type property."""
    pass


@dataclass
class Method(Member):
    """Represents a type method."""
    pass


@dataclass
class EnumMember:
    """Represents an enumeration member."""
    name: str
    description: str


@dataclass
class TypeInfo:
    """Complete information about a type (class, interface, or enum)."""
    name: str
    assembly: str
    namespace: str
    description: str = ""
    remarks: str = ""
    examples: List[ExampleReference] = field(default_factory=list)
    properties: List[Property] = field(default_factory=list)
    methods: List[Method] = field(default_factory=list)
    enum_members: List[EnumMember] = field(default_factory=list)
    functional_category: Optional[str] = None

    @property
    def fully_qualified_name(self) -> str:
        """Returns the fully qualified type name."""
        return f"{self.namespace}.{self.name}"

    @property
    def is_enum(self) -> bool:
        """Returns True if this type is an enumeration."""
        return len(self.enum_members) > 0


@dataclass
class FunctionalCategory:
    """Represents a functional category with its associated types."""
    name: str
    types: List[str] = field(default_factory=list)


@dataclass
class ExportStatistics:
    """Statistics about the export process."""
    total_types: int = 0
    types_with_descriptions: int = 0
    types_with_remarks: int = 0
    types_with_examples: int = 0
    total_properties: int = 0
    total_methods: int = 0
    total_enum_members: int = 0
    total_examples: int = 0
    functional_categories: int = 0
    markdown_files_generated: int = 0
    programming_guide_files: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'total_types': self.total_types,
            'types_with_descriptions': self.types_with_descriptions,
            'types_with_remarks': self.types_with_remarks,
            'types_with_examples': self.types_with_examples,
            'total_properties': self.total_properties,
            'total_methods': self.total_methods,
            'total_enum_members': self.total_enum_members,
            'total_examples': self.total_examples,
            'functional_categories': self.functional_categories,
            'markdown_files_generated': self.markdown_files_generated,
            'programming_guide_files': self.programming_guide_files,
        }
