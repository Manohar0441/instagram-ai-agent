import boto3

from app.core.settings import settings

_table = None


def get_cache_table():
    """Return a lazily-created, process-wide DynamoDB Table resource.

    endpoint_url is None in production (Lambda), pointing boto3 at the real
    AWS endpoint; local dev/tests set DYNAMODB_ENDPOINT_URL at a local
    DynamoDB instance instead.

    Credentials/region are only overridden when talking to that local
    endpoint. In production, Lambda's execution role provides temporary STS
    credentials via three env vars (access key, secret key, *and* a session
    token) - overriding just the first two here (which is what the
    AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY settings fields would otherwise
    pick up, since Lambda sets those as real env vars and pydantic-settings
    reads real env vars first) drops the session token and breaks auth with
    "the security token included in the request is invalid". Leaving
    boto3's own default chain in charge picks up all three correctly.
    """
    global _table
    if _table is None:
        kwargs: dict[str, str] = {}
        if settings.DYNAMODB_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
            if settings.AWS_ACCESS_KEY_ID:
                kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            if settings.AWS_SECRET_ACCESS_KEY:
                kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
            if settings.AWS_DEFAULT_REGION:
                kwargs["region_name"] = settings.AWS_DEFAULT_REGION
        resource = boto3.resource("dynamodb", **kwargs)
        _table = resource.Table(settings.DYNAMODB_CACHE_TABLE)
    return _table
