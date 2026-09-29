class VisaITL1Error(Exception):
    """Base package exception."""

class SchemaError(VisaITL1Error):
    """Required columns or configured fields are invalid."""

class GeographyError(VisaITL1Error):
    """Postcode or geography processing failed."""

class ReconciliationError(VisaITL1Error):
    """Allocated values do not reconcile to input controls."""
