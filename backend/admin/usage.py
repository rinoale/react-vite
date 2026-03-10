from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from core.config import get_settings

router = APIRouter()

CF_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"

R2_FREE_TIER = {
    "storage_gb": 10,
    "class_a_ops": 1_000_000,
    "class_b_ops": 10_000_000,
}


async def _query_cf(query: str, variables: dict) -> dict:
    settings = get_settings()
    if not settings.cloudflare_api_token:
        raise HTTPException(status_code=501, detail="Cloudflare API token not configured")

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
        raise HTTPException(status_code=502, detail=f"Cloudflare API error: {detail}")
    return data["data"]


@router.get("/usage/r2")
async def r2_usage():
    """Return current-month R2 storage and operation counts vs free tier limits."""
    settings = get_settings()
    account_id = settings.r2_account_id
    if not account_id:
        raise HTTPException(status_code=501, detail="R2 account ID not configured")

    now = datetime.now(timezone.utc)
    month_start_date = now.strftime("%Y-%m-01")
    today_date = now.strftime("%Y-%m-%d")
    month_start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    now_dt = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Storage query — aggregate over current month (uses Date! filters)
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

    # Operations query — sum over current month (uses DateTime! filters)
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

    # Parse storage
    storage_rows = (
        storage_data.get("viewer", {}).get("accounts", [{}])[0]
        .get("r2StorageAdaptiveGroups", [])
    )
    total_bytes = sum(row.get("max", {}).get("payloadSize", 0) for row in storage_rows)
    total_objects = sum(row.get("max", {}).get("objectCount", 0) for row in storage_rows)

    # Parse operations
    CLASS_A = {"PutObject", "CopyObject", "CompleteMultipartUpload", "CreateMultipartUpload",
               "UploadPart", "UploadPartCopy", "ListBuckets", "ListObjects", "ListObjectsV2",
               "ListMultipartUploads", "ListParts"}
    ops_rows = (
        ops_data.get("viewer", {}).get("accounts", [{}])[0]
        .get("r2OperationsAdaptiveGroups", [])
    )
    class_a = 0
    class_b = 0
    for row in ops_rows:
        action = row.get("dimensions", {}).get("actionType", "")
        count = row.get("sum", {}).get("requests", 0)
        if action in CLASS_A:
            class_a += count
        else:
            class_b += count

    storage_gb = total_bytes / (1024 ** 3)

    return {
        "period": f"{now.strftime('%Y-%m')}",
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
