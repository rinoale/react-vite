"""R2 and OCI usage queries."""
from datetime import datetime, timedelta, timezone

import httpx
import oci

from core.config import get_settings


# ── R2 (Cloudflare) ──

CF_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"

R2_FREE_TIER = {
    "storage_gb": 10,
    "class_a_ops": 1_000_000,
    "class_b_ops": 10_000_000,
}

_CLASS_A = {
    "PutObject", "CopyObject", "CompleteMultipartUpload", "CreateMultipartUpload",
    "UploadPart", "UploadPartCopy", "ListBuckets", "ListObjects", "ListObjectsV2",
    "ListMultipartUploads", "ListParts",
}


async def _query_cf(query: str, variables: dict) -> dict:
    settings = get_settings()
    if not settings.cloudflare_api_token:
        raise ValueError("Cloudflare API token not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            CF_GRAPHQL,
            headers={
                "Authorization": f"Bearer {settings.cloudflare_api_token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
            timeout=15,
        )
    data = resp.json()
    if resp.status_code != 200 or data.get("errors"):
        detail = data.get("errors", [{}])[0].get("message", resp.text)
        raise ValueError(f"Cloudflare API error: {detail}")
    return data["data"]


async def get_r2_usage():
    settings = get_settings()
    account_id = settings.r2_account_id
    if not account_id:
        raise ValueError("R2 account ID not configured")

    now = datetime.now(timezone.utc)
    month_start_date = now.strftime("%Y-%m-01")
    today_date = now.strftime("%Y-%m-%d")
    month_start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_dt = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    storage_query = """
    query ($accountTag: String!, $date_geq: Date!, $date_leq: Date!) {
      viewer {
        accounts(filter: { accountTag: $accountTag }) {
          r2StorageAdaptiveGroups(
            filter: { date_geq: $date_geq, date_leq: $date_leq }
            limit: 10
          ) {
            dimensions { bucketName }
            max { payloadSize objectCount }
          }
        }
      }
    }
    """

    ops_query = """
    query ($accountTag: String!, $date_geq: DateTime!, $date_leq: DateTime!) {
      viewer {
        accounts(filter: { accountTag: $accountTag }) {
          r2OperationsAdaptiveGroups(
            filter: { datetime_geq: $date_geq, datetime_leq: $date_leq }
            limit: 100
          ) {
            dimensions { actionType }
            sum { requests }
          }
        }
      }
    }
    """

    storage_data = await _query_cf(storage_query, {
        "accountTag": account_id,
        "date_geq": month_start_date,
        "date_leq": today_date,
    })
    ops_data = await _query_cf(ops_query, {
        "accountTag": account_id,
        "date_geq": month_start_dt,
        "date_leq": now_dt,
    })

    storage_rows = (
        storage_data.get("viewer", {}).get("accounts", [{}])[0]
        .get("r2StorageAdaptiveGroups", [])
    )
    total_bytes = sum(row.get("max", {}).get("payloadSize", 0) for row in storage_rows)
    total_objects = sum(row.get("max", {}).get("objectCount", 0) for row in storage_rows)

    ops_rows = (
        ops_data.get("viewer", {}).get("accounts", [{}])[0]
        .get("r2OperationsAdaptiveGroups", [])
    )
    class_a = 0
    class_b = 0
    for row in ops_rows:
        action = row.get("dimensions", {}).get("actionType", "")
        count = row.get("sum", {}).get("requests", 0)
        if action in _CLASS_A:
            class_a += count
        else:
            class_b += count

    storage_gb = total_bytes / (1024 ** 3)

    return {
        "period": now.strftime("%Y-%m"),
        "storage": {
            "used_bytes": total_bytes,
            "used_gb": round(storage_gb, 3),
            "limit_gb": R2_FREE_TIER["storage_gb"],
            "pct": round(storage_gb / R2_FREE_TIER["storage_gb"] * 100, 1),
            "objects": total_objects,
        },
        "class_a_ops": {
            "used": class_a,
            "limit": R2_FREE_TIER["class_a_ops"],
            "pct": round(class_a / R2_FREE_TIER["class_a_ops"] * 100, 1),
        },
        "class_b_ops": {
            "used": class_b,
            "limit": R2_FREE_TIER["class_b_ops"],
            "pct": round(class_b / R2_FREE_TIER["class_b_ops"] * 100, 1),
        },
    }


# ── OCI ──

def _get_oci_config() -> dict:
    settings = get_settings()
    if not settings.oci_tenancy_ocid:
        raise ValueError("OCI credentials not configured")
    return {
        "user": settings.oci_user_ocid,
        "key_content": settings.oci_private_key.replace("\\n", "\n"),
        "fingerprint": settings.oci_fingerprint,
        "tenancy": settings.oci_tenancy_ocid,
        "region": settings.oci_region,
    }


def get_oci_usage():
    cfg = _get_oci_config()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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
        service = item.service or "Unknown"
        if cost == 0.0:
            continue
        services.append({"service": service, "cost": round(cost, 4), "currency": currency})
        total += cost

    services.sort(key=lambda s: s["cost"], reverse=True)

    return {
        "period": now.strftime("%Y-%m"),
        "currency": services[0]["currency"] if services else "USD",
        "total": round(total, 4),
        "services": services,
    }
