# docstrings.md

---
description: Require docstrings for all public objects
globs: "**/*.py"
alwaysApply: true
---

# Docstring Requirements

Every public Python object must have a docstring:

- **Modules**: Module-level docstring explaining purpose
- **Classes**: Class docstring with description and attributes
- **Functions/Methods**: Docstring with Args, Returns, Raises (if applicable)

## Example

```python
"""AI provider factory module.

This module provides factory functions for creating AI provider instances
from user configuration.
"""

class ProviderFactory:
    """Factory for creating AI provider instances from user configuration.

    Attributes:
        PROVIDER_PRESETS: Dictionary of predefined provider configurations.
    """

    @classmethod
    def from_config(
        cls,
        base_url: str,
        model: str,
        api_key: str | None = None,
    ) -> AIProvider:
        """Create a provider from user-provided configuration.

        Args:
            base_url: API endpoint URL.
            model: Model name to use.
            api_key: API key (optional for local providers).

        Returns:
            Configured AIProvider instance.

        Raises:
            ValueError: If api_type is not supported.
        """
```

## Exceptions

- Private methods/functions (prefixed with `_`) may omit docstrings if trivial
- Test functions may have minimal docstrings
