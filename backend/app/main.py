from fastapi import Depends, FastAPI

from app.auth.dependencies import get_current_user

# Existing API routers
from app.api.shipments import router as shipments_router
from app.api.shipment_events import router as shipment_events_router
from app.api.documents import router as documents_router
from app.api.documents_validations import router as document_validations_router
from app.api.exceptions import router as exceptions_router
from app.api.agent_workflows import router as agent_workflows_router
from app.api.agent_runs import router as agent_runs_router
from app.api.auth import router as auth_router
from app.api.supervisor import router as supervisor_router
# New API routers
from app.api.investigations import router as investigations_router
from app.api.risk_assessments import router as risk_assessments_router
from app.api.resolution_plans import router as resolution_plans_router
from app.api.actions import router as actions_router
from app.api.audit_logs import router as audit_logs_router
from app.api.dashboard import router as dashboard_router
from app.api.risk_configurations import router as risk_configurations_router
from app.api import monitoring
from app.api.resolution_verifications import (
    router as resolution_verifications_router
)

app = FastAPI(
    title="CargoPilot 360",
    description="AI-powered Logistics Operations Management System",
    version="1.0.0"
)


# Require a valid login for every operational API router.
# The authentication router remains public so users can log in.
# Existing role-based dependencies on sensitive write operations
# continue to enforce their more restrictive permissions.
authenticated_router_dependencies = [
    Depends(get_current_user)
]

# Register existing API routers
app.include_router(
    shipments_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    shipment_events_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    documents_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    document_validations_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    exceptions_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    agent_workflows_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    agent_runs_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(auth_router)
app.include_router(
    risk_configurations_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    monitoring.router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    supervisor_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    resolution_verifications_router,
    dependencies=authenticated_router_dependencies
)

# Register additional API routers
app.include_router(
    investigations_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    risk_assessments_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    resolution_plans_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    actions_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    audit_logs_router,
    dependencies=authenticated_router_dependencies
)
app.include_router(
    dashboard_router,
    dependencies=authenticated_router_dependencies
)


@app.get("/")
def root():
    return {
        "message": "Welcome to CargoPilot 360!",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "CargoPilot 360"
    }
