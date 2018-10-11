#!/usr/bin/python
"""
Creates the AWS SQS for use by the backend services

"""

import argparse
import os
import sys
import json
import aws_client_sqs
import re
import arg_parser


def setup_and_parse_args():
    parser = arg_parser.create_parser(desc="""
    Setup AWS SQS in the specified environment/region. Environment implies both region and its use case

    Example usage:
    python ./sqs_create.py --file=<config-file.yaml>        # (region us-east-1, developer environment)
    """)
    return arg_parser.parse_config_from_args(parser)


def maybe_create_sqs(config):
    """
    Create SQS for the cluster.
    """
    sqs_client = aws_client_sqs.SqsClient(config)
    sqs_client.maybe_create_sqs()


def delete_sqs(config):
    sqs_client = aws_client_sqs.SqsClient(config)
    sqs_client.delete_sqs()


def __main__():
    config, _ = setup_and_parse_args()
    maybe_create_sqs(config)


if __name__ == "__main__":
    __main__()
