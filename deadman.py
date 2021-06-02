#! /usr/bin/env python

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import boto3
import click
from botocore.config import Config
from tzlocal import get_localzone


def pet_aws_watchdog(client, s3_path: str) -> None:
    path_components = s3_path.split("/")
    assert len(path_components) == 2
    bucket = path_components[0]
    path = path_components[1]

    result = client.put_object(
        Body=datetime.now(timezone.utc).isoformat(),
        Bucket=bucket,
        Key=path,
    )
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200


def get_aws_watchdog(client, s3_path: str) -> datetime:
    path_components = s3_path.split("/")
    assert len(path_components) == 2
    bucket = path_components[0]
    path = path_components[1]

    result = client.get_object(
        Bucket=bucket,
        Key=path,
    )
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

    return datetime.fromisoformat(str(result["Body"].read(), "UTF-8"))


def send_aws_email_template(
    client,
    from_email: str,
    to_email: str,
    template: str,
    args: Dict[str, str],
) -> None:
    result = client.send_templated_email(
        Source=from_email,
        Template=template,
        TemplateData=json.dumps(args),
        Destination={"ToAddresses": [to_email]},
    )
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200


def set_aws_ciphertext(client, s3_path: str, ciphertext: str) -> None:
    path_components = s3_path.split("/")
    assert len(path_components) == 2
    bucket = path_components[0]
    path = path_components[1]

    result = client.put_object(
        Body=ciphertext,
        Bucket=bucket,
        Key=path,
    )
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200


def get_aws_ciphertext(client, s3_path: str) -> str:
    path_components = s3_path.split("/")
    assert len(path_components) == 2
    bucket = path_components[0]
    path = path_components[1]

    result = client.get_object(
        Bucket=bucket,
        Key=path,
    )
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

    return str(result["Body"].read(), "UTF-8")


@click.group()
def cli():
    pass


@cli.command()
def pet_watchdog() -> None:
    """Updates last seen timestamp in S3 bucket"""

    client = boto3.client("s3")
    s3_path = os.environ["DEADMAN_S3_PATH"]

    pet_aws_watchdog(client, s3_path)
    print("Watchdog petted!")


@cli.command()
def get_watchdog() -> None:
    """Updates last seen timestamp in S3 bucket"""

    client = boto3.client("s3")
    s3_path = os.environ["DEADMAN_S3_PATH"]

    print(get_aws_watchdog(client, s3_path).astimezone(get_localzone()))


@cli.command()
@click.argument("template", type=str)
@click.argument("arg_dict", type=str)
def send_email_template(template: str, arg_dict: str) -> None:
    """Send email template. Takes equal/comma delimited tuples for args"""

    args = {v.split("=")[0]: v.split("=")[1] for v in arg_dict.split(",")}

    email = os.environ["DEADMAN_SEND_EMAIL"]
    client = boto3.client("ses", config=Config(region_name="us-east-1"))
    send_aws_email_template(client, email, email, template, args)

    print("Email sent!")


@cli.command()
@click.option(
    "--timeout",
    default=7,
    help="number of days to wait before watchdog expires",
    show_default=True,
)
def check_watchdog(timeout: int) -> None:
    """Checks last seen timestamp in S3 bucket and emails if too old"""

    s3_client = boto3.client("s3")
    ses_client = boto3.client("ses", config=Config(region_name="us-east-1"))

    s3_path = os.environ["DEADMAN_S3_PATH"]
    ciphertext_s3_path = os.environ["DEADMAN_CIPHERTEXT_S3_PATH"]
    email = os.environ["DEADMAN_SEND_EMAIL"]
    template = os.environ["DEADMAN_EMAIL_TEMPLATE"]

    watchdog = get_aws_watchdog(s3_client, s3_path)
    now = datetime.now(timezone.utc)
    delta = now - watchdog

    if delta < timedelta(days=timeout):
        print(f"Watchdog not expired. Delta: {delta}")

        return

    print(f"Watchdog expired!!! Delta: {delta}")

    send_aws_email_template(
        ses_client,
        email,
        email,
        template,
        {
            "last_updated": watchdog.astimezone(get_localzone()).isoformat(),
            "ciphertext": get_aws_ciphertext(s3_client, ciphertext_s3_path),
        },
    )
    print("Email sent!")


@cli.command()
@click.argument("ciphertext", type=str)
def set_ciphertext(ciphertext: str) -> None:
    """Updates ciphertext in S3 bucket"""

    client = boto3.client("s3")
    s3_path = os.environ["DEADMAN_CIPHERTEXT_S3_PATH"]

    set_aws_ciphertext(client, s3_path, ciphertext)
    print("Ciphertext set!")


@cli.command()
def get_ciphertext() -> None:
    """Gets ciphertext from S3 bucket"""

    client = boto3.client("s3")
    s3_path = os.environ["DEADMAN_CIPHERTEXT_S3_PATH"]

    print(get_aws_ciphertext(client, s3_path))


if __name__ == "__main__":
    cli()
