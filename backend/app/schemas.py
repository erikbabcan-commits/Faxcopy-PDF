import hashlib
import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def digest(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Rules(StrictModel):
    trim_width_mm: float | None = Field(default=None, ge=10, le=3000)
    trim_height_mm: float | None = Field(default=None, ge=10, le=3000)
    tolerance_mm: float = Field(default=0.5, ge=0.05, le=3)
    bleed_mm: float = Field(default=0, ge=0, le=20)
    min_dpi: int = Field(default=150, ge=36, le=2400)
    min_pages: int = Field(default=1, ge=1, le=200)
    max_pages: int = Field(default=200, ge=1, le=200)
    require_embedded_fonts: bool = True
    require_explicit_trim: bool = False
    flag_rgb: bool = False

    @model_validator(mode="after")
    def pair_dimensions(self):
        if (self.trim_height_mm is None) != (self.trim_width_mm is None):
            raise ValueError("Zadajte oba rozmery alebo žiadny.")
        return self

    @field_validator("max_pages")
    @classmethod
    def page_range(cls, v, info):
        if v < info.data.get("min_pages", 1):
            raise ValueError("Maximum strán musí byť aspoň minimum.")
        return v


class LoginIn(StrictModel):
    workspace_id: str = Field(min_length=36, max_length=36)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ProfileIn(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    rules: Rules
    base_profile_id: str | None = None


class ReviewIn(StrictModel):
    decision: Literal["accepted", "rejected"]
    note: str = Field(min_length=10, max_length=2000)
    acknowledge_limits: bool

    @field_validator("note")
    @classmethod
    def meaningful_note(cls, value):
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Poznámka musí obsahovať aspoň 10 neprázdnych znakov vrátane slov.")
        return value


class MemberIn(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["owner", "operator", "viewer"] = "operator"

    @field_validator("email")
    @classmethod
    def email_shape(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Neplatný e-mail.")
        return value


class PasswordIn(StrictModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


PRESETS = [
    ("Vstupná kontrola PDF", Rules().model_dump()),
    ("Vizitka · 85 × 55 mm", Rules(trim_width_mm=85, trim_height_mm=55, bleed_mm=3,
         min_dpi=300, max_pages=2, require_explicit_trim=True).model_dump()),
    ("Leták A5 · 148 × 210 mm", Rules(trim_width_mm=148, trim_height_mm=210, bleed_mm=3,
         min_dpi=300, max_pages=2, require_explicit_trim=True).model_dump()),
]


class KeyIn(StrictModel):
    name: str = Field(min_length=2, max_length=80)
    scope: Literal["read", "upload"] = "upload"
    expires_days: int = Field(default=30, ge=1, le=90)
