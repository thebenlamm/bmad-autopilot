"""Python AST parser for extracting code structure."""

import ast
import re
from pathlib import Path

from .models import IndexEntry


def extract_keywords(name: str, docstring: str | None, signature: str | None) -> list[str]:
    """Extract search keywords from symbol components.

    Args:
        name: Symbol name (function/class name)
        docstring: Documentation string
        signature: Function signature

    Returns:
        List of keywords
    """
    keywords = set()

    # Split camelCase and snake_case names
    # e.g., "getUserById" -> ["get", "user", "by", "id"]
    # e.g., "get_user_by_id" -> ["get", "user", "by", "id"]
    words = re.split(r'[_\s]+|(?<=[a-z])(?=[A-Z])', name)
    for word in words:
        if word and len(word) > 1:
            keywords.add(word.lower())

    # Extract words from docstring
    if docstring:
        # Remove common filler words
        filler = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "to", "of", "and", "or", "in", "on", "at", "for", "with", "by"}
        doc_words = re.findall(r'\b[a-zA-Z]{3,}\b', docstring.lower())
        for word in doc_words:
            if word not in filler:
                keywords.add(word)

    # Extract type names from signature
    if signature:
        type_words = re.findall(r'\b[A-Z][a-zA-Z]+\b', signature)
        for word in type_words:
            keywords.add(word.lower())
        # Also extract parameter names
        param_words = re.findall(r'(\w+)\s*:', signature)
        for word in param_words:
            if word and len(word) > 1:
                keywords.add(word.lower())

    return list(keywords)


class PythonParser:
    """Parses Python files to extract functions, classes, and methods."""

    def parse(self, file_path: Path) -> list[IndexEntry]:
        """Parse a Python file and extract symbols.

        Args:
            file_path: Path to Python file

        Returns:
            List of IndexEntry objects for found symbols
        """
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return []

        entries = []
        rel_path = str(file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                entry = self._parse_function(node, rel_path, "function")
                if entry:
                    entries.append(entry)

            elif isinstance(node, ast.AsyncFunctionDef):
                entry = self._parse_function(node, rel_path, "function")
                if entry:
                    entries.append(entry)

            elif isinstance(node, ast.ClassDef):
                # Add the class itself
                entry = self._parse_class(node, rel_path)
                if entry:
                    entries.append(entry)

                # Add methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_entry = self._parse_function(item, rel_path, "method")
                        if method_entry:
                            entries.append(method_entry)

        return entries

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, file_path: str, symbol_type: str) -> IndexEntry | None:
        """Parse a function/method node.

        Args:
            node: AST function node
            file_path: Path to the file
            symbol_type: 'function' or 'method'

        Returns:
            IndexEntry or None
        """
        name = node.name
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        # Get docstring
        docstring = ast.get_docstring(node)

        # Build signature
        signature = self._build_signature(node)

        # Extract keywords
        keywords = extract_keywords(name, docstring, signature)

        return IndexEntry(
            file_path=file_path,
            symbol_name=name,
            symbol_type=symbol_type,
            line_start=line_start,
            line_end=line_end,
            keywords=keywords,
            signature=signature,
            docstring=docstring,
        )

    def _parse_class(self, node: ast.ClassDef, file_path: str) -> IndexEntry | None:
        """Parse a class node.

        Args:
            node: AST class node
            file_path: Path to the file

        Returns:
            IndexEntry or None
        """
        name = node.name
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        # Get docstring
        docstring = ast.get_docstring(node)

        # Build simple signature (class name with bases)
        bases = [self._get_name(base) for base in node.bases if self._get_name(base)]
        signature = f"class {name}" + (f"({', '.join(bases)})" if bases else "")

        # Extract keywords
        keywords = extract_keywords(name, docstring, signature)

        return IndexEntry(
            file_path=file_path,
            symbol_name=name,
            symbol_type="class",
            line_start=line_start,
            line_end=line_end,
            keywords=keywords,
            signature=signature,
            docstring=docstring,
        )

    def _build_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build function signature string.

        Args:
            node: AST function node

        Returns:
            Signature string
        """
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_annotation(arg.annotation)}"
            args.append(arg_str)

        returns = ""
        if node.returns:
            returns = f" -> {self._get_annotation(node.returns)}"

        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        return f"{prefix}{node.name}({', '.join(args)}){returns}"

    def _get_annotation(self, node: ast.expr) -> str:
        """Get string representation of type annotation.

        Args:
            node: AST annotation node

        Returns:
            Annotation string
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            value = self._get_annotation(node.value)
            slice_val = self._get_annotation(node.slice)
            return f"{value}[{slice_val}]"
        elif isinstance(node, ast.Attribute):
            return f"{self._get_annotation(node.value)}.{node.attr}"
        elif isinstance(node, ast.Tuple):
            items = ", ".join(self._get_annotation(elt) for elt in node.elts)
            return items
        else:
            return "..."

    def _get_name(self, node: ast.expr) -> str | None:
        """Get name from expression node.

        Args:
            node: AST expression node

        Returns:
            Name string or None
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None
