#!/bin/python

"""
AWS boto3 client for API gateway
"""
import aws_client
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

class ApiGatewayClient(aws_client.AwsClient):
    config = None
    client = None
    log = None

    def __init__(self, config):
        client = boto3.client('apigateway', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)

    def create_get_api(self, name, description):
        response = self.client.create_rest_api(
            name=name,
            description=description,
            endpointConfiguration={
                'types': [
                    'REGIONAL'
                ]
            }
        )
        id = response['id']
        self.client.get_method(
            restApiId=id,
        )
        return response
