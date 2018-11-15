#!/bin/python

"""
AWS boto3 client for ELB
"""
import aws_client
import boto3
from botocore.exceptions import ClientError

class ElbClient(aws_client.AwsClient):
    """
    Client for Elastic Load Balancer.
    """

    def __init__(self, config):
        client = boto3.client('elbv2', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)
        self.lb = None
        self.tg = None
        self.lb_arn = None
        self.tg_arn = None
        self.listener_arn = None

    def get_lb_details(self):
        lb_name = self.config.get_lb_name()
        lb_arn = None
        dns_name = None
        try:
            load_balancers = self.client.describe_load_balancers(Names=[
                lb_name,
            ])
            for lb in load_balancers:
                # Return the first LoadBalancer.
                lb_info = load_balancers[lb][0]
                lb_arn = lb_info['LoadBalancerArn']
                dns_name = lb_info['DNSName']
                break
        except Exception as ex:
            self.log.debug("Could not find LB: %s", ex)
        return lb_arn, dns_name

    def get_first_matching_target_group(self, lb_arn):
        response = self.client.describe_target_groups(
            LoadBalancerArn=lb_arn,
        )
        # Return the first TargetGroup.
        target_groups = response['TargetGroups']
        if len(target_groups) > 0:
            return target_groups[0]
        return None

    def update_load_balancer_settings(self):
        # Modify the LB timeout attributes if one was provided
        lb_arn, _dns_name = self.get_lb_details()
        lb_idle_timeout = self.config.get_lb_timeouts()
        attributes = []
        if lb_idle_timeout != None:
            attributes.append({
                'Key': 'idle_timeout.timeout_seconds',
                'Value': str(lb_idle_timeout),
            })
        if len(attributes):
            self.log.info('Setting LB attributes:%s LBName:%s',
                          attributes, self.config.get_lb_name())
            self.client.modify_load_balancer_attributes(
                LoadBalancerArn=lb_arn,
                Attributes=attributes,
            )

    def create_load_balancer(self):
        type = self.config.get_lb_type()
        kwargs = {}
        if type == 'network':
            kwargs = {
                'Name': self.config.get_lb_name(),
                'Type': self.config.get_lb_type(),
                'Subnets': self.config.get_subnets(),
                'Scheme': self.config.get_lb_scheme(),
            }
        else:
            kwargs = {
                'Name': self.config.get_lb_name(),
                'Type': self.config.get_lb_type(),
                'Subnets': self.config.get_subnets(),
                'SecurityGroups': self.config.get_security_groups(),
                'Scheme': self.config.get_lb_scheme(),
            }
        response = self.client.create_load_balancer(**kwargs)
        # log some information
        self.log.info('LB creation response: %s', response)
        the_lb = None
        for lb in response['LoadBalancers']:
            self.lb_arn = lb['LoadBalancerArn']
            self.log.info("Created/Updated LoadBalancer: LBName:%s LBArn:%s ",
                          lb['LoadBalancerName'], self.lb_arn)
            the_lb = lb  # There should only be one entry in the returned response array
            break
        return the_lb

    def delete_lb_and_friends(self):
        lb_name = self.config.get_lb_name()
        # Get LB details and then delete it.
        lbarn, _dns_name = self.get_lb_details()
        if lbarn is not None:
            response = self.client.describe_listeners(
                LoadBalancerArn=lbarn
            )
            # Delete all listeners on that LB
            for listener in response['Listeners']:
                self.log.info('Deleteing LB Listener. %s',
                              listener['ListenerArn'])
                self.client.delete_listener(
                    ListenerArn=listener['ListenerArn']
                )
            self.log.info('Delete LB. %s', lb_name)
            self.client.delete_load_balancer(LoadBalancerArn=lbarn)
        else:
            self.log.info('LB %s not found', lb_name)
        # Get target group details and delete it.
        tg_name = self.config.get_tg_name()
        elb_client = ElbClient(self.config)
        try:
            response = elb_client.client.describe_target_groups(
                Names=[
                    tg_name
                ]
            )
            for tg in response['TargetGroups']:
                self.log.info('Deleting TargetGroup %s', tg['TargetGroupName'])
                elb_client.client.delete_target_group(
                    TargetGroupArn=tg['TargetGroupArn']
                )
        except ClientError as e:
            self.log.warn(
                'Target group %s may have been already deleted. Error: %s', tg_name, e)
            pass

    def create_lb_and_friends(self):
        """
        Create LB, TargetGroup and Listeners from the configuration
        """
        # TODO: Subnets, 'Security Groups', VPC should be created and elsewhere and passed on here.
        lb_arn, _dns_name = self.get_lb_details()
        if lb_arn is None:
            # create a new LB
            lb_arn = self.create_load_balancer()
            lb_arn = lb_arn['LoadBalancerArn']
        self.update_load_balancer_settings()
        tg = self.create_or_update_target_group()
        self.create_load_balancer_listeners(lb_arn, tg)

    def create_load_balancer_listeners(self,
                                       lb_arn,
                                       target_group,
                                       ):
        # TODO :Create TargetGroup before creating listener.
        self.lb_arn = lb_arn
        self.tg_arn = target_group['TargetGroupArn']
        port, protocol = self.config.get_main_listener_info()
        response = self.client.create_listener(
            LoadBalancerArn=self.lb_arn,
            Protocol=protocol,
            Port=port,
            DefaultActions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': self.tg_arn,
                }
            ]
        )

        alt_listeners = self.config.get_alt_listener_infos()
        self.log.info(alt_listeners)
        if alt_listeners is not None:
            for listener in alt_listeners:
                self.log.info(listener)
                certs = []
                if listener['cert_arn'] is not None:
                    certs = [
                    {
                        'CertificateArn': listener['cert_arn']
                    }
                ]
                response = self.client.create_listener(
                    LoadBalancerArn=self.lb_arn,
                    Protocol=listener['protocol'],
                    Port=listener['port'],
                    Certificates=certs,
                    DefaultActions=[
                        {
                            'Type': 'forward',
                            'TargetGroupArn': self.tg_arn,
                        }
                    ]
                )

        # log some information
        self.log.debug("LBListeners: %s", response)
        for listener in response['Listeners']:
            for action in listener['DefaultActions']:
                self.listener_arn = listener['LoadBalancerArn']
                self.log.info("Created/Updated LBListener: LBArn:%s TargetGroupArn:%s",
                              self.listener_arn, action['TargetGroupArn'])

        return response

    def create_or_update_target_group(self):
        tg_name = self.config.get_tg_name()
        tg_protocol = self.config.get_tg_protocol()
        port, path, healthy_threshold, healthy_check_interval = self.config.get_tg_health_check_info()
        kwargs = {}
        try:
            # If there is one that already exists then modify that
            response = self.client.describe_target_groups(
                Names=[
                    tg_name,
                ]
            )
            # Modify the existing one. Only some parameters can be modified without
            # taking down the entire TG/LB/Listeners.
            tg_arn = response['TargetGroups'][0]['TargetGroupArn']
            if tg_protocol == 'TCP':
                kwargs = {
                    'TargetGroupArn': tg_arn,
                    'HealthCheckIntervalSeconds': healthy_check_interval,
                    'HealthyThresholdCount': healthy_threshold,
                    'UnhealthyThresholdCount': healthy_threshold,
                }
            else:
                kwargs = {
                    'TargetGroupArn': tg_arn,
                    'HealthCheckPath': path,
                    'HealthCheckIntervalSeconds': healthy_check_interval,
                    'HealthyThresholdCount': healthy_threshold,
                }
            response = self.client.modify_target_group(**kwargs)
        except:
            # No Target group found
            if tg_protocol == 'TCP':
                kwargs = {
                    'Name': tg_name,
                    'Protocol': tg_protocol,
                    'Port': port,
                    'VpcId': self.config.get_vpc(),
                    'HealthCheckProtocol': tg_protocol,
                    'HealthCheckPort': str(port),
                    'HealthCheckIntervalSeconds': healthy_check_interval,
                    'HealthyThresholdCount': healthy_threshold,
                    'UnhealthyThresholdCount': healthy_threshold,
                }
            else:
                kwargs = {
                    'Name': tg_name,
                    'Protocol': tg_protocol,
                    'Port': port,
                    'VpcId': self.config.get_vpc(),
                    'HealthCheckProtocol': tg_protocol,
                    'HealthCheckPort': str(port),
                    'HealthCheckPath': path,
                    'HealthCheckIntervalSeconds': healthy_check_interval,
                    'HealthyThresholdCount': healthy_threshold,
                }
            response = self.client.create_target_group(**kwargs)
            tg_arn = response['TargetGroups'][0]['TargetGroupArn']
        # Modify the target group attribute if any
        stickiness, drain_timeout = self.config.get_tg_attributes()
        attributes = []
        if stickiness is not None:
            stickiness = str(stickiness).lower()
            duration = str(120)
            attributes.append({
                'Key': 'stickiness.enabled',
                'Value': stickiness,
            })

            attributes.append(
                {
                    'Key': 'stickiness.type',
                    'Value': 'lb_cookie',
                })
            attributes.append(
                {
                    'Key': 'stickiness.lb_cookie.duration_seconds',
                    'Value': duration,
                })
        if drain_timeout != None:
            attributes.append(
                {
                    'Key': 'deregistration_delay.timeout_seconds',
                    'Value': str(drain_timeout),
                })

        if len(attributes) > 0:
            self.client.modify_target_group_attributes(
                TargetGroupArn=tg_arn,
                Attributes=attributes)
        # log some information
        self.log.debug("TargetGroup: %s", response)
        for tg in response['TargetGroups']:
            self.tg_arn = tg['TargetGroupArn']
            self.log.info("Created/Updated TargetGroup: TGName:%s TGArn:%s ",
                          tg['TargetGroupName'], self.tg_arn)
            return tg  # There should only be one target group in the returned response array
        return None

    def getTargetGroupArn(self):
        """
        Return the cached value of target group ARN
        """
        return self.tg_arn

    def get_lb_and_tg(self):
        lb_arn, _dns_name = self.get_lb_details()
        tg = self.get_first_matching_target_group(lb_arn)
        tg_arn = tg['TargetGroupArn']
        return lb_arn, tg_arn

    def _remove_instances(self, instances, blocking):
        _, tg = self.get_lb_and_tg()
        for i in instances:
            response = self.client.deregister_targets(
                TargetGroupArn=tg,
                Targets=[
                    {
                        'Id': i,
                    },
                ]
            )
            self.log.info('Deregistering target %s. Response %s', i, response)
            self.log.info('Tg %s', tg)
            if blocking:
                while True:
                    response = self.client.describe_target_health(
                        TargetGroupArn=tg,
                        Targets=[
                            {
                                'Id': i,
                            }
                        ]
                    )
                    if len(response['TargetHealthDescriptions']) == 0:
                        break
                    state = response['TargetHealthDescriptions'][0]['TargetHealth']['State']
                    if state == 'draining':
                        self.log.info(
                            'Instance %s is still draining. State %s', i, state)
                        time.sleep(30)
                    else:
                        self.log.info(
                            'Finished draining instance %s State %s', i, state)
                        break

    def remove_instances(self, instances):
        """
        Remove instances from this Load balancer
        """
        self._remove_instances(instances, blocking=True)

