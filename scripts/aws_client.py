#!/bin/python

"""
Returns the various kinds of AWS boto3 clients
"""
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options


class AwsClient():
    config = None
    client = None
    log = None

    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.log = logger.getLogger()

