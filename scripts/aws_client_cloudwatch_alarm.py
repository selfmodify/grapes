#!/bin/python

"""
AWS boto3 client for cloud watch
"""
import aws_client
import aws_client_elb
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

class CloudWatchAlarm(aws_client.AwsClient):
    def __init__(self, config):
        client = boto3.client('cloudwatch', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)
        self.alarm = self.config.get_alarm()

    def put_elb_unhealthy_alarm(self):
        """
        Put the Alarm on the LB. The alarm should be created using the EC2 console
        """
        alarm_name = self.config.get_alarm_name()
        # Find the LB and Target
        elb_client = aws_client_elb.ElbClient(self.config)
        grape_lb_arn, grape_tg_arn = elb_client.get_lb_and_tg()
        response = self.client.put_metric_alarm(
            AlarmName=alarm_name,
            AlarmDescription=self.alarm['description'],
            ActionsEnabled=self.alarm['enabled'],
            AlarmActions=[
                self.config.get_alarm_action(),
            ],

            MetricName='UnHealthyHostCount',
            Namespace='AWS/ApplicationELB',
            Statistic='Average',
            Dimensions=[
                {
                    'Name': 'LoadBalancer',
                    'Value': grape_lb_arn,
                },
                {
                    'Name': 'TargetGroup',
                    'Value': grape_tg_arn,
                }
            ],
            Period=60,
            Unit='Count',
            ComparisonOperator='GreaterThanThreshold',
            Threshold=0,
            EvaluationPeriods=1,
        )
        return response
