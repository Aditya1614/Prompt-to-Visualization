"""Pydantic models for request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Any


class VisualizeRequest(BaseModel):
    """Request schema for the /api/visualize endpoint."""
    prompt: str = Field(..., description="User's natural language question about the data")
    data: Optional[list[dict[str, Any]]] = Field(None, description="JSON array of data records (for JSON paste mode)")
    table_name: Optional[str] = Field(None, description="BigQuery table name (for dropdown mode)")
    dataset: Optional[str] = Field(None, description="BigQuery dataset name (company)")


class ChartConfig(BaseModel):
    """Chart configuration that the frontend will use to render a chart."""
    x_field: str = Field("", description="Column name for x-axis")
    y_field: str | list[str] = Field("", description="Column name(s) for y-axis")
    data: list[dict[str, Any]] = Field(default_factory=list, description="Processed data for the chart")
    title: str = Field("", description="Chart title")
    x_label: str = Field("", description="X-axis label")
    y_label: str = Field("", description="Y-axis label")
    colors: list[str] = Field(default_factory=list, description="Optional color palette")


class TokenUsage(BaseModel):
    """Token usage statistics from the AI agent."""
    prompt_tokens: int = Field(0, description="Number of input/prompt tokens")
    completion_tokens: int = Field(0, description="Number of output/completion tokens")
    total_tokens: int = Field(0, description="Total tokens used")
    agent_turns: int = Field(0, description="Number of agent turns (tool calls + final response)")


class CountTokensResponse(BaseModel):
    """Response schema for token counting endpoint."""
    total_tokens: int = Field(0, description="Estimated total tokens for the input")


class TableInfo(BaseModel):
    """Info about a single BigQuery table."""
    name: str = Field(..., description="Table name")


class TableListResponse(BaseModel):
    """Response with list of available tables."""
    dataset: str = Field("", description="BigQuery dataset name")
    tables: list[TableInfo] = Field(default_factory=list, description="Available tables")


class QuotaInfo(BaseModel):
    """Token quota information for a user."""
    registered: bool = Field(True, description="Whether the user is registered for quota")
    email: str = Field("", description="User's email")
    daily_limit: int = Field(0, description="Daily token limit")
    used_today: int = Field(0, description="Tokens used today")
    remaining: int = Field(0, description="Tokens remaining today")
    date: str = Field("", description="Current date (quota resets daily)")
    is_admin: bool = Field(False, description="Whether the user is an admin")


class VisualizeResponse(BaseModel):
    """Response schema from the /api/visualize endpoint."""
    rejected: bool = Field(False, description="Whether the request was rejected")
    reject_reason: str = Field("", description="Reason for rejection, if any")
    chart_type: str = Field("", description="Type of chart: line, bar, pie, scatter, area")
    chart_config: Optional[ChartConfig] = Field(None, description="Chart configuration")
    insight: str = Field("", description="AI-generated insight about the data")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage statistics")
    quota: Optional[QuotaInfo] = Field(None, description="Updated quota info after request")


# ── Admin Models ──────────────────────────────────────────────────

class OrgUser(BaseModel):
    """A user from the Lark organization."""
    name: str = Field("", description="User's display name")
    email: str = Field("", description="User's email")
    avatar_url: str = Field("", description="Avatar image URL")
    department: str = Field("", description="Department name or ID")
    open_id: str = Field("", description="Lark open_id")


class QuotaSettingEntry(BaseModel):
    """A registered user's quota settings for the admin dashboard."""
    email: str = Field("", description="User's email")
    name: str = Field("", description="Display name")
    daily_limit: int = Field(0, description="Daily token limit")
    used_today: int = Field(0, description="Tokens used today")
    remaining: int = Field(0, description="Tokens remaining today")
    is_admin: bool = Field(False, description="Whether the user is an admin")


class UpdateUserRequest(BaseModel):
    """Request to add or update a user's quota."""
    email: str = Field(..., description="User's email")
    name: str = Field("", description="Display name")
    daily_limit: int = Field(100_000, description="Daily token limit")


class RemoveUserRequest(BaseModel):
    """Request to remove a user's access."""
    email: str = Field(..., description="User's email")


class SetAdminRequest(BaseModel):
    """Request to change a user's admin status."""
    email: str = Field(..., description="User's email")
    is_admin: bool = Field(..., description="Whether the user should be an admin")


class DatamartInfoAdmin(BaseModel):
    """Admin view of a datamart's access control."""
    dataset: str = Field(..., description="BigQuery dataset name")
    table: str = Field(..., description="BigQuery table name")
    allowed_users: list[str] = Field(default_factory=list, description="List of emails allowed to access")


class UpdateDatamartAccessRequest(BaseModel):
    """Request to update users allowed for a datamart."""
    dataset: str = Field(..., description="BigQuery dataset name")
    table: str = Field(..., description="BigQuery table name")
    allowed_users: list[str] = Field(..., description="List of emails allowed to access")
