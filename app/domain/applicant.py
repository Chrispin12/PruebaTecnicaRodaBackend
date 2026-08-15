from dataclasses import dataclass

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

    Existe como tipo del dominio para que el caso de uso y el repositorio no se pasen entre si
    el schema HTTP ni una bolsa de cinco argumentos sueltos. No valida formato: eso pertenece
    al contrato de entrada, que es donde se sabe que el dato viene de un formulario.
    """

    first_name: str
    last_name: str
    email: str
    phone: str
    city: str
