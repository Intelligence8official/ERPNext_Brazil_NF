"""
CNPJ (Cadastro Nacional da Pessoa Juridica) validation and formatting utilities.
"""


def clean_cnpj(cnpj):
    """
    Remove formatting from CNPJ.

    Args:
        cnpj: CNPJ string with or without formatting

    Returns:
        str: Clean CNPJ (14 digits only)
    """
    if not cnpj:
        return ""
    return "".join(filter(str.isdigit, str(cnpj)))


def validate_cnpj(cnpj):
    """
    Validate a CNPJ number using the official algorithm.

    The validation uses two check digits calculated using module 11.

    Args:
        cnpj: CNPJ string (14 digits)

    Returns:
        bool: True if valid, False otherwise
    """
    cnpj = clean_cnpj(cnpj)

    # Must be 14 digits
    if len(cnpj) != 14:
        return False

    # All same digits is invalid
    if cnpj == cnpj[0] * 14:
        return False

    # Calculate first check digit
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * weights1[i] for i in range(12))
    remainder = total % 11
    digit1 = 0 if remainder < 2 else 11 - remainder

    if int(cnpj[12]) != digit1:
        return False

    # Calculate second check digit
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * weights2[i] for i in range(13))
    remainder = total % 11
    digit2 = 0 if remainder < 2 else 11 - remainder

    if int(cnpj[13]) != digit2:
        return False

    return True


def format_cnpj(cnpj):
    """
    Format CNPJ with mask: XX.XXX.XXX/XXXX-XX

    Args:
        cnpj: Clean CNPJ (14 digits)

    Returns:
        str: Formatted CNPJ
    """
    cnpj = clean_cnpj(cnpj)

    if len(cnpj) != 14:
        return cnpj

    return f"{cnpj[0:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"


def get_cnpj_base(cnpj):
    """
    Get the base (root) CNPJ (first 8 digits).

    This identifies the company regardless of branch.

    Args:
        cnpj: CNPJ string

    Returns:
        str: 8-digit base CNPJ
    """
    cnpj = clean_cnpj(cnpj)

    if len(cnpj) < 8:
        return cnpj

    return cnpj[:8]


def get_cnpj_branch(cnpj):
    """
    Get the branch number from CNPJ (digits 9-12).

    0001 = headquarters
    0002+ = branches

    Args:
        cnpj: CNPJ string

    Returns:
        str: 4-digit branch number
    """
    cnpj = clean_cnpj(cnpj)

    if len(cnpj) < 12:
        return ""

    return cnpj[8:12]


def is_headquarters(cnpj):
    """
    Check if CNPJ is for headquarters (branch = 0001).

    Args:
        cnpj: CNPJ string

    Returns:
        bool: True if headquarters
    """
    return get_cnpj_branch(cnpj) == "0001"
