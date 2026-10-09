"""Application-level errors shared by every AI provider."""


class AIProviderError(Exception):
    """Base provider failure safe for business services to catch."""


class AIProviderUnavailableError(AIProviderError):
    """Provider or configured model cannot currently be reached."""


class AIProviderAuthenticationError(AIProviderError):
    """Provider credentials are missing or rejected."""


class AIProviderRateLimitError(AIProviderError):
    """Provider rejected the request due to quota or rate limiting."""


class AIProviderTimeoutError(AIProviderError):
    """Provider request exceeded its configured deadline."""


class AIProviderResponseError(AIProviderError):
    """Provider returned malformed or schema-invalid content."""


class EmbeddingDimensionError(AIProviderResponseError):
    """An embedding vector did not have the configured dimensions."""


class EmbeddingCompatibilityError(AIProviderError):
    """Query and stored document vectors belong to different spaces."""
