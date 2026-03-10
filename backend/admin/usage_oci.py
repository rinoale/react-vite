from datetime import datetime, timedelta, timezone

import oci
from fastapi import APIRouter, HTTPException

from core.config import get_settings

router = APIRouter()


def _get_oci_config() -> dict:
    settings = get_settings()
    if not settings.oci_tenancy_ocid:
        raise HTTPException(status_code=501, detail="OCI credentials not configured")
    return {
        "user": settings.oci_user_ocid,
        "key_content": settings.oci_private_key.replace("\\n", "\n"),
        "fingerprint": settings.oci_fingerprint,
        "tenancy": settings.oci_tenancy_ocid,
        "region": settings.oci_region,
    }


@router.get("/usage/oci")
async def oci_usage():
    """Return current-month OCI cost breakdown by service."""
    cfg = _get_oci_config()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # OCI requires end date at midnight boundary (zero H/M/S)
    end_date = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    client = oci.usage_api.UsageapiClient(cfg)
    resp = client.request_summarized_usages(
        oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=cfg["tenancy"],
            time_usage_started=month_start,
            time_usage_ended=end_date,
            granularity="MONTHLY",
            query_type="COST",
            group_by=["service"],
        ),
    )

    services = []
    total = 0.0
    for item in resp.data.items:
        cost = item.computed_amount or 0.0
        currency = item.currency or "USD"
        service = (item.service or "Unknown")
        if cost == 0.0:
            continue
        services.append({
            "service": service,
            "cost": round(cost, 4),
            "currency": currency,
        })
        total += cost

    services.sort(key=lambda s: s["cost"], reverse=True)

    return {
        "period": now.strftime("%Y-%m"),
        "currency": services[0]["currency"] if services else "USD",
        "total": round(total, 4),
        "services": services,
    }
