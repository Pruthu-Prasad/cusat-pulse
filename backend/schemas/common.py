from pydantic import BaseModel, ConfigDict


class Out(BaseModel):
    """Base for response models. Extra columns pass through untouched, so the documented fields are a
    guaranteed minimum, not a filter (routes use response_model_exclude_unset to keep shapes exact)."""
    model_config = ConfigDict(extra="allow")
