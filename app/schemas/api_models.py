"""`/api/v1/python/*` DTO 모음."""

from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class PythonMealCrawlRequest(BaseModel):
    schoolName: str = Field(..., min_length=1)
    cafeteriaName: str = Field(..., min_length=1)
    sourceUrl: str = Field(..., min_length=1)
    startDate: date
    endDate: date

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.startDate > self.endDate:
            raise ValueError("startDate는 endDate보다 이후일 수 없습니다.")
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


class PythonMenuAnalysisResultDto(BaseModel):
    menuId: int
    menuName: str
    status: str
    reason: Optional[str] = None
    modelName: str
    modelVersion: str
    analyzedAt: datetime
    ingredients: list[PythonMenuIngredientResultDto]


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
