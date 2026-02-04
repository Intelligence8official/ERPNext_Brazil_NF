"""
Chave de Acesso (Access Key) parsing and validation utilities.

The chave de acesso is a 44-digit unique identifier for NF-e, CT-e, and NFS-e documents.

Structure: UF(2) + AAMM(4) + CNPJ(14) + Modelo(2) + Serie(3) + Numero(9) + TipoEmissao(1) + Codigo(8) + DV(1)
"""


def clean_chave(chave):
    """
    Remove formatting (spaces, dashes) from chave de acesso.

    Args:
        chave: Access key string

    Returns:
        str: Clean 44-digit key
    """
    if not chave:
        return ""
    return "".join(filter(str.isdigit, str(chave)))


def parse_chave_acesso(chave):
    """
    Parse the 44-digit access key into its components.

    Args:
        chave: 44-digit access key

    Returns:
        dict: Parsed components or None if invalid length
    """
    chave = clean_chave(chave)

    if len(chave) != 44:
        return None

    return {
        "uf": chave[0:2],
        "ano_mes": chave[2:6],
        "cnpj": chave[6:20],
        "modelo": chave[20:22],
        "serie": chave[22:25],
        "numero": chave[25:34],
        "tipo_emissao": chave[34:35],
        "codigo": chave[35:43],
        "dv": chave[43:44]
    }


def validate_chave_acesso(chave):
    """
    Validate access key check digit using module 11.

    Args:
        chave: 44-digit access key

    Returns:
        bool: True if valid
    """
    chave = clean_chave(chave)

    if len(chave) != 44:
        return False

    if not chave.isdigit():
        return False

    # Calculate check digit (modulo 11)
    # Multiply digits 1-43 by weights 2-9 (repeating), right to left
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = 0

    for i in range(42, -1, -1):
        weight_idx = (42 - i) % 8
        total += int(chave[i]) * weights[weight_idx]

    remainder = total % 11

    # Check digit calculation
    # If remainder is 0 or 1, DV = 0
    # Otherwise, DV = 11 - remainder
    expected_dv = 0 if remainder < 2 else 11 - remainder

    return int(chave[43]) == expected_dv


def format_chave_acesso(chave):
    """
    Format chave de acesso with spaces for readability.

    Args:
        chave: 44-digit access key

    Returns:
        str: Formatted key (XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX XXXX)
    """
    chave = clean_chave(chave)

    if len(chave) != 44:
        return chave

    return " ".join([chave[i:i+4] for i in range(0, 44, 4)])


def get_document_type_from_modelo(modelo):
    """
    Get document type from the modelo code.

    Args:
        modelo: 2-digit modelo code

    Returns:
        str: Document type (NF-e, CT-e, NFS-e, etc.)
    """
    modelo_map = {
        "55": "NF-e",      # Nota Fiscal Eletronica
        "65": "NFC-e",     # Nota Fiscal de Consumidor Eletronica
        "57": "CT-e",      # Conhecimento de Transporte Eletronico
        "67": "CT-e OS",   # CT-e para Outros Servicos
        "58": "MDF-e",     # Manifesto Eletronico de Documentos Fiscais
        "99": "NFS-e"      # Nota Fiscal de Servico Eletronica (varies by municipality)
    }

    return modelo_map.get(modelo, "Unknown")


def get_uf_name(uf_code):
    """
    Get state name from UF code.

    Args:
        uf_code: 2-digit IBGE UF code

    Returns:
        str: State abbreviation
    """
    uf_map = {
        "11": "RO", "12": "AC", "13": "AM", "14": "RR",
        "15": "PA", "16": "AP", "17": "TO", "21": "MA",
        "22": "PI", "23": "CE", "24": "RN", "25": "PB",
        "26": "PE", "27": "AL", "28": "SE", "29": "BA",
        "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
        "41": "PR", "42": "SC", "43": "RS", "50": "MS",
        "51": "MT", "52": "GO", "53": "DF"
    }

    return uf_map.get(uf_code, "XX")


def get_tipo_emissao_name(tipo):
    """
    Get emission type name.

    Args:
        tipo: 1-digit emission type code

    Returns:
        str: Emission type description
    """
    tipo_map = {
        "1": "Normal",
        "2": "Contingencia FS-IA",
        "3": "Contingencia SCAN",
        "4": "Contingencia DPEC",
        "5": "Contingencia FS-DA",
        "6": "Contingencia SVC-AN",
        "7": "Contingencia SVC-RS",
        "9": "Contingencia Offline NFC-e"
    }

    return tipo_map.get(tipo, "Unknown")


def extract_info_from_chave(chave):
    """
    Extract human-readable information from chave de acesso.

    Args:
        chave: 44-digit access key

    Returns:
        dict: Human-readable information
    """
    parsed = parse_chave_acesso(chave)

    if not parsed:
        return None

    return {
        "estado": get_uf_name(parsed["uf"]),
        "ano": f"20{parsed['ano_mes'][:2]}",
        "mes": parsed["ano_mes"][2:4],
        "cnpj_formatado": f"{parsed['cnpj'][:2]}.{parsed['cnpj'][2:5]}.{parsed['cnpj'][5:8]}/{parsed['cnpj'][8:12]}-{parsed['cnpj'][12:14]}",
        "tipo_documento": get_document_type_from_modelo(parsed["modelo"]),
        "serie": parsed["serie"].lstrip("0") or "0",
        "numero": parsed["numero"].lstrip("0") or "0",
        "tipo_emissao": get_tipo_emissao_name(parsed["tipo_emissao"]),
        "codigo_numerico": parsed["codigo"],
        "digito_verificador": parsed["dv"],
        "valido": validate_chave_acesso(chave)
    }
