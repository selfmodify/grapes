#!/usr/bin/python
"""
Creates the API

"""

import argparse
import aws_client_api_gateway
import service_env
import string
import arg_parser

def setup_and_parse_args():
    parser = arg_parser.create_parser(desc="""
    Setup API Gateway in the specified region. Environment implies both region and its use case

    Example usage:
    python ./api_create.py --file=<config-file.yaml>        # (region us-east-1, developer environment)
    """)
    return arg_parser.parse_config_from_args(parser)

def __main__():
    config = setup_and_parse_args()
    api_client = aws_client_api_gateway.ApiGatewayClient(config)
    print api_client.create_get_api('/version', 'Something')

if __name__ == "__main__":
    __main__()
