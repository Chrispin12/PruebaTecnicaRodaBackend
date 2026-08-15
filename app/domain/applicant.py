from dataclasses import dataclass

from app.domain.identity import DocumentType

# Longitudes maximas de los datos del solicitante. Viven aqui, y no en el modelo ni en el
# schema, para que el contrato de entrada y la columna de la tabla usen el mismo numero: si el
# contrato aceptara mas de lo que cabe en la columna, el error saldria de PostgreSQL.
NAME_MAX_LENGTH = 80
EMAIL_MAX_LENGTH = 255
PHONE_MAX_LENGTH = 20
CITY_MAX_LENGTH = 80


@dataclass(frozen=True)
class Applicant:
    """Datos de la persona que solicita el credito (RF-05).

    El documento de identidad es la clave natural del cliente; el correo tambien es unico.
    No valida formato: eso pertenece al contrato de entrada.
    """

    first_name: str
    last_name: str
    document_type: DocumentType
    document_number: str
    email: str
    phone: str
    city: str
