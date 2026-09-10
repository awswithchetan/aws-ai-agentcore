#!/usr/bin/env python3
"""Validate the IAM-protected ShopSmart API with SigV4-signed requests.

The script uses the standard boto3/botocore credential chain. The caller must
have execute-api:Invoke permission for the deployed API stage.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError, NoCredentialsError


@dataclass(frozen=True)
class Check:
    name: str
    method: str
    path: str
    query: dict[str, str] | None = None


CHECKS = (
    Check("list orders", "GET", "/orders", {"customerId": "C001"}),
    Check("get order", "GET", "/orders/ORD-1001"),
    Check("search products", "GET", "/products", {"q": "backpack"}),
)


def signed_request(
    session: boto3.Session,
    method: str,
    url: str,
    region: str,
) -> tuple[int, Any]:
    credentials = session.get_credentials()
    if credentials is None:
        raise NoCredentialsError()
    frozen = credentials.get_frozen_credentials()

    request = AWSRequest(method=method, url=url)
    SigV4Auth(frozen, "execute-api", region).add_auth(request)
    prepared = request.prepare()

    import urllib.request
    import urllib.error

    http_request = urllib.request.Request(
        prepared.url,
        method=prepared.method,
        headers=dict(prepared.headers),
    )
    try:
        with urllib.request.urlopen(http_request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
        return error.code, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="API URL including stage")
    parser.add_argument("--region", required=True, help="AWS Region of the API")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    session = boto3.Session(region_name=args.region)
    failed = False

    try:
        caller = session.client("sts").get_caller_identity()
        print(f"Using IAM principal: {caller['Arn']}")
    except (BotoCoreError, NoCredentialsError) as error:
        print(f"Unable to resolve AWS credentials: {error}", file=sys.stderr)
        return 2

    for check in CHECKS:
        query = f"?{urlencode(check.query)}" if check.query else ""
        url = f"{base_url}{check.path}{query}"
        try:
            status, body = signed_request(session, check.method, url, args.region)
        except (BotoCoreError, NoCredentialsError, OSError) as error:
            print(f"FAIL {check.name}: {error}", file=sys.stderr)
            failed = True
            continue

        if status // 100 == 2:
            print(f"PASS {check.name}: HTTP {status}")
        else:
            print(f"FAIL {check.name}: HTTP {status} — {body}", file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
