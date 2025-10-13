from __future__ import annotations

from datetime import datetime, date
from typing import List

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .db import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    dni: Mapped[str | None] = mapped_column(String(32))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    zip_code: Mapped[str | None] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    appointments: Mapped[List[Appointment]] = relationship(
        "Appointment", back_populates="patient", cascade="all, delete-orphan"
    )
    invoices: Mapped[List[Invoice]] = relationship(
        "Invoice", back_populates="patient", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500))
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    appointments: Mapped[List[Appointment]] = relationship("Appointment", back_populates="service")


class AppointmentStatus:
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELED = "canceled"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            AppointmentStatus.SCHEDULED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELED,
            name="appointment_status",
        ),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    patient: Mapped[Patient] = relationship("Patient", back_populates="appointments")
    service: Mapped[Service] = relationship("Service", back_populates="appointments")
    invoice_item: Mapped[InvoiceItem | None] = relationship("InvoiceItem", back_populates="appointment")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=21)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    patient: Mapped[Patient] = relationship("Patient", back_populates="invoices")
    items: Mapped[List[InvoiceItem]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="items")
    appointment: Mapped[Appointment | None] = relationship("Appointment", back_populates="invoice_item")
