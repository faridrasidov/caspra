# app/schemas/report.py

from datetime import date

from pydantic import BaseModel


class DailyReportRow(BaseModel):
    day: date
    transaction_count: int
    total_credit_minor: int
    total_debit_minor: int


class DailyReportOut(BaseModel):
    currency: str | None = None
    rows: list[DailyReportRow]


class DeviceReportRow(BaseModel):
    device_id: str
    device_name: str
    transaction_count: int
    total_amount_minor: int


class DeviceReportOut(BaseModel):
    rows: list[DeviceReportRow]


class TopProductRow(BaseModel):
    product_id: str
    product_name: str
    units_sold: int
    revenue_minor: int


class TopProductsOut(BaseModel):
    rows: list[TopProductRow]


class CustomerActivityRow(BaseModel):
    customer_id: str
    transaction_count: int
    total_spent_minor: int


class CustomerActivityOut(BaseModel):
    rows: list[CustomerActivityRow]


class ReportExportOut(BaseModel):
    format: str
    report: str
    rows: list[dict]
