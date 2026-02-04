"""
Certificate utilities for handling PFX/PKCS12 digital certificates.

Adapted from NFSe_WebMonitor/cert_utils.py with additional validation.
"""

import tempfile
import os
from datetime import datetime, timezone

import frappe
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    NoEncryption,
)
from cryptography import x509


def resolve_frappe_file_path(file_url: str) -> str:
    """
    Resolve a Frappe file URL to an absolute file path.

    Args:
        file_url: File URL like /files/cert.pfx or /private/files/cert.pfx

    Returns:
        str: Absolute file path
    """
    if not file_url:
        raise ValueError("File path is empty")

    # If it's already an absolute path and exists, return it
    if os.path.isabs(file_url) and os.path.exists(file_url):
        return file_url

    # Remove leading slash for path joining
    clean_path = file_url.lstrip("/")

    # Try different path resolutions
    possible_paths = []

    # Standard Frappe file paths
    if clean_path.startswith("files/") or clean_path.startswith("private/files/"):
        possible_paths.append(frappe.get_site_path(clean_path))

    # If path starts with /files/ or /private/files/
    if file_url.startswith("/files/"):
        possible_paths.append(frappe.get_site_path("public", file_url[1:]))
        possible_paths.append(frappe.get_site_path(file_url[1:]))

    if file_url.startswith("/private/files/"):
        possible_paths.append(frappe.get_site_path(file_url[1:]))

    # Try to get from File doctype
    try:
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        if file_doc and file_doc.get_full_path():
            possible_paths.insert(0, file_doc.get_full_path())
    except Exception:
        pass

    # Try each possible path
    for path in possible_paths:
        if path and os.path.exists(path):
            return path

    # If nothing worked, raise an error with debug info
    raise FileNotFoundError(
        f"Could not resolve file path: {file_url}. "
        f"Tried: {possible_paths}"
    )


def get_pfx_bytes_from_file(file_path: str) -> bytes:
    """
    Get PFX file content as bytes, handling Frappe file URLs.

    Args:
        file_path: File path or Frappe file URL

    Returns:
        bytes: PFX file content
    """
    resolved_path = resolve_frappe_file_path(file_path)

    with open(resolved_path, "rb") as f:
        return f.read()


def extract_cert_and_key_from_pfx_bytes(pfx_bytes: bytes, password: str) -> tuple:
    """
    Extract certificate and private key from PFX bytes.

    Args:
        pfx_bytes: PFX file content as bytes
        password: Password to unlock the PFX

    Returns:
        tuple: (cert_path, key_path) - Paths to temporary PEM files

    Raises:
        ValueError: If PFX doesn't contain valid certificate/key
    """
    key, cert, _chain = load_key_and_certificates(
        pfx_bytes,
        password.encode("utf-8") if password else None
    )

    if cert is None or key is None:
        raise ValueError("PFX does not contain a certificate and private key")

    cert_pem = cert.public_bytes(Encoding.PEM)
    key_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    # Create temporary files
    certfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    keyfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")

    certfile.write(cert_pem)
    keyfile.write(key_pem)
    certfile.close()
    keyfile.close()

    return certfile.name, keyfile.name


def extract_cert_and_key_from_file(file_path: str, password: str) -> tuple:
    """
    Extract certificate and private key from a PFX file.

    Args:
        file_path: Path to the PFX file (can be Frappe file URL)
        password: Password to unlock the PFX

    Returns:
        tuple: (cert_path, key_path) - Paths to temporary PEM files
    """
    pfx_bytes = get_pfx_bytes_from_file(file_path)
    return extract_cert_and_key_from_pfx_bytes(pfx_bytes, password)


def validate_pfx_certificate(file_path: str, password: str) -> str:
    """
    Validate a PFX certificate and return its expiry date.

    Args:
        file_path: Path to the PFX file
        password: Password to unlock the PFX

    Returns:
        str: Expiry date in YYYY-MM-DD format

    Raises:
        ValueError: If certificate is invalid or expired
    """
    pfx_bytes = get_pfx_bytes_from_file(file_path)

    try:
        key, cert, _chain = load_key_and_certificates(
            pfx_bytes,
            password.encode("utf-8") if password else None
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "mac" in error_msg or "pkcs12" in error_msg:
            raise ValueError(
                "Invalid password or the file is not a valid PFX/P12 certificate. "
                "Please verify the password and ensure the file is a valid digital certificate."
            )
        raise

    if cert is None:
        raise ValueError("PFX does not contain a certificate")

    if key is None:
        raise ValueError("PFX does not contain a private key")

    # Check expiry
    expiry = cert.not_valid_after_utc
    now = datetime.now(timezone.utc)

    if expiry < now:
        raise ValueError(f"Certificate expired on {expiry.strftime('%Y-%m-%d')}")

    # Check if certificate is valid yet
    not_before = cert.not_valid_before_utc
    if now < not_before:
        raise ValueError(f"Certificate not valid until {not_before.strftime('%Y-%m-%d')}")

    return expiry.strftime("%Y-%m-%d")


def get_certificate_info(file_path: str, password: str) -> dict:
    """
    Get detailed information about a PFX certificate.

    Args:
        file_path: Path to the PFX file
        password: Password to unlock the PFX

    Returns:
        dict: Certificate information
    """
    pfx_bytes = get_pfx_bytes_from_file(file_path)

    try:
        key, cert, chain = load_key_and_certificates(
            pfx_bytes,
            password.encode("utf-8") if password else None
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "mac" in error_msg or "pkcs12" in error_msg:
            raise ValueError(
                "Invalid password or the file is not a valid PFX/P12 certificate."
            )
        raise

    if cert is None:
        raise ValueError("PFX does not contain a certificate")

    # Extract subject information
    subject = cert.subject
    subject_dict = {}

    for attr in subject:
        oid_name = attr.oid._name
        subject_dict[oid_name] = attr.value

    # Extract issuer information
    issuer = cert.issuer
    issuer_dict = {}

    for attr in issuer:
        oid_name = attr.oid._name
        issuer_dict[oid_name] = attr.value

    # Extract CNPJ/CPF from subject if available
    cnpj_cpf = None
    common_name = subject_dict.get("commonName", "")
    if ":" in common_name:
        # Format: "Name:CNPJ" or similar
        parts = common_name.split(":")
        if len(parts) > 1:
            cnpj_cpf = parts[-1].strip()

    now = datetime.now(timezone.utc)
    expiry = cert.not_valid_after_utc
    not_before = cert.not_valid_before_utc

    return {
        "subject": subject_dict,
        "issuer": issuer_dict,
        "common_name": common_name,
        "cnpj_cpf": cnpj_cpf,
        "serial_number": str(cert.serial_number),
        "not_valid_before": not_before.strftime("%Y-%m-%d %H:%M:%S"),
        "not_valid_after": expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "is_valid": not_before <= now <= expiry,
        "is_expired": now > expiry,
        "days_until_expiry": (expiry - now).days if now < expiry else 0,
        "has_chain": chain is not None and len(chain) > 0,
        "chain_length": len(chain) if chain else 0
    }


def cleanup_temp_files(*file_paths):
    """
    Clean up temporary certificate/key files.

    Args:
        *file_paths: Paths to files to delete
    """
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass


class CertificateContext:
    """
    Context manager for handling certificate extraction and cleanup.

    Usage:
        with CertificateContext(file_path, password) as (cert_path, key_path):
            # Use cert_path and key_path
            requests.get(url, cert=(cert_path, key_path))
        # Files are automatically cleaned up
    """

    def __init__(self, file_path: str, password: str):
        self.file_path = file_path
        self.password = password
        self.cert_path = None
        self.key_path = None

    def __enter__(self):
        self.cert_path, self.key_path = extract_cert_and_key_from_file(
            self.file_path,
            self.password
        )
        return self.cert_path, self.key_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        cleanup_temp_files(self.cert_path, self.key_path)
        return False
