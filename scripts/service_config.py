#!/bin/python

"""
Use get('staging') (or 'prod') to get the service definition based on configuration file.
Service definition is a JSON object containing the names of the various resources like 'SQS', 'LB' based on the prefix and region
"""

import string
import json
import pprint
import logger
import yaml
import sys
import yaml_with_custom_extn


class Config():
    """
    Composition of the various services and their values.
    """
    state = {}
    log = None

    def __init__(self, config):
        self.state = config
        self.ecs_cluster_name_key = 'ecs_cluster_name'
        self.ecs_service_name_key = 'ecs_service_name'
        self.lb_name_key = 'lb_name'
        self.tg_name_key = 'tg_name'
        self.ec2_name_key = 'ec2_name'
        required_keys = [self.ecs_cluster_name_key, 'region', 'prefix']
        for k in required_keys:
            if k not in config:
                raise KeyError('Missing required ' +
                               k + ' name in config file')

    def get_prefix(self):
        return self.state['prefix']

    def get_prefix_str(self):
        prefix_str = self.state['prefix']
        if prefix_str:
            prefix_str = prefix_str + '-'
        else:
            prefix_str = ''
        return prefix_str

    def get_service_type_str(self):
        """
        Create the service_type prefix, like 'upload-', 'mixdown-' etc.
        """
        service_type_str = self.state['service_type']
        if service_type_str:
            service_type_str = service_type_str + '-'
        else:
            service_type_str = ''
        return service_type_str

    def get_service_version(self):
        return self.state['docker_image_tag']

    def get_cmdline_env_flag(self):
        return self.state['cmdline_env_flag']

    def create_name_with_separator(self, name_array):
        """
        Create a name for the AWS component of the form <prefix>-<service>-<the-supplied-name>-<env>-<region>
        """
        sep = '-'
        name = sep.join(name_array)
        # Remove leading and traling hyphens
        name = name.lstrip(sep).rstrip(sep)
        return name

    def create_name(self, name_array):
        """
        Create a name by concatenating elements of the name_array
        """
        name = ''.join(name_array)
        return name

    # Getter function which return the names of various components.
    def get_ecs_cluster_name(self):
        """
        Create the name of the cluster
        """
        return self.create_name_with_separator(self.state[self.ecs_cluster_name_key])

    def get_raw_service_name(self):
        """
        Get the undecorated service name.
        """
        return self.state['service_name']

    def get_ecs_service_name(self):
        return self.create_name_with_separator(self.state[self.ecs_service_name_key])

    def get_lb_name(self):
        name = self.create_name_with_separator(self.state[self.lb_name_key])
        return name

    def get_lb_type(self):
        return self.state['lb_type']

    def get_tg_name(self):
        name = self.create_name_with_separator(self.state[self.tg_name_key])
        return name

    def get_tg_protocol(self):
        return self.state['tg_protocol']

    def get_as_name(self):
        name = self.create_name_with_separator(
            self.state['auto_scale_group']['name'])
        return name

    def get_launch_config_name(self):
        name = self.create_name_with_separator(
            self.state['auto_scale_group']['launch_config_name'])
        return name

    def get_alarm_name(self):
        name = self.create_name_with_separator(self.state['alarm']['name'])
        return name

    def get_alarm_action(self):
        name = self.create_name_with_separator(
            self.state['alarm']['alarm_action'])
        return name

    def get_ec2_name(self):
        return self.create_name_with_separator(self.state[self.ec2_name_key])

    def get_instance_type(self):
        return self.state.get('instance_type', 't2.micro')

    def get_region(self):
        return self.state['region']

    def get_sqs(self):
        if 'sqs' in self.state:
            return self.state['sqs']
        return None

    def get_sqs_account(self):
        return self.state['sqs_account']

    def get_tg_health_check_info(self):
        port = self.state['tg_health_check_port']
        path = self.state['tg_health_check_path']
        healthy_threshold = self.state.get('tg_healthy_threshold', 5)
        healthy_check_interval = self.state.get('tg_health_check_interval', 30)
        return port, path, healthy_threshold, healthy_check_interval

    def get_tg_attributes(self):
        tg_stickiness = self.state.get('tg_stickiness', None)
        tg_connection_drain_timeout = self.state.get(
            'tg_connection_drain_timeout', None)
        return tg_stickiness, tg_connection_drain_timeout

    def get_main_listener_info(self):
        port = self.state['lb_port']
        protocol = self.state['tg_protocol']
        return port, protocol

    def get_alt_listener_infos(self):
        if 'lb_listeners' in self.state:
            return self.state['lb_listeners']
        return []

    def get_lb_timeouts(self):
        lb_idle_timeout = self.state.get('lb_idle_timeout', None)
        return lb_idle_timeout

    def get_named_components(self):
        """
        Map of component and its name. Used for logging/debugging
        """
        m = {
            self.ecs_cluster_name_key: self.get_ecs_cluster_name(),
            self.ecs_service_name_key: self.get_ecs_service_name(),
            self.lb_name_key: self.get_lb_name(),
            self.tg_name_key: self.get_tg_name(),
            'auto_scale_group.name': self.get_as_name(),
            'auto_scale_group.launch_config_name': self.get_launch_config_name(),
            'alarm.name': self.get_alarm_name(),
            'alarm.alarm_action': self.get_alarm_action(),
            self.ec2_name_key: self.get_ec2_name(),
        }
        return m

    def get_ssh_key(self):
        return self.state['sshkey']

    def get_ec2_iam_role(self):
        return self.state['ec2_iam_role']

    def get_vpc(self):
        return self.state['vpc']

    def get_ami(self):
        return self.state['ami']

    def get_security_groups(self):
        return self.state['security_groups']

    def get_subnets(self):
        return self.state['subnets']

    def get_task_def_network_mode(self):
        return self.state.get('task_def_network_mode', 'bridge')

    def get_container_definition(self):
        return self.state['container_definition']

    def get_task_definition_name(self):
        """
        For now container definition name is same as task definition name
        """
        td = self.state['container_definition']
        return self.create_name_with_separator(td['name'])

    def get_ecs_role(self):
        return self.state['ecs_role']

    def get_alarm(self):
        return self.state['alarm']

    def get_nginx_location_param(self):
        return self.state['nginx_location_param']

    def get_auto_scale_desired_count(self):
        desired = self.state['auto_scale_group']['desired']
        return desired

    def get_auto_scale_cpu_threshold(self):
        threshold = self.state['auto_scale_group']['cpu_threshold']
        if threshold <= 0 | threshold > 100:
            threshold = 70
        return threshold

    def get_launch_ec2_with_public_ip(self):
        return self.state.get('launch_ec2_with_public_ip',
                              True  # FIXME: Should be False by default, revisit
                              )

    def get_auto_scale_params(self):
        min = self.state['auto_scale_group']['min']
        max = self.state['auto_scale_group']['max']
        desired = self.state['auto_scale_group']['desired']
        availability_zones = self.state['auto_scale_group']['availability_zones']
        vpc_zone_identifier = self.state['auto_scale_group']['vpc_zone_identifier']
        default_cooldown = self.state['auto_scale_group']['default_cooldown']
        return min, max, desired, availability_zones, vpc_zone_identifier, default_cooldown

    def log_component_names(self):
        s = pprint.PrettyPrinter(4).pformat(self.get_named_components())
        logger.logger.info('Component names are: %s', s)
        return

    def dump(self, stream=None):
        return yaml.safe_dump(self.state, stream=stream)

    @staticmethod
    def pretty_print_json(js):
        return json.dumps(js, indent=4)


def load_config_from(filename):
    """
    Load YAML file without any custom mapping
    """
    with open(filename, 'r') as stream:
        config_data = yaml.safe_load(stream)
        config = Config(config_data)
        return config


def load_config_with_extension(filename, custom_fn_map):
    """
    Load YAML file with custom mapping.
    E.g. RTC yaml file can specific a function to get the audio/video server
    LB address and set it in the task definition command line params.
    If |custom_fn_map| is None then no mapping is loaded
    """
    config_data = yaml_with_custom_extn.load_config_with_custom_extension(
        filename, custom_fn_map)
    config = Config(config_data)
    return config
