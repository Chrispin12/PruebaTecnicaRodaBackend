import re
from enum import StrEnum

DOCUMENT_NUMBER_MAX_LENGTH = 20

_CC_PATTERN = re.compile(r"^\d{6,10}$")
_CE_PATTERN = re.compile(r"^[A-Z0-9]{6,12}$")
_PASSPORT_PATTERN = re.compile(r"^[A-Z0-9]{5,15}$")


class DocumentType(StrEnum):
    """Tipos de documento aceptados en el funnel (Colombia + pasaporte)."""

    CC = "cc"
    CE = "ce"
    PASSPORT = "passport"


def normalize_document_number(document_type: DocumentType, raw: str) -> str:
    compact = raw.strip().upper().replace(" ", "").replace("-", ".")
    compact = compact.replace(".", "")
    if document_type is DocumentType.CC:
        return re.sub(r"\D", "", compact)
    return re.sub(r"[^A-Z0-9]", "", compact)


def names_match(left: str, right: str) -> bool:
    return left.casefold().strip() == right.casefold().strip()


def is_valid_document_number(document_type: DocumentType, number: str) -> bool:
    if document_type is DocumentType.CC:
        return bool(_CC_PATTERN.fullmatch(number))
    if document_type is DocumentType.CE:
        return bool(_CE_PATTERN.fullmatch(number))
    return bool(_PASSPORT_PATTERN.fullmatch(number))
