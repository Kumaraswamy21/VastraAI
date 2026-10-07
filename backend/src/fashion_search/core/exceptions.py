"""Domain errors for conversational fashion search."""


class FashionSearchError(Exception):
    """Base error for the fashion search domain."""


class OffTopicQueryError(FashionSearchError):
    """Raised when a user message is outside fashion catalog search."""


class AmbiguousQueryError(FashionSearchError):
    """Raised when a query needs a clarifying question before retrieval."""
