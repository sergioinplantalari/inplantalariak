from __future__ import annotations

from datetime import datetime, timedelta, date
from random import choice

from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import Base, engine, SessionLocal
from .models import Patient, Service, Appointment, AppointmentStatus, Invoice, InvoiceItem


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)


def create_services(session: Session) -> list[Service]:
    existing = session.execute(select(Service)).scalars().all()
    if existing:
        return existing
    services = [
        Service(name="Fisioterapia", description="Sesión de fisioterapia", price_cents=4500),
        Service(name="Masaje deportivo", description="Masaje para deportistas", price_cents=3500),
        Service(name="Rehabilitación", description="Rehabilitación post-lesión", price_cents=5000),
        Service(name="Punción seca", description="Tratamiento de punción seca", price_cents=3000),
    ]
    session.add_all(services)
    session.commit()
    return services


def create_patients(session: Session) -> list[Patient]:
    if session.execute(select(Patient)).scalars().first():
        return session.execute(select(Patient)).scalars().all()
    sample = [
        dict(first_name="Ane", last_name="Etxeberria", phone="+34 688 111 222", email="ane.etxe@example.com", city="Bilbao", address="C/ Gran Vía, 12", zip_code="48001"),
        dict(first_name="Iker", last_name="García", phone="+34 644 333 444", email="iker.garcia@example.com", city="Barakaldo", address="Av. Libertad, 8", zip_code="48901"),
        dict(first_name="Maite", last_name="López", phone="+34 699 555 666", email="maite.lopez@example.com", city="Getxo", address="C/ Mayor, 22", zip_code="48930"),
        dict(first_name="Unai", last_name="Agirre", phone="+34 688 777 888", email="unai.agirre@example.com", city="Santurtzi", address="C/ Itsasalde, 5", zip_code="48980"),
        dict(first_name="Nerea", last_name="Sánchez", phone="+34 611 222 333", email="nerea.sanchez@example.com", city="Basauri", address="C/ Bidebieta, 14", zip_code="48970"),
        dict(first_name="Asier", last_name="Martínez", phone="+34 622 444 555", email="asier.martinez@example.com", city="Portugalete", address="C/ Coscojales, 3", zip_code="48920"),
    ]
    patients = [Patient(**p) for p in sample]
    session.add_all(patients)
    session.commit()
    return patients


def create_appointments(session: Session, patients: list[Patient], services: list[Service]) -> list[Appointment]:
    if session.execute(select(Appointment)).scalars().first():
        return session.execute(select(Appointment)).scalars().all()
    appointments: list[Appointment] = []
    now = datetime.utcnow()
    for i in range(12):
        patient = choice(patients)
        service = choice(services)
        when = now - timedelta(days=14 - i * 2)
        status = AppointmentStatus.COMPLETED if when < now else AppointmentStatus.SCHEDULED
        appointments.append(
            Appointment(patient_id=patient.id, service_id=service.id, scheduled_at=when, status=status)
        )
    session.add_all(appointments)
    session.commit()
    return appointments


def create_invoices_from_past_appointments(session: Session) -> list[Invoice]:
    past_uninvoiced = session.execute(
        select(Appointment).where(Appointment.scheduled_at < datetime.utcnow())
    ).scalars().all()
    created: list[Invoice] = []

    existing_any = session.execute(select(Invoice)).scalars().first()
    if existing_any:
        return session.execute(select(Invoice)).scalars().all()

    seq = 1
    year = datetime.utcnow().year
    for appt in past_uninvoiced[:5]:
        service = appt.service
        patient = appt.patient
        number = f"{year}-{seq:04d}"
        seq += 1
        subtotal = service.price_cents
        tax_percent = 21
        tax_cents = int(round(subtotal * tax_percent / 100))
        total_cents = subtotal + tax_cents

        invoice = Invoice(
            number=number,
            patient_id=patient.id,
            subtotal_cents=subtotal,
            tax_percent=tax_percent,
            tax_cents=tax_cents,
            total_cents=total_cents,
            paid=True,
        )
        item = InvoiceItem(
            description=service.name,
            quantity=1,
            unit_price_cents=service.price_cents,
            line_total_cents=service.price_cents,
            appointment_id=appt.id,
        )
        invoice.items.append(item)
        session.add(invoice)
    session.commit()

    return session.execute(select(Invoice)).scalars().all()


if __name__ == "__main__":
    ensure_schema()
    with SessionLocal() as session:
        services = create_services(session)
        patients = create_patients(session)
        appointments = create_appointments(session, patients, services)
        create_invoices_from_past_appointments(session)
    print("Seed completado.")
