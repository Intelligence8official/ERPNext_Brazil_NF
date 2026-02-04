"""
XML Parser for NF-e, CT-e, and NFS-e documents.

Adapted from NFSe_WebMonitor/xml_extractor.py with support for multiple schemas.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime

import frappe


# XML Namespaces
NAMESPACES = {
    "nfe": "http://www.portalfiscal.inf.br/nfe",
    "cte": "http://www.portalfiscal.inf.br/cte",
    "nfse_sped": "http://www.sped.fazenda.gov.br/nfse",
    "nfse_abrasf": "http://www.abrasf.org.br/nfse",
    "sig": "http://www.w3.org/2000/09/xmldsig#"
}


class NFXMLParser:
    """
    Parser for Brazilian electronic fiscal documents.

    Supports:
    - NF-e (Nota Fiscal Eletronica) - Products
    - CT-e (Conhecimento de Transporte Eletronico) - Transport
    - NFS-e (Nota Fiscal de Servico Eletronica) - Services (SPED and ABRASF)
    """

    def __init__(self):
        self.xml_content = None
        self.root = None
        self.document_type = None
        self.namespace = None

    def parse(self, xml_content):
        """
        Parse XML content and extract document data.

        Args:
            xml_content: XML string

        Returns:
            dict: Extracted document data
        """
        if not xml_content:
            return None

        self.xml_content = xml_content

        try:
            self.root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            frappe.log_error(f"XML Parse Error: {str(e)}", "XML Parser")
            return None

        # Detect document type and namespace
        self._detect_document_type()

        if not self.document_type:
            frappe.log_error("Could not detect document type", "XML Parser")
            return None

        # Parse based on document type
        if self.document_type == "NF-e":
            return self._parse_nfe()
        elif self.document_type == "CT-e":
            return self._parse_cte()
        elif self.document_type == "NFS-e":
            return self._parse_nfse()

        return None

    def _detect_document_type(self):
        """
        Detect document type from XML namespace or root element.
        """
        root_tag = self.root.tag.lower()
        root_ns = ""

        # Extract namespace from tag
        if "{" in self.root.tag:
            root_ns = self.root.tag.split("}")[0].strip("{")

        # Detect by namespace
        if "portalfiscal.inf.br/nfe" in root_ns or "nfe" in root_tag:
            self.document_type = "NF-e"
            self.namespace = NAMESPACES["nfe"]
        elif "portalfiscal.inf.br/cte" in root_ns or "cte" in root_tag:
            self.document_type = "CT-e"
            self.namespace = NAMESPACES["cte"]
        elif "sped.fazenda.gov.br/nfse" in root_ns:
            self.document_type = "NFS-e"
            self.namespace = NAMESPACES["nfse_sped"]
        elif "abrasf.org.br" in root_ns:
            self.document_type = "NFS-e"
            self.namespace = NAMESPACES["nfse_abrasf"]
        elif "nfse" in root_tag:
            self.document_type = "NFS-e"
            # Try to detect from content
            if "sped" in self.xml_content.lower():
                self.namespace = NAMESPACES["nfse_sped"]
            else:
                self.namespace = NAMESPACES["nfse_abrasf"]

    def _find_text(self, element, paths, default=""):
        """
        Find text using multiple XPath candidates.

        Args:
            element: XML element to search from
            paths: List of XPath expressions to try
            default: Default value if not found

        Returns:
            str: Found text or default
        """
        ns = {"n": self.namespace} if self.namespace else {}

        for path in paths:
            try:
                # Try with namespace
                result = element.find(path, ns)
                if result is not None and result.text:
                    return result.text.strip()

                # Try without namespace (for simple paths)
                if "/" not in path and ":" not in path:
                    for child in element.iter():
                        if child.tag.endswith(path) or child.tag == path:
                            if child.text:
                                return child.text.strip()
            except Exception:
                continue

        return default

    def _parse_nfe(self):
        """
        Parse NF-e (Nota Fiscal Eletronica) document.
        """
        data = {
            "document_type": "NF-e"
        }

        # Find infNFe element
        ns = {"n": self.namespace}
        inf_nfe = self.root.find(".//n:infNFe", ns)
        if inf_nfe is None:
            inf_nfe = self.root.find(".//{%s}infNFe" % self.namespace)
        if inf_nfe is None:
            # Try without namespace
            inf_nfe = self.root.find(".//infNFe")
        if inf_nfe is None:
            inf_nfe = self.root

        # Extract chave de acesso from Id attribute
        id_attr = inf_nfe.get("Id", "")
        if id_attr.startswith("NFe"):
            data["chave_de_acesso"] = id_attr[3:]

        # Identification
        data["numero"] = self._find_text(inf_nfe, [".//n:ide/n:nNF", ".//ide/nNF", "nNF"])
        data["serie"] = self._find_text(inf_nfe, [".//n:ide/n:serie", ".//ide/serie", "serie"])
        data["data_emissao"] = self._parse_date(
            self._find_text(inf_nfe, [".//n:ide/n:dhEmi", ".//ide/dhEmi", "dhEmi"])
        )

        # Emitente (Issuer)
        data["emitente_cnpj"] = self._find_text(inf_nfe, [".//n:emit/n:CNPJ", ".//emit/CNPJ", "CNPJ"])
        data["emitente_razao_social"] = self._find_text(inf_nfe, [".//n:emit/n:xNome", ".//emit/xNome", "xNome"])
        data["emitente_ie"] = self._find_text(inf_nfe, [".//n:emit/n:IE", ".//emit/IE"])
        data["emitente_uf"] = self._find_text(inf_nfe, [".//n:emit/n:enderEmit/n:UF", ".//emit/enderEmit/UF"])

        # Destinatario (Recipient)
        data["tomador_cnpj"] = self._find_text(inf_nfe, [".//n:dest/n:CNPJ", ".//dest/CNPJ"])
        data["tomador_razao_social"] = self._find_text(inf_nfe, [".//n:dest/n:xNome", ".//dest/xNome"])
        data["tomador_ie"] = self._find_text(inf_nfe, [".//n:dest/n:IE", ".//dest/IE"])

        # Totals
        data["valor_total"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vNF", ".//total/ICMSTot/vNF"])
        )
        data["valor_produtos"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vProd", ".//total/ICMSTot/vProd"])
        )
        data["valor_frete"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vFrete", ".//total/ICMSTot/vFrete"])
        )
        data["valor_desconto"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vDesc", ".//total/ICMSTot/vDesc"])
        )

        # Taxes
        data["valor_bc_icms"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vBC", ".//total/ICMSTot/vBC"])
        )
        data["valor_icms"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vICMS", ".//total/ICMSTot/vICMS"])
        )
        data["valor_ipi"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vIPI", ".//total/ICMSTot/vIPI"])
        )
        data["valor_pis"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vPIS", ".//total/ICMSTot/vPIS"])
        )
        data["valor_cofins"] = self._parse_currency(
            self._find_text(inf_nfe, [".//n:total/n:ICMSTot/n:vCOFINS", ".//total/ICMSTot/vCOFINS"])
        )

        # Parse items
        data["items"] = self._parse_nfe_items(inf_nfe)

        return data

    def _parse_nfe_items(self, inf_nfe):
        """
        Parse NF-e line items.
        """
        items = []
        ns = {"n": self.namespace}

        det_elements = inf_nfe.findall(".//n:det", ns)
        if not det_elements:
            det_elements = inf_nfe.findall(".//{%s}det" % self.namespace)
        if not det_elements:
            det_elements = inf_nfe.findall(".//det")

        for det in det_elements:
            item = {
                "numero_item": det.get("nItem"),
                "codigo_produto": self._find_text(det, [".//n:prod/n:cProd", ".//prod/cProd", "cProd"]),
                "codigo_barras": self._find_text(det, [".//n:prod/n:cEAN", ".//prod/cEAN", "cEAN"]),
                "descricao": self._find_text(det, [".//n:prod/n:xProd", ".//prod/xProd", "xProd"]),
                "ncm": self._find_text(det, [".//n:prod/n:NCM", ".//prod/NCM", "NCM"]),
                "cfop": self._find_text(det, [".//n:prod/n:CFOP", ".//prod/CFOP", "CFOP"]),
                "unidade": self._find_text(det, [".//n:prod/n:uCom", ".//prod/uCom", "uCom"]),
                "quantidade": self._parse_float(
                    self._find_text(det, [".//n:prod/n:qCom", ".//prod/qCom", "qCom"])
                ),
                "valor_unitario": self._parse_currency(
                    self._find_text(det, [".//n:prod/n:vUnCom", ".//prod/vUnCom", "vUnCom"])
                ),
                "valor_total": self._parse_currency(
                    self._find_text(det, [".//n:prod/n:vProd", ".//prod/vProd", "vProd"])
                )
            }

            # ICMS
            item["icms_cst"] = self._find_text(det, [".//n:imposto/n:ICMS//n:CST", ".//imposto/ICMS//CST"])
            item["icms_base_calculo"] = self._parse_currency(
                self._find_text(det, [".//n:imposto/n:ICMS//n:vBC", ".//imposto/ICMS//vBC"])
            )
            item["icms_aliquota"] = self._parse_float(
                self._find_text(det, [".//n:imposto/n:ICMS//n:pICMS", ".//imposto/ICMS//pICMS"])
            )
            item["icms_valor"] = self._parse_currency(
                self._find_text(det, [".//n:imposto/n:ICMS//n:vICMS", ".//imposto/ICMS//vICMS"])
            )

            items.append(item)

        return items

    def _parse_cte(self):
        """
        Parse CT-e (Conhecimento de Transporte Eletronico) document.
        """
        data = {
            "document_type": "CT-e"
        }

        # TODO: Implement CT-e parsing
        # Similar structure to NF-e but with transport-specific fields

        return data

    def _parse_nfse(self):
        """
        Parse NFS-e (Nota Fiscal de Servico Eletronica) document.

        Supports both SPED/Nacional and ABRASF formats.
        """
        data = {
            "document_type": "NFS-e"
        }

        ns = {"n": self.namespace}

        # Try SPED format first
        if "sped" in (self.namespace or "").lower():
            return self._parse_nfse_sped(data)
        else:
            return self._parse_nfse_abrasf(data)

    def _parse_nfse_sped(self, data):
        """
        Parse NFS-e in SPED/Nacional format.
        """
        ns = {"n": self.namespace}

        # Find infNFSe element
        inf_nfse = self.root.find(".//n:infNFSe", ns)
        if inf_nfse is None:
            inf_nfse = self.root

        # Extract ID for chave
        id_attr = inf_nfse.get("Id", "")
        if id_attr.startswith("NFS"):
            data["chave_de_acesso"] = id_attr[3:]

        # Identification
        data["numero"] = self._find_text(inf_nfse, ["n:nNFSe", "nNFSe"])
        data["data_emissao"] = self._parse_date(
            self._find_text(self.root, [".//n:DPS//n:dhEmi", ".//DPS//dhEmi", "dhEmi"])
        )

        # Emitente (Provider)
        data["emitente_cnpj"] = self._find_text(inf_nfse, [".//n:emit/n:CNPJ", ".//emit/CNPJ"])
        data["emitente_razao_social"] = self._find_text(inf_nfse, [".//n:emit/n:xNome", ".//emit/xNome"])
        data["emitente_im"] = self._find_text(self.root, [".//n:prest/n:IM", ".//prest/IM"])
        data["emitente_municipio"] = self._find_text(inf_nfse, [".//n:emit/n:enderNac/n:cMun", ".//emit/enderNac/cMun"])

        # Tomador (Taker)
        data["tomador_cnpj"] = self._find_text(self.root, [".//n:toma/n:CNPJ", ".//toma/CNPJ"])
        data["tomador_razao_social"] = self._find_text(self.root, [".//n:toma/n:xNome", ".//toma/xNome"])

        # Service classification
        data["codigo_tributacao_nacional"] = self._find_text(self.root, [".//n:cServ/n:cTribNac", ".//cServ/cTribNac"])
        data["codigo_tributacao_municipal"] = self._find_text(self.root, [".//n:cServ/n:cTribMun", ".//cServ/cTribMun"])
        data["codigo_nbs"] = self._find_text(self.root, [".//n:cServ/n:cNBS", ".//cServ/cNBS"])
        data["descricao_servico"] = self._find_text(self.root, [".//n:cServ/n:xDescServ", ".//cServ/xDescServ"])

        # Values
        data["valor_servicos"] = self._parse_currency(
            self._find_text(self.root, [".//n:vServPrest/n:vServ", ".//vServPrest/vServ"])
        )
        data["valor_total"] = data["valor_servicos"]

        # ISS
        data["valor_bc_issqn"] = self._parse_currency(
            self._find_text(inf_nfse, [".//n:valores/n:vBC", ".//valores/vBC"])
        )
        data["valor_issqn"] = self._parse_currency(
            self._find_text(inf_nfse, [".//n:valores/n:vISSQN", ".//valores/vISSQN"])
        )
        data["aliquota_issqn"] = self._parse_float(
            self._find_text(inf_nfse, [".//n:valores/n:pAliqAplic", ".//valores/pAliqAplic"])
        )
        data["valor_liquido"] = self._parse_currency(
            self._find_text(inf_nfse, [".//n:valores/n:vLiq", ".//valores/vLiq"])
        )

        # Tax totals
        data["valor_total_tributos_federais"] = self._parse_currency(
            self._find_text(self.root, [".//n:totTrib/n:vTotTribFed", ".//totTrib/vTotTribFed"])
        )
        data["valor_total_tributos_estaduais"] = self._parse_currency(
            self._find_text(self.root, [".//n:totTrib/n:vTotTribEst", ".//totTrib/vTotTribEst"])
        )
        data["valor_total_tributos_municipais"] = self._parse_currency(
            self._find_text(self.root, [".//n:totTrib/n:vTotTribMun", ".//totTrib/vTotTribMun"])
        )

        # Tax regime
        regime = self._find_text(self.root, [".//n:regTrib/n:opSimpNac", ".//regTrib/opSimpNac"])
        if regime:
            data["regime_simples_nacional"] = f"{regime} - {'MEI' if regime == '1' else 'Simples Nacional' if regime == '2' else 'Not Applicable'}"

        # Create item entry for the service
        # NFS-e typically has a single service, but we treat it as an item for processing
        data["items"] = [{
            "numero_item": "1",
            "codigo_produto": data.get("codigo_tributacao_nacional") or data.get("codigo_nbs") or "",
            "codigo_tributacao_nacional": data.get("codigo_tributacao_nacional"),
            "codigo_nbs": data.get("codigo_nbs"),
            "descricao": data.get("descricao_servico") or "Servico",
            "quantidade": 1,
            "valor_unitario": data.get("valor_servicos") or data.get("valor_total"),
            "valor_total": data.get("valor_servicos") or data.get("valor_total"),
            "unidade": "UN",
            "iss_base_calculo": data.get("valor_bc_issqn"),
            "iss_aliquota": data.get("aliquota_issqn"),
            "iss_valor": data.get("valor_issqn")
        }]

        return data

    def _parse_nfse_abrasf(self, data):
        """
        Parse NFS-e in ABRASF format.
        """
        # Similar structure but with different element names
        data["numero"] = self._find_text(self.root, [".//Numero", "Numero"])
        data["data_emissao"] = self._parse_date(
            self._find_text(self.root, [".//DataEmissao", "DataEmissao"])
        )

        # Provider
        data["emitente_cnpj"] = self._find_text(self.root, [".//Prestador//Cnpj", ".//Prestador/Cnpj"])
        data["emitente_im"] = self._find_text(self.root, [".//Prestador//InscricaoMunicipal"])
        data["emitente_razao_social"] = self._find_text(self.root, [".//Prestador//RazaoSocial"])

        # Taker
        data["tomador_cnpj"] = self._find_text(self.root, [".//Tomador//Cnpj"])
        data["tomador_razao_social"] = self._find_text(self.root, [".//Tomador//RazaoSocial"])

        # Service
        data["descricao_servico"] = self._find_text(self.root, [".//Servico//Discriminacao"])

        # Values
        data["valor_servicos"] = self._parse_currency(
            self._find_text(self.root, [".//Servico//Valores//ValorServicos"])
        )
        data["valor_total"] = data["valor_servicos"]

        data["valor_issqn"] = self._parse_currency(
            self._find_text(self.root, [".//Servico//Valores//ValorIss"])
        )
        data["aliquota_issqn"] = self._parse_float(
            self._find_text(self.root, [".//Servico//Valores//Aliquota"])
        )

        # Service code
        service_code = self._find_text(self.root, [".//Servico//ItemListaServico", ".//Servico//CodigoTributacaoMunicipio"])

        # Create item entry for the service
        data["items"] = [{
            "numero_item": "1",
            "codigo_produto": service_code or "",
            "descricao": data.get("descricao_servico") or "Servico",
            "quantidade": 1,
            "valor_unitario": data.get("valor_servicos") or data.get("valor_total"),
            "valor_total": data.get("valor_servicos") or data.get("valor_total"),
            "unidade": "UN",
            "iss_base_calculo": data.get("valor_bc_issqn"),
            "iss_aliquota": data.get("aliquota_issqn"),
            "iss_valor": data.get("valor_issqn")
        }]

        return data

    def _parse_date(self, date_str):
        """
        Parse date string to date object.
        """
        if not date_str:
            return None

        # Try ISO format with timezone
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                # Handle timezone with colon (e.g., -03:00)
                clean_date = date_str.replace(":", "").replace("T", " ")[:19]
                dt = datetime.strptime(clean_date, fmt.replace(":", "").replace("T", " ")[:19].replace("%z", ""))
                return dt.date()
            except ValueError:
                continue

        return None

    def _parse_currency(self, value_str):
        """
        Parse currency string to float.

        Handles both formats:
        - XML standard: 16800.00 (dot as decimal separator)
        - Brazilian format: 16.800,00 (dot as thousands, comma as decimal)
        """
        if not value_str:
            return 0.0

        try:
            value_str = value_str.strip()

            # Check if it's Brazilian format (has comma as decimal separator)
            if "," in value_str:
                # Brazilian format: 16.800,00 or 16800,00
                clean = value_str.replace(".", "").replace(",", ".")
                return float(clean)
            else:
                # XML/International format: 16800.00 or 16800
                # Don't remove dots - they are decimal separators
                return float(value_str)
        except ValueError:
            return 0.0

    def _parse_float(self, value_str):
        """
        Parse float string.
        """
        if not value_str:
            return 0.0

        try:
            return float(value_str.replace(",", "."))
        except ValueError:
            return 0.0
