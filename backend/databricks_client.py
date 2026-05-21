"""Centralized Databricks SDK + token helpers (dual-mode: in-app vs local CLI profile)."""
import os
from functools import lru_cache

from databricks.sdk import WorkspaceClient


@lru_cache
def get_workspace_client() -> WorkspaceClient:
    if os.environ.get("DATABRICKS_APP_NAME"):
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
    return WorkspaceClient(profile=profile)


def get_oauth_token() -> str:
    """Return a generic Databricks API token (Bearer)."""
    client = get_workspace_client()
    headers = client.config.authenticate()
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return client.config.token or ""


def get_lakebase_token(instance_name: str = "rcw-lakebase") -> str:
    """Return a Lakebase-specific Postgres JWT credential.

    Lakebase Postgres rejects plain API tokens — it requires a JWT minted via
    `database.generate_database_credential`. In the Databricks Apps runtime the
    `PGPASSWORD` env var is auto-populated with this token; outside the app we
    mint one on demand.
    """
    import os
    cached = os.environ.get("PGPASSWORD")
    if cached:
        return cached
    client = get_workspace_client()
    # SDK versions differ; try the modern path first
    try:
        cred = client.database.generate_database_credential(
            request_id=f"rcw-{instance_name}", instance_names=[instance_name]
        )
        token = getattr(cred, "token", None)
        if token:
            return token
    except Exception:
        pass
    # Fallback: some SDKs expose this on a sub-resource
    try:
        cred = client.database.generate_database_credential(  # type: ignore[call-arg]
            request_id=f"rcw-{instance_name}", instance_name=instance_name
        )
        token = getattr(cred, "token", None) or getattr(cred, "credential", None)
        if token:
            return token
    except Exception:
        pass
    # Last resort: return the generic OAuth token (works inside apps with auto-populated PGPASSWORD)
    return get_oauth_token()


def get_workspace_host() -> str:
    if os.environ.get("DATABRICKS_APP_NAME"):
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    return get_workspace_client().config.host


def get_current_user_email() -> str:
    if os.environ.get("DATABRICKS_APP_NAME"):
        return os.environ.get("DATABRICKS_USER_EMAIL", "anonymous@databricks.com")
    return get_workspace_client().current_user.me().user_name or "anonymous@databricks.com"
