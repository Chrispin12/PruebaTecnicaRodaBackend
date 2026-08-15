"""Acceso a datos de `credit_applications`.

Unico modulo que conoce SQLAlchemy para esta entidad: el caso de uso no importa la sesion ni
el modelo, asi que puede probarse y razonarse sin base de datos. Solo expone lo que la prueba
necesita; no se agrega un CRUD completo que nadie usa.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.applicant import Applicant
from app.domain.credit_engine import CreditPlan
from app.domain.credit_terms import CreditTerms
from app.domain.interest import quantize_rate
from app.models.credit_application import CreditApplication

logger = logging.getLogger(__name__)


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
        """Persiste la solicitud y devuelve la fila almacenada.

        El resultado financiero se guarda tal como se calculo: es la fotografia de lo que se
        le presento al solicitante, no un valor a recalcular despues.

        La operacion es atomica: un solo INSERT y un commit. Si algo falla se revierte la
        transaccion y se propaga el error, que el manejador global convierte en un 500 con
        mensaje generico; el detalle de PostgreSQL queda unicamente en los logs.
        """
        application = CreditApplication(
            first_name=applicant.first_name,
            last_name=applicant.last_name,
            email=applicant.email,
            phone=applicant.phone,
            city=applicant.city,
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

        try:
            self._session.add(application)
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            logger.exception("Fallo al persistir la solicitud de credito")
            raise

        # `created_at` lo genera la base de datos: sin refresh el objeto no lo tiene cargado.
        self._session.refresh(application)
        return application
