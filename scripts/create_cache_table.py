"""Create the DynamoDB cache table if it doesn't already exist.

Idempotent - safe to run against a fresh DynamoDB Local instance for local
dev, or against real AWS DynamoDB for a first-time production setup. Reads
DYNAMODB_CACHE_TABLE / DYNAMODB_ENDPOINT_URL from the same settings the app
itself uses.

    python -m scripts.create_cache_table
"""

import boto3
from botocore.exceptions import ClientError

from app.core.settings import settings


def main() -> None:
    # Only override credentials/region when talking to DynamoDB Local -
    # against real AWS, leave boto3's own default chain in charge so it
    # picks up real credentials (e.g. from `aws configure`) correctly.
    kwargs: dict[str, str] = {}
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
        if settings.AWS_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        if settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        if settings.AWS_DEFAULT_REGION:
            kwargs["region_name"] = settings.AWS_DEFAULT_REGION
    client = boto3.client("dynamodb", **kwargs)

    try:
        client.create_table(
            TableName=settings.DYNAMODB_CACHE_TABLE,
            KeySchema=[{"AttributeName": "cache_key", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "cache_key", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.get_waiter("table_exists").wait(TableName=settings.DYNAMODB_CACHE_TABLE)
        print(f"Created table {settings.DYNAMODB_CACHE_TABLE!r}.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceInUseException":
            raise
        print(f"Table {settings.DYNAMODB_CACHE_TABLE!r} already exists.")

    # DynamoDB's native TTL: items past their expires_at are eventually
    # (not immediately) deleted for free, as a storage-cost cleanup - the
    # app itself still checks expiry on read (see app/utils/cache.py) since
    # this deletion is best-effort and can lag up to 48h.
    try:
        client.update_time_to_live(
            TableName=settings.DYNAMODB_CACHE_TABLE,
            TimeToLiveSpecification={"AttributeName": "expires_at", "Enabled": True},
        )
        print("Enabled TTL on 'expires_at'.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationException":
            raise
        print("TTL already enabled.")


if __name__ == "__main__":
    main()
