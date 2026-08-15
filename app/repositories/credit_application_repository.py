"""Acceso a datos de clientes y solicitudes de credito.

Un commit atomico cubre el upsert del cliente (documento / correo) y el INSERT de la solicitud.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.domain.applicant import Applicant
from app.domain.credit_engine import CreditPlan
from app.domain.credit_terms import CreditTerms
from app.domain.identity import names_match
from app.domain.interest import quantize_rate
from app.models.credit_application import CreditApplication
from app.models.customer import Customer

logger = logging.getLogger(__name__)

_EMAIL_TAKEN = "Este correo electronico ya esta asociado a otro documento de identidad."
_IDENTITY_ALREADY_REGISTERED = (
    "Esta persona ya esta registrada con otra cedula. "
    "Un usuario solo puede tener un documento de identidad."
)
_IDENTITY_MISMATCH = (
    "Los datos no coinciden con la cedula ya registrada. "
    "Nombre y apellido deben ser los de la primera solicitud."
)


class CreditApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        applicant: Applicant,
        terms: CreditTerms,
        plan: CreditPlan,
    ) -> CreditApplication:
        try:
            customer = self._get_or_create_customer(applicant)
            application = CreditApplication(
                customer_id=customer.id,
                vehicle_type=terms.vehicle_type,
                vehicle_value=terms.vehicle_value,
                down_payment=terms.down_payment,
                term_months=terms.term_months,
                annual_interest_rate=quantize_rate(terms.annual_interest_rate),
                monthly_interest_rate=quantize_rate(plan.monthly_interest_rate),
                financed_amount=plan.financed_amount,
                monthly_payment=plan.monthly_payment,
                total_interest=plan.total_interest,
                total_payment=plan.total_payment,
            )
            self._session.add(application)
            self._session.commit()
        except BusinessRuleError:
            self._session.rollback()
            raise
        except IntegrityError:
            self._session.rollback()
            logger.info("Conflicto de unicidad al persistir cliente o solicitud")
            raise BusinessRuleError(_IDENTITY_ALREADY_REGISTERED) from None
        except SQLAlchemyError:
            self._session.rollback()
            logger.exception("Fallo al persistir la solicitud de credito")
            raise

        self._session.refresh(application)
        return application

    def _get_or_create_customer(self, applicant: Applicant) -> Customer:
        email = applicant.email.lower()
        by_document = self._session.scalar(
            select(Customer).where(
                Customer.document_type == applicant.document_type,
                Customer.document_number == applicant.document_number,
            )
        )
        by_email = self._session.scalar(select(Customer).where(Customer.email == email))

        if by_document is not None and by_email is not None and by_document.id != by_email.id:
            raise BusinessRuleError(_EMAIL_TAKEN)

        if by_document is not None:
            if not names_match(by_document.first_name, applicant.first_name) or not names_match(
                by_document.last_name, applicant.last_name
            ):
                raise BusinessRuleError(_IDENTITY_MISMATCH)
            if by_email is not None and by_email.id != by_document.id:
                raise BusinessRuleError(_EMAIL_TAKEN)
            by_document.email = email
            return by_document

        if by_email is not None:
            raise BusinessRuleError(_IDENTITY_ALREADY_REGISTERED)

        by_phone = self._session.scalar(select(Customer).where(Customer.phone == applicant.phone))
        if by_phone is not None:
            raise BusinessRuleError(_IDENTITY_ALREADY_REGISTERED)

        by_name = self._session.scalar(
            select(Customer).where(
                func.lower(Customer.first_name) == applicant.first_name.casefold().strip(),
                func.lower(Customer.last_name) == applicant.last_name.casefold().strip(),
            )
        )
        if by_name is not None:
            raise BusinessRuleError(_IDENTITY_ALREADY_REGISTERED)

        customer = Customer(
            first_name=applicant.first_name,
            last_name=applicant.last_name,
            document_type=applicant.document_type,
            document_number=applicant.document_number,
            email=email,
            phone=applicant.phone,
            city=applicant.city,
        )
        self._session.add(customer)
        self._session.flush()
        return customer
