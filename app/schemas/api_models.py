"""`/api/v1/python/*` DTO 모음."""

from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

from app.domain.crawler.kumoh_menu import normalize_kumoh_cafeteria_name

T = TypeVar("T")


class PythonMealCrawlRequest(BaseModel):
    schoolName: str = Field(..., min_length=1)
    cafeteriaName: str = Field(
        ...,
        min_length=1,
        description=(
            "금오공대 식단 페이지 기준 식당명: 일품식당(restaurant01.do), "
            "정찬식당(restaurant02.do), 분식당(restaurant04.do). "
            "구명칭 학생식당→일품식당, 교직원식당→정찬식당 도 자동 치환됩니다."
        ),
    )
    sourceUrl: str = Field(..., min_length=1)
    startDate: date
    endDate: date

    @model_validator(mode="after")
    def validate_date_range_and_cafeteria(self):
        if self.startDate > self.endDate:
            raise ValueError("startDate는 endDate보다 이후일 수 없습니다.")
        self.cafeteriaName = normalize_kumoh_cafeteria_name(self.cafeteriaName)
        return self


class PythonMenuAnalysisTargetDto(BaseModel):
    menuId: int
    menuName: str = Field(..., min_length=1)


class PythonMenuAnalysisRequest(BaseModel):
    menus: list[PythonMenuAnalysisTargetDto] = Field(..., min_length=1)


class PythonMenuOcrMenuDto(BaseModel):
    menuName: str


class PythonMenuOcrResponse(BaseModel):
    rawText: str
    menus: list[PythonMenuOcrMenuDto]


class PythonMenuTranslationTargetDto(BaseModel):
    menuId: int
    menuName: str = Field(..., min_length=1)


class PythonMenuTranslationRequest(BaseModel):
    menus: list[PythonMenuTranslationTargetDto] = Field(..., min_length=1)
    targetLanguages: list[str] = Field(..., min_length=1)


class ApiErrorResponse(BaseModel):
    success: bool = Field(default=False, examples=[False])
    code: str = Field(..., examples=["COM_002"])
    msg: str = Field(..., examples=["요청 데이터 변환 과정에서 오류가 발생했습니다."])


class ApiSuccessResponse(BaseModel, Generic[T]):
    success: bool = Field(default=True, examples=[True])
    data: T


class PythonCrawledMenuDto(BaseModel):
    cornerName: str
    displayOrder: int
    menuName: str


class PythonDailyMealDto(BaseModel):
    mealDate: date
    mealType: str
    menus: list[PythonCrawledMenuDto]


class PythonMealCrawlResponse(BaseModel):
    schoolName: str
    cafeteriaName: str
    sourceUrl: str
    startDate: date
    endDate: date
    meals: list[PythonDailyMealDto]


class PythonMenuIngredientResultDto(BaseModel):
    ingredientCode: str
    confidence: float


class PythonMenuAllergyResultDto(BaseModel):
    allergyCode: str
    confidence: float


class PythonMenuAnalysisResultDto(BaseModel):
    menuId: int
    menuName: str
    status: str
    reason: Optional[str] = None
    modelName: str
    modelVersion: str
    analyzedAt: datetime
    ingredients: list[PythonMenuIngredientResultDto]
    allergies: list[PythonMenuAllergyResultDto] = Field(default_factory=list)
    spicyLevel: Optional[int] = None


class PythonMenuAnalysisResponse(BaseModel):
    results: list[PythonMenuAnalysisResultDto]


class PythonTranslatedMenuNameDto(BaseModel):
    langCode: str
    translatedName: str


class PythonMenuTranslationResultDto(BaseModel):
    menuId: int
    sourceName: str
    translations: list[PythonTranslatedMenuNameDto]


class PythonMenuTranslationResponse(BaseModel):
    results: list[PythonMenuTranslationResultDto]
