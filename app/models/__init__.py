"""SQLAlchemy ORM models.

Tenant models (Base) live in per-company tenant DBs.
Auth models (AuthBase) live in the central auth.db.
"""

# Tenant models (per-company DB)
from app.models.base import Base
from app.models.company_settings import CompanySettings
from app.models.property import Property
from app.models.room_template import RoomTemplate
from app.models.session import Session
from app.models.capture import Capture
from app.models.capture_image import CaptureImage
from app.models.annotation import Annotation
from app.models.comparison import Comparison
from app.models.candidate import Candidate
from app.models.tenant_link import TenantLink

# Auth models (central auth DB)
from app.models.auth_models import AuthBase, Company, User, UserSession, PasswordReset, Invite

__all__ = [
    # Tenant
    "Base", "CompanySettings", "Property", "RoomTemplate",
    "Session", "Capture", "CaptureImage", "Annotation", "Comparison",
    "Candidate", "TenantLink",
    # Auth
    "AuthBase", "Company", "User", "UserSession", "PasswordReset", "Invite",
]
