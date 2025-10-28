from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from .db import Base, engine, get_db
from .models import Patient, Service, Appointment, AppointmentStatus, Invoice, InvoiceItem

app = FastAPI(title="CRM Fisioterapia Bizkaia")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


def _format_eur(value_cents: int) -> str:
    euros = value_cents / 100
    return f"{euros:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


templates.env.filters["eur"] = _format_eur
templates.env.globals["now"] = datetime.utcnow


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    patients_count = db.scalar(select(func.count()).select_from(Patient)) or 0
    upcoming_count = db.scalar(
        select(func.count()).select_from(Appointment).where(
            Appointment.scheduled_at >= datetime.utcnow(),
            Appointment.status == AppointmentStatus.SCHEDULED,
        )
    ) or 0
    invoices_count = db.scalar(select(func.count()).select_from(Invoice)) or 0

    recent_appointments = db.execute(
        select(Appointment).order_by(Appointment.scheduled_at.desc()).limit(5)
    ).scalars().all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "patients_count": patients_count,
            "upcoming_count": upcoming_count,
            "invoices_count": invoices_count,
            "recent_appointments": recent_appointments,
        },
    )


# Patients
@app.get("/pacientes")
def list_patients(request: Request, db: Session = Depends(get_db)):
    patients = db.execute(select(Patient).order_by(Patient.last_name, Patient.first_name)).scalars().all()
    return templates.TemplateResponse("patients/list.html", {"request": request, "patients": patients})


@app.get("/pacientes/nuevo")
def new_patient_form(request: Request):
    return templates.TemplateResponse("patients/new.html", {"request": request})


@app.post("/pacientes/nuevo")
def create_patient(
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str | None = Form(None),
    email: str | None = Form(None),
    dni: str | None = Form(None),
    date_of_birth: str | None = Form(None),
    address: str | None = Form(None),
    city: str | None = Form(None),
    zip_code: str | None = Form(None),
    db: Session = Depends(get_db),
):
    dob = None
    if date_of_birth:
        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            dob = None

    patient = Patient(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip() if phone else None,
        email=email.strip() if email else None,
        dni=dni.strip() if dni else None,
        date_of_birth=dob,
        address=address.strip() if address else None,
        city=city.strip() if city else None,
        zip_code=zip_code.strip() if zip_code else None,
    )
    db.add(patient)
    db.commit()
    return RedirectResponse(url="/pacientes", status_code=303)


# Appointments
@app.get("/citas")
def list_appointments(request: Request, db: Session = Depends(get_db)):
    appointments = db.execute(
        select(Appointment).order_by(Appointment.scheduled_at.desc())
    ).scalars().all()
    services = db.execute(select(Service).order_by(Service.name)).scalars().all()
    patients = db.execute(select(Patient).order_by(Patient.last_name, Patient.first_name)).scalars().all()
    return templates.TemplateResponse(
        "appointments/list.html",
        {"request": request, "appointments": appointments, "services": services, "patients": patients},
    )


@app.get("/citas/nueva")
def new_appointment_form(request: Request, db: Session = Depends(get_db)):
    services = db.execute(select(Service).order_by(Service.name)).scalars().all()
    patients = db.execute(select(Patient).order_by(Patient.last_name, Patient.first_name)).scalars().all()
    return templates.TemplateResponse(
        "appointments/new.html", {"request": request, "services": services, "patients": patients}
    )


@app.post("/citas/nueva")
def create_appointment(
    patient_id: int = Form(...),
    service_id: int = Form(...),
    scheduled_at: str = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    dt = datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
    appt = Appointment(
        patient_id=patient_id,
        service_id=service_id,
        scheduled_at=dt,
        notes=notes.strip() if notes else None,
    )
    db.add(appt)
    db.commit()
    return RedirectResponse(url="/citas", status_code=303)


# Invoices
@app.get("/facturas")
def list_invoices(request: Request, db: Session = Depends(get_db)):
    invoices = db.execute(select(Invoice).order_by(Invoice.issue_date.desc())).scalars().all()
    return templates.TemplateResponse("invoices/list.html", {"request": request, "invoices": invoices})


@app.get("/facturas/nueva")
def new_invoice_form(request: Request, db: Session = Depends(get_db)):
    # Only appointments without invoice item
    appointments = db.execute(
        select(Appointment).where(Appointment.id.notin_(select(InvoiceItem.appointment_id))).order_by(
            Appointment.scheduled_at.desc()
        )
    ).scalars().all()
    return templates.TemplateResponse(
        "invoices/new.html",
        {"request": request, "appointments": appointments},
    )


@app.get("/facturas/{invoice_id}")
def invoice_detail(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/facturas", status_code=303)
    return templates.TemplateResponse("invoices/detail.html", {"request": request, "invoice": invoice})


@app.post("/facturas/nueva")
def create_invoice(
    appointment_id: int = Form(...),
    paid: bool | None = Form(None),
    db: Session = Depends(get_db),
):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        return RedirectResponse(url="/facturas/nueva", status_code=303)

    service = appt.service
    patient = appt.patient

    year = datetime.utcnow().year
    last_in_year = db.execute(
        select(Invoice).where(func.strftime("%Y", Invoice.issue_date) == str(year)).order_by(Invoice.id.desc())
    ).scalars().first()
    next_seq = 1
    if last_in_year and last_in_year.number.startswith(str(year)):
        try:
            next_seq = int(last_in_year.number.split("-")[1]) + 1
        except Exception:
            next_seq = last_in_year.id + 1
    number = f"{year}-{next_seq:04d}"

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
        paid=bool(paid),
    )

    item = InvoiceItem(
        description=service.name,
        quantity=1,
        unit_price_cents=service.price_cents,
        line_total_cents=service.price_cents,
        appointment_id=appt.id,
    )
    invoice.items.append(item)

    db.add(invoice)
    db.commit()

    # Mark appointment as completed if in the past
    if appt.scheduled_at <= datetime.utcnow():
        appt.status = AppointmentStatus.COMPLETED
        db.commit()

    return RedirectResponse(url=f"/facturas/{invoice.id}", status_code=303)
