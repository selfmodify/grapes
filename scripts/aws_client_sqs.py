#!/bin/python

"""
AWS boto3 client for SQS
"""
import aws_client
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

class SqsClient(aws_client.AwsClient):
    """
    Client to create AWS SQS
    """

    def __init__(self, config):
        client = boto3.client('sqs', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)

    def maybe_create_sqs(self):
        """
        Create SQS if sqs name is not Null in the config file
        """
        if self.config.get_sqs() != None:
            self.create_sqs()

    def create_sqs(self):
        qname = self.config.create_name_with_separator(self.config.get_sqs())
        self.log.info('Env:%s Creating SQS:%s', self.config.get_env(), qname)
        q = self.client.create_queue(
            QueueName=qname
        )
        self.log.info("Finished creating queue: %s", q)
        self.set_sqs_permissions(q['QueueUrl'])

    def delete_sqs(self):
        qname = self.config.create_name_with_separator(self.config.get_sqs())
        self.log.info('Deleting SQS %s', qname)
        try:
            response = self.client.get_queue_url(
                QueueName=qname
            )
            if 'QueueUrl' in response:
                self.client.delete_queue(
                    QueueUrl=response['QueueUrl']
                )
            else:
                self.log.warn('SQS queue %s does not exist', qname)
        except Exception as e:
            self.log.warn('SQS queue %s does not exist. Error: %s', qname, e)

    def set_sqs_permissions(self, qurl):
        # q_parts = re.search('(\d+)/(.+)$', q.url)
        # aws_id = q_parts.group(1)
        # q_name = q_parts.group(2)
        # policy = {
        # "Version": "2012-10-17",
        # "Statement": [
        #     {
        #     "Effect": "Allow",
        #     # "Principal": {
        #     #     "Service": "mturk-requester.amazonaws.com"
        #     # },
        #     "Action": "*",
        #     "Resource": "arn:aws:sqs:us-east-1:{}:{}".format(aws_id, q_name),
        #     "Condition": {
        #         "Bool": {
        #         }
        #     }
        #     }
        # ]
        # }
        # p = sqsClient.meta.client.set_queue_attributes(QueueUrl=q.url, Attributes={'Policy': json.dumps(policy)})
        qname = self.config.create_name_with_separator(self.config.get_sqs())
        p = self.client.add_permission(
            QueueUrl=qurl,
            Label=qname,
            AWSAccountIds=self.config.get_sqs_account(),
            Actions=['*']
        )
        self.log.debug(
            "Setting permissions of %s to %s", qurl, p)
        return p

