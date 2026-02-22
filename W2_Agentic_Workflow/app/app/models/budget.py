"""
Budget tracking models.
"""
from typing import List

from pydantic import BaseModel, Field


class BudgetCategory(BaseModel):
    """Per-category budget allocation and spend."""

    category: str = Field(..., description="e.g. transport, accommodation, activities")
    allocated: float = Field(..., ge=0)
    spent: float = Field(default=0, ge=0)
    remaining: float = Field(..., description="allocated - spent")


class BudgetTracker(BaseModel):
    """Overall budget with categories and warnings."""

    total_budget: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    categories: List[BudgetCategory] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def is_over_budget(self) -> bool:
        return self.remaining_total() < 0

    def remaining_total(self) -> float:
        return self.total_budget - sum(c.spent for c in self.categories)
