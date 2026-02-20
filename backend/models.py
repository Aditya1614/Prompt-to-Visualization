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


class VisualizeResponse(BaseModel):
    """Response schema from the /api/visualize endpoint."""
    rejected: bool = Field(False, description="Whether the request was rejected")
    reject_reason: str = Field("", description="Reason for rejection, if any")
    chart_type: str = Field("", description="Type of chart: line, bar, pie, scatter, area")
    chart_config: Optional[ChartConfig] = Field(None, description="Chart configuration")
    insight: str = Field("", description="AI-generated insight about the data")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage statistics")
